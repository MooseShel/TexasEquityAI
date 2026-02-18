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
        if self.url and self.key:
            self.client: Client = create_client(self.url, self.key)
        else:
            logger.warning("Supabase URL or Key not found. Database operations will be disabled.")
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

    async def save_equity_comps(self, protest_id: str, comps: list):
        if not self.client: return None
        for comp in comps:
            comp['protest_id'] = protest_id
            self.client.table("equity_comparables").insert(comp).execute()

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

# Singleton instance
supabase_service = SupabaseService()
