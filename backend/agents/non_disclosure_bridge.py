import os
import requests
import logging
from typing import Optional, Dict

from backend.utils.address_utils import normalize_address_for_search, fuzzy_best_match

logger = logging.getLogger(__name__)

class RentCastAgent:
    def __init__(self):
        self.api_key = os.getenv("RENTCAST_API_KEY")
        self.base_url = "https://api.rentcast.io/v1/properties"

    def _fetch_property(self, address: str) -> Optional[dict]:
        """
        Single internal call to /v1/properties for a given address.
        Returns the first matching property dict, or None.
        All public methods share this one HTTP call to avoid duplicates.
        """
        if not self.api_key:
            return None
        try:
            headers = {"X-Api-Key": self.api_key, "accept": "application/json"}
            resp = requests.get(self.base_url, headers=headers,
                                params={"address": address}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0]
                if isinstance(data, dict) and data:
                    return data
            elif resp.status_code == 404:
                logger.info(f"RentCast: No record for '{address}' (404).")
            else:
                logger.warning(f"RentCast returned {resp.status_code} for '{address}'")
        except Exception as e:
            logger.error(f"RentCast fetch failed for '{address}': {e}")
        return None

    async def detect_property_type(self, address: str) -> Optional[str]:
        """
        Quick RentCast lookup to determine property type.
        Reuses _fetch_property — NO extra API call.
        """
        logger.info(f"Resolving Address via RentCast: {address}")
        prop = self._fetch_property(address)
        if prop:
            ptype = prop.get("propertyType")
            logger.info(f"RentCast propertyType for '{address}': {ptype}")
            return ptype
        return None

    async def get_sale_data(self, address: str,
                            cached_prop: Optional[dict] = None) -> Optional[Dict]:
        """
        Returns last sale price/date for an address.
        Accepts an already-fetched property dict to avoid a duplicate API call.
        """
        if not self.api_key:
            logger.warning("RentCast API Key missing.")
            return None
        prop = cached_prop or self._fetch_property(address)
        if prop:
            sale_price = prop.get("lastSalePrice")
            logger.info(f"RentCast found sale price: {sale_price}")
            return {
                "sale_price": sale_price,
                "sale_date": prop.get("lastSaleDate"),
                "source": "RentCast"
            }
        return None

    async def resolve_address(self, address: str) -> Optional[Dict]:
        """
        Resolves a street address to an assessorID and property details.
        Makes exactly ONE RentCast API call and also extracts sale data inline.
        """
        if not self.api_key:
            return None
        logger.info(f"Resolving Address via RentCast: {address}")
        prop = self._fetch_property(address)
        if not prop:
            return None

        details = {
            "account_number": prop.get("assessorID"),
            "address": prop.get("formattedAddress"),
            "appraised_value": 0,
            "building_area": prop.get("squareFootage"),
            "year_built": prop.get("yearBuilt"),
            "legal_description": prop.get("legalDescription"),
            "owner_name": prop.get("ownerName") or prop.get("owner"),
            "mailing_address": prop.get("mailingAddress") or prop.get("ownerMailingAddress"),
            "land_area": prop.get("lotSize"),
            "rentcast_data": prop,       # full payload cached for downstream reuse
            # Sale data baked in — no second call needed
            "_sale_price": prop.get("lastSalePrice"),
            "_sale_date":  prop.get("lastSaleDate"),
        }

        # Appraised value from tax assessments
        tax_assessments = prop.get("taxAssessments", {})
        if tax_assessments:
            latest_year = max(tax_assessments.keys(), key=lambda x: int(x))
            details['appraised_value'] = tax_assessments[latest_year].get('value', 0)

        return details


