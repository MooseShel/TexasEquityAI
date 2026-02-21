import os
import json
import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

COMP_CACHE_TTL_DAYS = 30  # Cached comps are considered fresh for 30 days

class SupabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        if not self.url:
            logger.error("SUPABASE_URL is not set — all database operations will be skipped. Set it in .env.")
        if not self.key:
            logger.error("SUPABASE_KEY is not set — all database operations will be skipped. Set it in .env.")
        if self.url and self.key:
            try:
                self.client: Client = create_client(self.url, self.key)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.error(f"Supabase client initialization failed: {e}. Database operations will be disabled.")
                self.client = None
        else:
            self.client = None

    async def get_property_by_account(self, account_number: str):
        if not self.client: return None
        response = self.client.table("properties").select("*").eq("account_number", account_number).execute()
        return response.data[0] if response.data else None

    async def upsert_property(self, property_data: dict):
        if not self.client: return None
        response = self.client.table("properties").upsert(property_data, on_conflict="account_number").execute()
        return response.data[0] if response.data else None

    async def save_protest(self, protest_data: dict):
        if not self.client: return None
        response = self.client.table("protests").insert(protest_data).execute()
        return response.data[0] if response.data else None

    async def get_latest_protest(self, account_number: str):
        """
        Fetches the most recent protest generated for this account.
        """
        if not self.client: return None
        try:
            response = self.client.table("protests") \
                .select("*") \
                .eq("account_number", account_number) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching protest for {account_number}: {e}")
            return None

    async def save_equity_comps(self, protest_id: str, comps: list):
        if not self.client: return None
        # Whitelist of known columns on equity_comparables — prevents PGRST204 on unknown fields
        KNOWN_COLS = {
            'protest_id', 'account_number', 'address', 'owner_name',
            'distance', 'similarity', 'appraised_val', 'market_val',
            'sqft', 'year_built', 'grade', 'cdu', 'adjustments',
            'neighborhood_code', 'building_area', 'appraised_value',
        }
        for comp in comps:
            comp['protest_id'] = protest_id
            # Strip keys not in the DB schema
            clean_comp = {}
            for k, v in comp.items():
                if k in KNOWN_COLS:
                    # Serialize dict/list values to JSON string for JSONB or TEXT columns
                    if isinstance(v, (dict, list)):
                        clean_comp[k] = json.dumps(v)
                    else:
                        clean_comp[k] = v
            try:
                self.client.table("equity_comparables").insert(clean_comp).execute()
            except Exception as e:
                logger.error(f"Failed to insert equity comp: {e}")

    async def get_cached_comps(self, account_number: str, ttl_days: int = COMP_CACHE_TTL_DAYS):
        """
        Returns cached neighbor comps for an account if they exist and are fresh (within ttl_days).
        Returns None if no cache or cache is stale.
        """
        if not self.client: return None
        try:
            response = self.client.table("properties") \
                .select("cached_comps, comps_scraped_at") \
                .eq("account_number", account_number) \
                .execute()
            if not response.data:
                return None
            row = response.data[0]
            cached_comps = row.get("cached_comps")
            comps_scraped_at = row.get("comps_scraped_at")
            if not cached_comps or not comps_scraped_at:
                return None
            # Check TTL
            scraped_dt = datetime.fromisoformat(comps_scraped_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - scraped_dt).days
            if age_days > ttl_days:
                logger.info(f"Cached comps for {account_number} are {age_days} days old (TTL={ttl_days}d) — treating as stale.")
                return None
            logger.info(f"Using cached comps for {account_number} (age: {age_days} days).")
            # Deserialize JSON string if needed
            if isinstance(cached_comps, str):
                cached_comps = json.loads(cached_comps)
            return cached_comps
        except Exception as e:
            logger.warning(f"get_cached_comps failed: {e}")
            return None

    async def save_cached_comps(self, account_number: str, comps: list):
        """
        Saves neighbor comps as JSON to the properties table with a current timestamp.
        """
        if not self.client: return None
        try:
            self.client.table("properties").upsert({
                "account_number": account_number,
                "cached_comps": json.dumps(comps),
                "comps_scraped_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="account_number").execute()
            logger.info(f"Saved {len(comps)} comps to cache for {account_number}.")
        except Exception as e:
            logger.warning(f"save_cached_comps failed: {e}")

    async def get_neighbors_from_db(self, account_number: str, neighborhood_code: str,
                                     building_area: int, district: str = "HCAD",
                                     tolerance: float = 0.35, limit: int = 20) -> list:
        """
        Query Supabase for comparable properties by neighborhood_code and building_area.
        Returns up to `limit` records excluding the subject property.
        Tolerance controls the ±% range for building_area (default ±35%).
        """
        if not self.client or not neighborhood_code or not building_area:
            return []
        try:
            min_area = int(building_area * (1 - tolerance))
            max_area = int(building_area * (1 + tolerance))
            response = (
                self.client.table("properties")
                .select("account_number,address,appraised_value,market_value,building_area,land_area,year_built,neighborhood_code,district,building_grade,building_quality,valuation_history,land_breakdown,last_sale_date,deed_count")
                .eq("neighborhood_code", neighborhood_code)
                .eq("district", district)
                .neq("account_number", account_number)
                .gte("building_area", min_area)
                .lte("building_area", max_area)
                .gt("appraised_value", 0)
                .gt("building_area", 0)
                .limit(limit)
                .execute()
            )
            results = response.data or []
            logger.info(f"DB neighbor lookup: {len(results)} comps for nbhd={neighborhood_code}, area={building_area}±{int(tolerance*100)}%")
            return results
        except Exception as e:
            logger.warning(f"get_neighbors_from_db failed: {e}")
            return []

    async def search_address_globally(self, address_query: str, limit: int = 5) -> list:
        """
        Search for properties by address across ALL districts.
        Useful when user input is ambiguous (e.g. "123 Main St" without City/Zip).
        """
        if not self.client or not address_query: return []
        
        # Basic cleaning to help ILIKE match better
        clean_q = "".join(c for c in address_query if c.isalnum() or c.isspace()).strip()
        if len(clean_q) < 4: return []
        
        try:
            # Use ILIKE for case-insensitive partial match
            # This is fast enough on indexed 'address' column for prefix searches
            # For "123 Main", we might get multiple, but usually user types full street
            response = self.client.table("properties") \
                .select("account_number, address, district, appraised_value") \
                .ilike("address", f"%{clean_q}%") \
                .limit(limit) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.warning(f"search_address_globally failed: {e}")
            return []
    # ── Generic field-level cache helpers ──────────────────────────────────
    #   These read/write JSON blobs + timestamps on the `properties` table.
    #   No schema migration needed — Supabase JSONB columns auto-create on upsert.

    async def _get_cached_field(self, account_number: str, data_col: str, ts_col: str, ttl_days: int):
        """Return cached JSON from `data_col` if `ts_col` is within TTL, else None."""
        if not self.client:
            return None
        try:
            response = self.client.table("properties") \
                .select(f"{data_col}, {ts_col}") \
                .eq("account_number", account_number) \
                .execute()
            if not response.data:
                return None
            row = response.data[0]
            data = row.get(data_col)
            ts = row.get(ts_col)
            if not data or not ts:
                return None
            scraped_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - scraped_dt).days
            if age_days > ttl_days:
                logger.info(f"Cache stale for {account_number}.{data_col} ({age_days}d > {ttl_days}d TTL)")
                return None
            logger.info(f"Cache HIT for {account_number}.{data_col} (age: {age_days}d)")
            if isinstance(data, str):
                data = json.loads(data)
            return data
        except Exception as e:
            logger.warning(f"_get_cached_field({data_col}) failed: {e}")
            return None

    async def _save_cached_field(self, account_number: str, data_col: str, ts_col: str, value):
        """Save a JSON blob + current timestamp to the properties table."""
        if not self.client:
            return
        try:
            self.client.table("properties").upsert({
                "account_number": account_number,
                data_col: json.dumps(value) if isinstance(value, (dict, list)) else value,
                ts_col: datetime.now(timezone.utc).isoformat(),
            }, on_conflict="account_number").execute()
            logger.info(f"Cache SAVED for {account_number}.{data_col}")
        except Exception as e:
            logger.warning(f"_save_cached_field({data_col}) failed: {e}")

    # ── Sales Comp Cache (30-day TTL) ─────────────────────────────────────
    async def get_cached_sales(self, account_number: str):
        return await self._get_cached_field(account_number, "sales_cache", "sales_fetched_at", 30)

    async def save_cached_sales(self, account_number: str, sales_data: list):
        await self._save_cached_field(account_number, "sales_cache", "sales_fetched_at", sales_data)

    # ── FEMA Flood Zone Cache (365-day TTL) ───────────────────────────────
    async def get_cached_flood(self, account_number: str):
        return await self._get_cached_field(account_number, "flood_cache", "flood_fetched_at", 365)

    async def save_cached_flood(self, account_number: str, flood_data: dict):
        await self._save_cached_field(account_number, "flood_cache", "flood_fetched_at", flood_data)

    # ── Vision Analysis Cache (90-day TTL) ────────────────────────────────
    async def get_cached_vision(self, account_number: str):
        return await self._get_cached_field(account_number, "vision_cache", "vision_fetched_at", 90)

    async def save_cached_vision(self, account_number: str, vision_data):
        await self._save_cached_field(account_number, "vision_cache", "vision_fetched_at", vision_data)

    # ── Market Value Cache (30-day TTL) ───────────────────────────────────
    async def get_cached_market(self, account_number: str):
        return await self._get_cached_field(account_number, "market_cache", "market_fetched_at", 30)

    async def save_cached_market(self, account_number: str, market_data: dict):
        await self._save_cached_field(account_number, "market_cache", "market_fetched_at", market_data)

    # ── Deed Data Queries ─────────────────────────────────────────────────
    async def get_deed_history(self, account_number: str) -> list:
        """Returns all deed records for an account, most recent first."""
        if not self.client:
            return []
        try:
            response = self.client.table("property_deeds") \
                .select("acct, date_of_sale, clerk_year, clerk_id, deed_id") \
                .eq("acct", account_number) \
                .order("date_of_sale", desc=True) \
                .execute()
            return response.data or []
        except Exception as e:
            logger.warning(f"get_deed_history failed for {account_number}: {e}")
            return []

    async def get_last_sale_date(self, account_number: str) -> str:
        """
        Returns the most recent sale date for an account.
        First checks properties.last_sale_date (fast), falls back to property_deeds query.
        """
        if not self.client:
            return None
        try:
            # Fast path: check materialized column
            response = self.client.table("properties") \
                .select("last_sale_date") \
                .eq("account_number", account_number) \
                .execute()
            if response.data and response.data[0].get("last_sale_date"):
                return response.data[0]["last_sale_date"]

            # Slow path: query deed records directly
            deeds = await self.get_deed_history(account_number)
            if deeds:
                return deeds[0].get("date_of_sale")
            return None
        except Exception as e:
            logger.warning(f"get_last_sale_date failed for {account_number}: {e}")
            return None

# Singleton instance
supabase_service = SupabaseService()
