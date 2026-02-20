import os
import httpx
import requests  # used by _reapi_lookup (sync context only)
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class CommercialEnrichmentAgent:
    """
    Enriches commercial property records using RentCast and RealEstateAPI
    when district scrapers return no usable data.

    Provides:
    - enrich_property()      → normalized property dict (appraised_value, building_area, etc.)
    - get_equity_comp_pool() → sales comps reshaped for EquityAgent.find_equity_5()
    """

    def __init__(self):
        self.rentcast_key = os.getenv("RENTCAST_API_KEY")
        self.reapi_key = os.getenv("REALESTATEAPI_KEY")
        self.rentcast_props_url = "https://api.rentcast.io/v1/properties"
        self.reapi_base = "https://api.realestateapi.com/v2"

    # ─── Primary: RentCast /properties ───────────────────────────────────────

    async def _rentcast_lookup(self, address: str) -> Optional[Dict]:
        """Query RentCast /properties and return a normalized property dict (async, non-blocking)."""
        if not self.rentcast_key:
            logger.warning("CommercialEnrichment: RENTCAST_API_KEY not set.")
            return None
        try:
            headers = {"X-Api-Key": self.rentcast_key, "accept": "application/json"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(self.rentcast_props_url, headers=headers, params={"address": address})
            if resp.status_code != 200:
                logger.warning(f"RentCast /properties returned {resp.status_code}: {resp.text[:200]}")
                return None
            data = resp.json()
            prop = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
            if not prop:
                return None

            # Pull appraised value from taxAssessments (latest year)
            appraised_value = 0
            tax_assessments = prop.get("taxAssessments", {})
            if tax_assessments:
                try:
                    latest_year = max(tax_assessments.keys(), key=lambda x: int(x))
                    appraised_value = float(tax_assessments[latest_year].get("value", 0) or 0)
                except Exception:
                    pass

            # Also check lastSalePrice as a value proxy if no tax assessment
            last_sale = float(prop.get("lastSalePrice") or 0)
            if appraised_value == 0 and last_sale > 0:
                appraised_value = last_sale

            result = {
                "account_number": prop.get("assessorID"),
                "address": prop.get("formattedAddress") or address,
                "appraised_value": appraised_value,
                "building_area": float(prop.get("squareFootage") or 0),
                "lot_size": float(prop.get("lotSize") or 0),
                "year_built": prop.get("yearBuilt"),
                "property_type": prop.get("propertyType", "Commercial"),
                "last_sale_price": last_sale,
                "last_sale_date": prop.get("lastSaleDate"),
                "source": "RentCast",
            }
            logger.info(f"CommercialEnrichment: RentCast enriched → appraised=${result['appraised_value']:,.0f}, area={result['building_area']} sqft")
            return result
        except Exception as e:
            logger.error(f"CommercialEnrichment: RentCast lookup failed: {e}")
            return None

    # ─── Fallback: RealEstateAPI /PropertyDetail ──────────────────────────────

    def _reapi_lookup(self, address: str) -> Optional[Dict]:
        """Query RealEstateAPI /PropertyDetail and return a normalized property dict."""
        if not self.reapi_key:
            logger.warning("CommercialEnrichment: REALESTATEAPI_KEY not set.")
            return None
        try:
            headers = {"x-api-key": self.reapi_key, "Content-Type": "application/json"}
            resp = requests.post(f"{self.reapi_base}/PropertyDetail", json={"address": address}, headers=headers, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"RealEstateAPI /PropertyDetail returned {resp.status_code}: {resp.text[:200]}")
                return None
            raw = resp.json()
            if not raw:
                return None

            # Support both dict and list responses
            prop = raw[0] if isinstance(raw, list) else raw

            # Appraised value — try multiple keys
            appraised_value = float(
                prop.get("assessedValue")
                or prop.get("assessedTotalValue")
                or prop.get("taxAssessedValue")
                or prop.get("lastSalePrice")
                or prop.get("estimatedValue")
                or 0
            )

            building_area = float(
                prop.get("buildingArea")
                or prop.get("buildingSize")
                or prop.get("squareFootage")
                or prop.get("grossBuildingArea")
                or 0
            )

            result = {
                "account_number": prop.get("apn") or prop.get("countyTaxId"),
                "address": prop.get("formattedAddress") or prop.get("address") or address,
                "appraised_value": appraised_value,
                "building_area": building_area,
                "lot_size": float(prop.get("lotSize") or 0),
                "year_built": prop.get("yearBuilt"),
                "property_type": prop.get("propertyType") or prop.get("useCode") or "Commercial",
                "last_sale_price": float(prop.get("lastSalePrice") or 0),
                "last_sale_date": prop.get("lastSaleDate") or prop.get("saleDate"),
                "source": "RealEstateAPI",
            }
            logger.info(f"CommercialEnrichment: RealEstateAPI enriched → appraised=${result['appraised_value']:,.0f}, area={result['building_area']} sqft")
            return result
        except Exception as e:
            logger.error(f"CommercialEnrichment: RealEstateAPI lookup failed: {e}")
            return None

    # ─── Public API ───────────────────────────────────────────────────────────

    async def enrich_property(self, address: str) -> Optional[Dict]:
        """
        Try RentCast then RealEstateAPI to build a normalized property dict.
        Returns the first successful result with at least some useful data.
        """
        # Try RealEstateAPI first (better commercial coverage)
        result = self._reapi_lookup(address)
        if result and (result.get("appraised_value", 0) > 0 or result.get("building_area", 0) > 0):
            return result

        # Fallback to RentCast
        result = await self._rentcast_lookup(address)
        if result and (result.get("appraised_value", 0) > 0 or result.get("building_area", 0) > 0):
            return result

        # Return whatever we have (even if mostly empty) so downstream can decide
        logger.warning(f"CommercialEnrichment: No usable data found for '{address}' from RealEstateAPI or RentCast. Trying HCAD scraper fallback...")

        # Fallback 3: HCAD scraper via street-level discovery
        # Use get_neighbors_by_street to find the account number, then scrape full details
        hcad_result = await self._hcad_scraper_fallback(address)
        if hcad_result and (hcad_result.get("appraised_value", 0) > 0 or hcad_result.get("building_area", 0) > 0):
            return hcad_result

        logger.error(f"CommercialEnrichment: All sources exhausted for '{address}'. No usable data found.")
        return None

    async def _hcad_scraper_fallback(self, address: str) -> Optional[Dict]:
        """
        Last-resort fallback: use HCAD's street-level discovery to find the account number
        matching this address, then scrape full property details.
        Works for Houston-area commercial properties not in RentCast or RealEstateAPI.
        """
        try:
            from backend.agents.hcad_scraper import HCADScraper
            scraper = HCADScraper()

            print(f"DEBUG: _hcad_scraper_fallback called with address: '{address}'")

            # Parse street name and number from address
            # e.g. "28750 Tomball Pkwy, Houston, TX" -> street="Tomball Pkwy", num="28750"
            addr_clean = address.split(",")[0].strip()  # drop city/state suffix
            parts = addr_clean.split()
            if not parts:
                return None

            # First token is the street number if it starts with a digit
            street_num = None
            street_parts = parts
            if parts[0][0].isdigit():
                street_num = parts[0]
                street_parts = parts[1:]
            
            try:
                with open("debug_hcad_address.txt", "a") as f:
                    import datetime
                    ts = datetime.datetime.now().isoformat()
                    f.write(f"{ts} DEBUG: address='{address}', cleaned='{addr_clean}', parts={parts}, street_num='{street_num}'\\n")
            except Exception as e:
                logger.error(f"Failed to write debug file: {e}")

            # Clean street parts: remove City, State, Zip if present at the end
            # e.g. ['Hempstead', 'Rd', 'Houston', 'TX'] -> ['Hempstead', 'Rd']
            IGNORED_TOKENS = {"HOUSTON", "TX", "TEXAS", "HARRIS", "USA", "KATY", "HUMBLE", "PASADENA", "TOMBALL", "CYPRESS", "SPRING"}
            while street_parts and (street_parts[-1].upper() in IGNORED_TOKENS or (street_parts[-1].isdigit() and len(street_parts[-1]) == 5)):
                street_parts.pop()

            street_name = " ".join(street_parts)

            if not street_name:
                logger.warning(f"CommercialEnrichment: Could not parse street name from '{address}'.")
                return None

            # Build street name variants to try — HCAD indexes addresses inconsistently.
            # Order: original → abbreviated directions → no street-type suffix.
            # e.g. "North Loop W" → "N Loop W"; "Hempstead Rd" → "Hempstead"

            # Street type suffixes HCAD sometimes omits
            STREET_SUFFIXES = {
                "Rd", "Road", "St", "Street", "Ave", "Avenue", "Blvd", "Boulevard",
                "Dr", "Drive", "Ct", "Court", "Pl", "Place", "Ln", "Lane",
                "Fwy", "Freeway", "Hwy", "Highway", "Pkwy", "Parkway",
                "Cir", "Circle", "Trl", "Trail", "Way", "Expy", "Expressway",
            }

            def abbreviated(name: str) -> str:
                """Abbreviate directional words and street types."""
                abbrevs = {
                    "North": "N", "South": "S", "East": "E", "West": "W",
                    "Boulevard": "Blvd", "Avenue": "Ave", "Street": "St",
                    "Drive": "Dr", "Court": "Ct", "Place": "Pl", "Lane": "Ln",
                    "Road": "Rd", "Freeway": "Fwy", "Highway": "Hwy",
                    "Parkway": "Pkwy", "Circle": "Cir", "Trail": "Trl",
                }
                tokens = name.split()
                return " ".join(abbrevs.get(t, t) for t in tokens)

            street_variants = [street_name]
            abbrev = abbreviated(street_name)
            if abbrev != street_name:
                street_variants.append(abbrev)

            # Also try without the trailing street-type token (e.g. "Hempstead Rd" → "Hempstead")
            def drop_suffix(name: str) -> str:
                tokens = name.split()
                if tokens and tokens[-1] in STREET_SUFFIXES:
                    return " ".join(tokens[:-1])
                return name

            for base in list(street_variants):  # iterate over original + abbrev
                no_suffix = drop_suffix(base)
                if no_suffix != base and no_suffix not in street_variants:
                    street_variants.append(no_suffix)

            print(f"DEBUG: Street variants for '{address}': {street_variants}")

            neighbors = []
            for variant in street_variants:
                # Build the full address search term (number + street) for HCAD
                # so it narrows to the correct block instead of returning all of the street
                if street_num:
                    full_search = f"{street_num} {variant}"
                else:
                    full_search = variant
                print(f"DEBUG: Trying HCAD search: '{full_search}' (variant: '{variant}')")
                logger.info(f"CommercialEnrichment: HCAD search for '{full_search}'")
                neighbors = await scraper.get_neighbors_by_street(variant, search_term=full_search)
                if neighbors:
                    logger.info(f"CommercialEnrichment: Found {len(neighbors)} results for '{full_search}'")
                    print(f"DEBUG: Success! Found {len(neighbors)} neighbors.")
                    break
                logger.info(f"CommercialEnrichment: No results for '{full_search}', trying next variant...")
                print(f"DEBUG: No results for '{full_search}'")

            if not neighbors:
                logger.warning(f"CommercialEnrichment: No HCAD neighbors found for any variant of '{street_name}'.")
                return None

            # The get_neighbors_by_street JS now extracts real street addresses (not owner names).
            # Match the target street number directly in the neighbor list — no extra scraping needed.
            target_account = None
            for n in neighbors:
                n_addr = str(n.get("address", ""))
                if street_num and n_addr.startswith(street_num):
                    target_account = n["account_number"]
                    logger.info(f"CommercialEnrichment: Direct address match → account {target_account} at '{n_addr}'")
                    break

            # Fallback: if no direct match (address field was 'Unknown'), use the first result
            if not target_account:
                target_account = neighbors[0]["account_number"]
                logger.info(f"CommercialEnrichment: No direct match — using first result: account {target_account}")

            # Scrape ONLY the one matching account (avoids concurrent 6-browser overhead)
            logger.info(f"CommercialEnrichment: Scraping account {target_account}...")
            best_match = None
            try:
                best_match = await scraper.get_property_details(target_account)
            except Exception as e:
                logger.error(f"CommercialEnrichment: HCAD account scrape failed: {e}")

            if not best_match:
                logger.warning(f"CommercialEnrichment: HCAD scrape returned no details for account '{target_account}'.")
                return None

            details = best_match

            # Normalize to the commercial enrichment format
            appraised = float(details.get("appraised_value") or 0)
            return {
                "address": details.get("address") or address,
                "appraised_value": appraised,
                "building_area": float(details.get("building_area") or 0),
                "lot_size": 0.0,
                "year_built": details.get("year_built"),
                "property_type": "Commercial",
                "last_sale_price": 0.0,
                "last_sale_date": None,
                "neighborhood_code": details.get("neighborhood_code"),
                "account_number": target_account,
                "district": "HCAD",
                "source": "HCAD",
            }
        except Exception as e:
            logger.error(f"CommercialEnrichment: HCAD scraper fallback failed: {e}")
            return None


    def get_equity_comp_pool(self, address: str, property_details: Dict) -> List[Dict]:
        """
        Build an EquityAgent-compatible neighbor pool from sales comps.
        Uses SalesAgent (RealEstateAPI + RentCast) to find nearby sales,
        then reshapes each comp into {appraised_value, building_area, year_built, address}.
        sale_price is used as a proxy for appraised_value since tax records are unavailable.
        """
        from backend.agents.sales_agent import SalesAgent

        agent = SalesAgent()
        raw_comps = agent.find_sales_comps(property_details)

        # Subject building area as fallback for comps with missing sqft (e.g. mortgage-inferred)
        subject_area = float(property_details.get("building_area") or 0)

        # Residential types to exclude from the commercial equity pool
        RESIDENTIAL_EXCLUDE = {"single family", "condo", "townhouse", "multifamily", "residential"}

        pool = []
        for comp in raw_comps:
            try:
                # Skip residential comps — commercial subjects should only compare against commercial
                comp_type = (comp.get("Type") or "").lower().replace("_", " ")
                if comp_type in RESIDENTIAL_EXCLUDE:
                    logger.debug(f"CommercialEnrichment: Skipping residential comp: {comp.get('Address')} ({comp_type})")
                    continue

                # Parse sale price from formatted string e.g. "$1,200,000" or "$1,200,000 (est)"
                price_raw = comp.get("Sale Price", "0")
                price_str = price_raw.replace("$", "").replace(",", "").replace("(est)", "").strip()
                price = float(price_str) if price_str and price_str != "N/A" else 0

                # Parse sqft — fall back to subject area so inferred comps aren't dropped
                sqft_raw = comp.get("SqFt", "0")
                sqft_str = sqft_raw.replace(",", "").strip()
                if sqft_str and sqft_str != "N/A":
                    sqft = int(float(sqft_str))
                else:
                    sqft = int(subject_area)  # use subject area as proxy

                year = comp.get("Year Built")
                try:
                    year = int(year) if year and str(year) != "N/A" else None
                except (ValueError, TypeError):
                    year = None

                if price > 0 and sqft > 0:
                    pool.append({
                        "account_number": f"comp_{comp.get('Address', '')[:10]}",
                        "address": comp.get("Address", ""),
                        "appraised_value": price,   # sale price as value proxy for commercial
                        "building_area": sqft,
                        "year_built": year,
                        "property_type": comp.get("Type", "Commercial"),
                        "district": property_details.get("district", "HCAD"),
                        "source": comp.get("Source", "SalesComp"),
                    })
            except Exception as e:
                logger.warning(f"CommercialEnrichment: Skipping malformed comp: {e}")
                continue

        logger.info(f"CommercialEnrichment: Built equity pool of {len(pool)} comps from sales data for '{address}'")
        return pool
