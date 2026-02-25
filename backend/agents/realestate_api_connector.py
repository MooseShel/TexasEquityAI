import os
import requests
import logging
import time
from typing import List, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from backend.models.sales_comp import SalesComparable

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Simple memory-based circuit breaker to fail-fast if external API goes down."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.last_failure_time = 0.0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"Circuit Breaker threshold increased: {self.failure_count}/{self.failure_threshold}")

    def record_success(self):
        if self.failure_count > 0:
            logger.info("Circuit Breaker reset: Connection to API restored.")
        self.failure_count = 0

    def check(self) -> bool:
        """Returns True if the circuit is CLOSED (ok to make request). Returns False if OPEN (fail fast)."""
        if self.failure_count >= self.failure_threshold:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure < self.recovery_timeout_sec:
                logger.error(f"Circuit Breaker is OPEN. Failing fast for next {int(self.recovery_timeout_sec - time_since_failure)}s.")
                return False
            else:
                # Half-open: let one request through to test
                logger.info("Circuit Breaker timeout expired. Half-open state allowed to retry.")
                return True
        return True

# Shared circuit breaker instance across all connector instantiations
_realestate_api_circuit = CircuitBreaker()


class RealEstateAPIConnector:
    """
    Connector for RealEstateAPI.com to fetch sales comparables.
    Documentation: https://api.realestateapi.com/v2/PropertyComps
    """
    def __init__(self):
        self.api_key = os.getenv("REALESTATEAPI_KEY")
        self.base_url = "https://api.realestateapi.com/v2"

    def check_api_key(self) -> bool:
        if not self.api_key:
            logger.error("RealEstateAPI Key is missing. Please set REALESTATEAPI_KEY in .env")
            return False
        return True

    def get_sales_comparables(self, address: str, property_type: str = "Residential") -> List[SalesComparable]:
        """
        Fetch sales comparables from RealEstateAPI.
        """
        if not self.check_api_key():
            return []

        # Endpoint: POST /PropertyComps is common for rich searches, or GET. 
        # Based on typical patterns, we'll try POST if parameters are complex, 
        # but let's try the simple GET or POST approach. 
        # API docs usually suggest POST for address matching.
        
        url = f"{self.base_url}/PropertyComps"
        
        # Headers
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Payload
        # We need to structure the address. 
        # Most APIs take a single string or parts. 
        # Let's assume a simple address string payload based on standard practices for this API.
        payload = {
            "address": address,
            # "limit": 10, # Caused validation error
            # "days_old": 365, # Caused validation error
            # "radius": 1.0 # Optional, default usually 1 mile
        }

        try:
            if not _realestate_api_circuit.check():
                logger.error("RealEstateAPI: Circuit breaker prevents request.")
                return []

            logger.info(f"RealEstateAPI: Fetching sales comps for {address}...")
            
            # Sub-function with tenacity retry for the actual network call
            @retry(
                wait=wait_exponential(multiplier=1, min=2, max=10),
                stop=stop_after_attempt(3),
                retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
            )
            def _make_request():
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                resp.raise_for_status()
                return resp

            response = _make_request()
            _realestate_api_circuit.record_success()
            
            data = response.json()
            # Parse response. Structure is likely: 
            # { "comps": [ { "address": ..., "price": ..., "date": ... } ] } 
            # OR simple list.
            
            # Since we don't have the exact schema, we will wrap in try/except 
            # and log the keys to debug if it fails on first run.
            
            comps = data.get('comps', []) if isinstance(data, dict) else data
            
            if comps:
                logger.info(f"RealEstateAPI: Raw comp keys: {list(comps[0].keys())}")

            sales_comps = []
            for comp in comps:
                # Mapping fields - adjusting based on likely JSON keys
                # address, soldPrice, soldDate, squareFootage, yearBuilt
                try:
                    # Address can be a string or a nested dict
                    raw_addr = comp.get('address', '')
                    if isinstance(raw_addr, dict):
                        # Build clean address from dict fields
                        street = raw_addr.get('street') or raw_addr.get('deliveryLine') or raw_addr.get('line1') or ''
                        city = raw_addr.get('city', '')
                        state = raw_addr.get('state', '')
                        zip_code = raw_addr.get('zip') or raw_addr.get('zipCode') or ''
                        c_addr = f"{street}, {city}, {state} {zip_code}".strip().rstrip(',')
                    else:
                        c_addr = str(raw_addr)
                    
                    if not c_addr or c_addr.strip() in ('', ','): continue
                    
                    # Price — try multiple key names
                    price = (comp.get('soldPrice') or comp.get('lastSalePrice') or 
                             comp.get('price') or comp.get('salePrice') or
                             comp.get('lastSaleAmount') or 0)
                    try:
                        price = float(str(price).replace('$', '').replace(',', ''))
                    except (ValueError, TypeError):
                        price = 0

                    # Skip comps with no real sale price
                    if price <= 0:
                        continue
                    
                    date = comp.get('soldDate') or comp.get('lastSaleDate') or comp.get('date')
                    
                    # SqFt — try multiple key names
                    sqft = (comp.get('squareFootage') or comp.get('buildingSize') or 
                            comp.get('livingArea') or comp.get('sqft') or
                            comp.get('buildingArea') or 0)
                    try:
                        sqft = int(float(str(sqft).replace(',', '')))
                    except (ValueError, TypeError):
                        sqft = 0
                    
                    # Calculate PPS
                    pps = price / sqft if sqft and sqft > 0 and price > 0 else 0
                    
                    # Year built
                    year = comp.get('yearBuilt') or comp.get('year_built')

                    # Property type for filtering
                    ptype = (comp.get('propertyType') or comp.get('useCode') or
                             comp.get('property_type') or '')
                    
                    sales_comps.append(SalesComparable(
                        address=c_addr,
                        sale_price=float(price),
                        sale_date=str(date) if date else None,
                        sqft=int(sqft),
                        price_per_sqft=float(pps),
                        year_built=year,
                        source="RealEstateAPI",
                        dist_from_subject=comp.get('distance'),
                        property_type=ptype,
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing comp: {e}")
                    continue
            
            logger.info(f"RealEstateAPI: Found {len(sales_comps)} comparables.")
            return sales_comps

        except Exception as e:
            logger.error(f"RealEstateAPI Request Failed: {e}")
            _realestate_api_circuit.record_failure()
            return []

    def get_property_detail(self, address: str) -> Optional[dict]:
        """
        Fetch detailed property info from RealEstateAPI /PropertyDetail.
        Returns a normalized dict with standard schema keys, or None on failure.
        """
        if not self.check_api_key():
            return None

        url = f"{self.base_url}/PropertyDetail"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {"address": address}

        try:
            if not _realestate_api_circuit.check():
                logger.error("RealEstateAPI: Circuit breaker prevents request.")
                return None

            logger.info(f"RealEstateAPI: Fetching details for {address}...")
            
            @retry(
                wait=wait_exponential(multiplier=1, min=2, max=10),
                stop=stop_after_attempt(3),
                retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
            )
            def _make_detail_request():
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                resp.raise_for_status()
                return resp

            response = _make_detail_request()
            _realestate_api_circuit.record_success()

            raw = response.json()
            if not raw:
                return None

            # Support both dict and list responses
            prop = raw[0] if isinstance(raw, list) else raw

            # Normalize to standard schema
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

            normalized = {
                "address": prop.get("formattedAddress") or prop.get("address") or address,
                "appraised_value": appraised_value,
                "building_area": building_area,
                "lot_size": float(prop.get("lotSize") or 0),
                "year_built": prop.get("yearBuilt"),
                "property_type": prop.get("propertyType") or prop.get("useCode") or "Commercial",
                "last_sale_price": float(prop.get("lastSalePrice") or 0),
                "last_sale_date": prop.get("lastSaleDate") or prop.get("saleDate"),
                "mortgageHistory": prop.get("mortgageHistory", []),
                # Owner / legal enrichment fields
                "owner_name": prop.get("ownerName") or prop.get("owner"),
                "mailing_address": prop.get("mailingAddress") or prop.get("ownerAddress"),
                "legal_description": prop.get("legalDescription"),
                "land_area": float(prop.get("lotSize") or 0),
                "_raw": prop,
            }
            logger.info(f"RealEstateAPI: Normalized detail → appraised=${normalized['appraised_value']:,.0f}, area={normalized['building_area']} sqft")
            return normalized
        except Exception as e:
            logger.error(f"RealEstateAPI Detail Request Failed: {e}")
            _realestate_api_circuit.record_failure()
            return None

    def resolve_to_account_id(self, address: str) -> Optional[str]:
        """
        Attempts to resolve a street address to an appraisal district account ID.
        Calls /PropertyDetail and inspects the raw payload for any assessor/parcel ID field.
        Returns the first non-empty ID string found, or None.

        Common raw field names across different data providers:
          assessorID, parcelNumber, apn, apnFormatted, taxParcelId,
          parcelId, taxAccountNumber, taxAssessorId
        """
        detail = self.get_property_detail(address)
        if not detail:
            return None
        raw = detail.get('_raw', {})
        if not raw:
            return None

        # Try a prioritised list of field names that carry the assessor/parcel ID
        ID_FIELDS = [
            'assessorID', 'assessorId', 'parcelNumber', 'apn', 'apnFormatted',
            'taxParcelId', 'parcelId', 'taxAccountNumber', 'taxAssessorId',
        ]
        for field in ID_FIELDS:
            val = raw.get(field)
            if val and str(val).strip():
                account_id = str(val).strip()
                logger.info(f"RealEstateAPI resolved '{address}' → account_id='{account_id}' (field: {field})")
                return account_id

        logger.info(f"RealEstateAPI: no assessorID field found for '{address}'. Keys: {list(raw.keys())[:15]}")
        return None
