import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

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

# Singleton instance
supabase_service = SupabaseService()