class NonDisclosureBridge:
    def __init__(self):
        self.rentcast = RentCastAgent()

    async def get_last_sale_price(self, address: str,
                                  resolved_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Returns last sale price.  If resolve_address() was already called, pass in
        the result to skip the duplicate API hit.
        """
        # If the resolved data already has sale info embedded, use it
        if resolved_data and resolved_data.get("_sale_price"):
            return {
                "sale_price": resolved_data["_sale_price"],
                "sale_date":  resolved_data.get("_sale_date"),
                "source": "RentCast"
            }
        # Otherwise fall back to a fresh lookup (only happens if resolve wasn't called)
        data = await self.rentcast.get_sale_data(address)
        if data and data.get("sale_price"):
            return data
        return None

    async def resolve_address(self, address: str) -> Optional[Dict]:
        return await self.rentcast.resolve_address(address)

    async def detect_property_type(self, address: str) -> Optional[str]:
        """
        Returns property type. NOTE: this makes one RentCast call.
        If resolve_address() was already called for this address, consider
        reading rentcast_data['propertyType'] instead to avoid a duplicate.
        """
        return await self.rentcast.detect_property_type(address)

    def calculate_fallback_value(self, neighborhood_sales: list) -> float:
        if not neighborhood_sales: return 1.0
        ratios = [s['sale_price'] / s['appraised_value'] for s in neighborhood_sales if s['appraised_value'] > 0]
        if not ratios: return 1.0
        return sorted(ratios)[len(ratios)//2]

    async def get_estimated_market_value(self, appraised_value: float, address: str) -> float:
        return appraised_value

    async def resolve_account_id(self, raw_address: str, district: str = None) -> Optional[Dict]:
        """
        ID-first resolution chain: resolves a street address to an appraisal district
        account number BEFORE any Playwright scraping is attempted.

        Chain order:
          [1] Supabase DB  — normalized ILIKE search (free, instant)
          [2] RentCast     — returns assessorID for residential properties
          [3] RealEstateAPI — checks raw payload for assessorID (good for commercial)

        Returns a dict:
          {
            "account_number": str,
            "district":       str | None,   # inferred from ID format or district arg
            "source":         str,           # "DB" | "RentCast" | "RealEstateAPI"
            "rentcast_data":  dict | None,   # cached RentCast payload for downstream reuse
            "confidence":     float,         # 1.0 for exact matches, <1.0 for fuzzy DB hits
          }
        Returns None if all layers fail (caller should fall through to scraper with normalized addr).
        """
        # Lazy imports to avoid circular-import issues at module load time
        from backend.db.supabase_client import supabase_service
        from backend.agents.realestate_api_connector import RealEstateAPIConnector
        from backend.agents.district_factory import DistrictConnectorFactory

        normalized = normalize_address_for_search(raw_address)
        logger.info(f"resolve_account_id: raw='{raw_address}' → normalized='{normalized}'")

        # ── Layer 1: Supabase DB ──────────────────────────────────────────────
        try:
            candidates = await supabase_service.search_address_globally(normalized)
            if not candidates:
                # retry with original in case DB stored un-normalized form
                candidates = await supabase_service.search_address_globally(raw_address)
            if candidates:
                best = fuzzy_best_match(normalized, candidates, key='address')
                if best and best.get('account_number'):
                    acc = best['account_number']
                    dist = best.get('district') or district or DistrictConnectorFactory.detect_district_from_account(acc)
                    logger.info(f"resolve_account_id [DB]: resolved '{raw_address}' → '{acc}' (district={dist})")
                    return {
                        "account_number": acc,
                        "district":       dist,
                        "source":         "DB",
                        "rentcast_data":  None,
                        "confidence":     1.0 if len(candidates) == 1 else 0.85,
                    }
        except Exception as e:
            logger.warning(f"resolve_account_id: DB layer failed ({e}) — continuing")

        # ── Layer 2: RentCast ─────────────────────────────────────────────────
        try:
            resolved = await self.rentcast.resolve_address(normalized or raw_address)
            if resolved and resolved.get('account_number'):
                acc = resolved['account_number']
                dist = district or DistrictConnectorFactory.detect_district_from_account(acc)
                logger.info(f"resolve_account_id [RentCast]: resolved '{raw_address}' → '{acc}' (district={dist})")
                return {
                    "account_number": acc,
                    "district":       dist,
                    "source":         "RentCast",
                    "rentcast_data":  resolved,   # full payload — reused downstream
                    "confidence":     1.0,
                }
        except Exception as e:
            logger.warning(f"resolve_account_id: RentCast layer failed ({e}) — continuing")

        # ── Layer 3: RealEstateAPI ────────────────────────────────────────────
        try:
            reapi = RealEstateAPIConnector()
            acc = reapi.resolve_to_account_id(normalized or raw_address)
            if acc:
                dist = district or DistrictConnectorFactory.detect_district_from_account(acc)
                logger.info(f"resolve_account_id [RealEstateAPI]: resolved '{raw_address}' → '{acc}' (district={dist})")
                return {
                    "account_number": acc,
                    "district":       dist,
                    "source":         "RealEstateAPI",
                    "rentcast_data":  None,
                    "confidence":     1.0,
                }
        except Exception as e:
            logger.warning(f"resolve_account_id: RealEstateAPI layer failed ({e}) — continuing")

        # ── Layer 4: District Connector search_by_address ─────────────────────
        # Last resort: use the district connector's API-based address search
        # (e.g. CCAD Socrata). Only non-scraper connectors have this.
        try:
            target_district = district or "HCAD"
            connector = DistrictConnectorFactory.get_connector(target_district)
            result = await connector.search_by_address(normalized or raw_address)
            if result and result.get('account_number'):
                acc = result['account_number']
                dist = result.get('district') or target_district
                logger.info(f"resolve_account_id [Connector]: resolved '{raw_address}' → '{acc}' (district={dist})")
                return {
                    "account_number": acc,
                    "district":       dist,
                    "source":         "Connector",
                    "rentcast_data":  None,
                    "confidence":     0.9,
                }
        except Exception as e:
            logger.warning(f"resolve_account_id: Connector search_by_address failed ({e}) — continuing")

        logger.info(f"resolve_account_id: all layers exhausted for '{raw_address}' — caller should scrape with normalized address: '{normalized}'")
        return None
