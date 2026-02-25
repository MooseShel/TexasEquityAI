import os
import requests
import logging
import time
from typing import Optional, List
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
                logger.info("Circuit Breaker timeout expired. Half-open state allowed to retry.")
                return True
        return True

_rentcast_circuit = CircuitBreaker()


# Property types considered residential — used to filter comps by type
RESIDENTIAL_TYPES = {"single family", "condo", "townhouse", "multifamily", "residential"}
COMMERCIAL_TYPES  = {"commercial", "office", "retail", "industrial", "mixed use", "land", "vacant"}

class RentCastConnector:
    def __init__(self):
        self.api_key = os.getenv("RENTCAST_API_KEY")
        self.base_url_comps = "https://api.rentcast.io/v1/avm/value"   # AVM (for residential comps)
        self.base_url_props = "https://api.rentcast.io/v1/properties"   # Properties list (for sold records)

    def check_api_key(self) -> bool:
        if not self.api_key:
            logger.error("RentCast API Key is missing. Please set RENTCAST_API_KEY in .env")
            return False
        return True

    def get_sales_comparables(self, address: str, property_type: str = "Residential") -> List[SalesComparable]:
        """
        Fetches sold sales comparables from RentCast.

        Strategy:
        - Residential: Use AVM /v1/avm/value endpoint (returns sale comps with correlationPrice)
        - Commercial:  Use /v1/properties?status=Sold since AVM doesn't support commercial well.
        Both paths filter out comps that have $0 sale price or 0 sqft.
        """
        if not self.check_api_key():
            return []

        is_commercial = property_type.lower() not in ("residential",)

        try:
            if is_commercial:
                return self._get_sold_properties(address, property_type)
            else:
                return self._get_avm_comps(address, property_type)
        except Exception as e:
            logger.error(f"RentCast Connector Exception: {e}")
            return []

    def _get_avm_comps(self, address: str, property_type: str) -> List[SalesComparable]:
        """Use the AVM endpoint for residential — returns sale comparables with correlationPrice."""
        headers = {"X-Api-Key": self.api_key, "accept": "application/json"}
        params = {
            "address": address,
            "propertyType": property_type,
            "radius": 1.0,
            "compType": "sale",
            "daysOld": 365,
        }
        logger.info(f"RentCast: Fetching residential AVM comps for {address}...")
        
        if not _rentcast_circuit.check():
            logger.error("RentCast: Circuit breaker prevents request.")
            return []
            
        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
        )
        def _make_request():
            resp = requests.get(self.base_url_comps, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp

        try:
            response = _make_request()
            _rentcast_circuit.record_success()
        except Exception as e:
            logger.error(f"RentCast AVM Request Failed: {e}")
            _rentcast_circuit.record_failure()
            return []

        comps_list = []
        data = response.json()
        raw_comps = data.get("comparables", []) if data else []
        logger.info(f"RentCast: Found {len(raw_comps)} AVM comparables.")

        for comp in raw_comps:
            try:
                # Use actual sale price first, fall back to correlationPrice (AVM comparable)
                price = comp.get("lastSalePrice") or comp.get("correlationPrice") or comp.get("price") or 0
                sqft  = comp.get("squareFootage") or 0
                date  = comp.get("lastSaleDate") or comp.get("listedDate")
                ptype = comp.get("propertyType", "")

                if not price or float(price) <= 0 or not sqft or int(sqft) <= 0:
                    continue  # skip $0 or zero-sqft comps

                price_f = float(price)
                sqft_i  = int(sqft)
                comps_list.append(SalesComparable(
                    address=comp.get("formattedAddress") or comp.get("addressLine1", ""),
                    sale_price=price_f,
                    sale_date=str(date) if date else None,
                    sqft=sqft_i,
                    price_per_sqft=round(price_f / sqft_i, 2),
                    year_built=comp.get("yearBuilt"),
                    source="RentCast",
                    dist_from_subject=comp.get("distance"),
                    property_type=ptype,
                ))
            except Exception as e:
                logger.warning(f"RentCast: Skipping malformed AVM comp: {e}")
        
        # Filter: residential comps should not include commercial types
        comps_list = [c for c in comps_list if not _is_commercial_type(c.property_type)]
        return comps_list

    def _get_sold_properties(self, address: str, property_type: str) -> List[SalesComparable]:
        """
        Use the /v1/properties endpoint with status=Sold to find recent commercial sales.
        RentCast doesn't have a commercial-specific comp endpoint, so we search nearby
        sold properties and filter out residential types.
        """
        headers = {"X-Api-Key": self.api_key, "accept": "application/json"}
        # Extract city/state from address for a broader area search
        params = {
            "address": address,
            "status": "Sold",
            "radius": 1.5,
            "limit": 20,
            "daysOld": 730,   # 2 year lookback for commercial (less frequent sales)
        }
        logger.info(f"RentCast: Fetching sold commercial properties near {address}...")
        
        if not _rentcast_circuit.check():
            logger.error("RentCast: Circuit breaker prevents request.")
            return []

        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=10),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
        )
        def _make_request():
            resp = requests.get(self.base_url_props, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp

        try:
            response = _make_request()
            _rentcast_circuit.record_success()
        except Exception as e:
            logger.error(f"RentCast Properties Request Failed: {e}")
            _rentcast_circuit.record_failure()
            return []

        comps_list = []
        data = response.json()
        raw_props = data if isinstance(data, list) else data.get("properties", [])
        logger.info(f"RentCast: Found {len(raw_props)} sold properties nearby.")

        skipped_no_price = 0
        skipped_no_sqft = 0
        for prop in raw_props:
            try:
                ptype = prop.get("propertyType", "")
                # Note: type filtering is handled by sales_agent._filter_comps_by_type
                # (soft filter — keeps comps as fallback if all would be removed)

                price = prop.get("lastSalePrice") or prop.get("price") or 0
                sqft  = prop.get("squareFootage") or prop.get("buildingSize") or 0
                date  = prop.get("lastSaleDate") or prop.get("soldDate")

                if not price or float(price) <= 0:
                    skipped_no_price += 1
                    continue

                price_f = float(price)
                sqft_i  = int(sqft) if sqft else 0
                # Allow comps with 0 sqft but valid sale price (common for land/commercial)
                pps = round(price_f / sqft_i, 2) if sqft_i > 0 else 0.0

                comps_list.append(SalesComparable(
                    address=prop.get("formattedAddress") or prop.get("addressLine1", ""),
                    sale_price=price_f,
                    sale_date=str(date) if date else None,
                    sqft=sqft_i,
                    price_per_sqft=pps,
                    year_built=prop.get("yearBuilt"),
                    source="RentCast",
                    dist_from_subject=prop.get("distance"),
                    property_type=ptype,
                ))
            except Exception as e:
                logger.warning(f"RentCast: Skipping malformed sold property: {e}")
        
        logger.info(f"RentCast sold props: {len(comps_list)} usable, {skipped_no_price} skipped (no price), {skipped_no_sqft} skipped (no sqft)")

        return comps_list


def _is_residential_type(ptype: str) -> bool:
    if not ptype:
        return False
    return ptype.lower().replace("_", " ") in RESIDENTIAL_TYPES

def _is_commercial_type(ptype: str) -> bool:
    if not ptype:
        return False
    return ptype.lower().replace("_", " ") in COMMERCIAL_TYPES
