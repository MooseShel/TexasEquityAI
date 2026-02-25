import logging
import httpx
import asyncio
from datetime import datetime, timedelta
import urllib.parse

logger = logging.getLogger(__name__)

class CrimeAgent:
    def __init__(self):
        # Houston Police Department Incidents (SODA API)
        self.soda_url = "https://data.houstontx.gov/resource/m59i-pqwv.json"

    async def get_local_crime_data(self, address: str, radius_miles: float = 0.5) -> dict:
        """Fetches property and violent crime incidents within a radius for external obsolescence."""
        if not address:
            return {"status": "Error", "message": "No address provided.", "count": 0}

        # Geocode the address first using Nominatim
        lat, lon = await self._geocode(address)
        if not lat or not lon:
            logger.warning(f"CrimeAgent could not geocode address: {address}")
            return {"status": "Error", "message": "Could not geocode address.", "count": 0}

        return await self._fetch_houston_crime(lat, lon, radius_miles)

    async def _geocode(self, address: str):
        try:
            async with httpx.AsyncClient() as client:
                query = urllib.parse.quote(f"{address}, Texas")
                url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
                resp = await client.get(url, headers={"User-Agent": "TexasEquityAI/1.0"}, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return float(data[0]['lat']), float(data[0]['lon'])
        except Exception as e:
            logger.error(f"Geocoding failed in CrimeAgent: {e}")
        return None, None

    async def _fetch_houston_crime(self, lat: float, lon: float, radius_miles: float) -> dict:
        radius_meters = int(radius_miles * 1609.34)
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000')

        # Assuming standard SODA point column is 'location' or fallback to latitude/longitude
        query_params = {
            "$where": f"within_circle(location, {lat}, {lon}, {radius_meters}) AND incident_date >= '{one_year_ago}'",
            "$limit": 500
        }

        try:
             async with httpx.AsyncClient() as client:
                 resp = await client.get(self.soda_url, params=query_params, timeout=5)
                 
                 # SODA Schema fallback if 'location' doesn't exist but lat/lon do
                 if resp.status_code == 400 and 'within_circle' in resp.text:
                      lat_diff = radius_miles / 69.0
                      lon_diff = radius_miles / 54.6
                      alt_where = f"latitude >= {lat-lat_diff} AND latitude <= {lat+lat_diff} AND longitude >= {lon-lon_diff} AND longitude <= {lon+lon_diff} AND incident_date >= '{one_year_ago}'"
                      resp = await client.get(self.soda_url, params={"$where": alt_where, "$limit": 500}, timeout=5)

                 if resp.status_code != 200:
                     logger.warning(f"CrimeAgent SODA API failed: {resp.status_code} - {resp.text}")
                     return {"status": "Error", "message": "Crime API unavailable.", "count": 0}
                 
                 data = resp.json()
                 
                 # Filter locally for specific high-impact external obsolescence crimes
                 # Burglary, Robbery, Theft, Assault, Auto Theft, Homicide
                 target_crimes = ['burglary', 'robbery', 'assault', 'theft', 'motor', 'narcotic', 'weapon', 'homicide', 'murder']
                 relevant_incidents = []
                 for row in data:
                     # Different datasets use different column names for offense type
                     desc = str(row.get('nibrs_description', row.get('offense_type', row.get('primary_type', '')))).lower()
                     if any(tc in desc for tc in target_crimes) or not desc:
                         relevant_incidents.append(row)

                 if len(relevant_incidents) > 0:
                     message = f"High Crime Area: {len(relevant_incidents)} property/violent crimes reported within {radius_miles} miles in the last 12 months."
                 else:
                     message = f"Low Crime Area: {len(relevant_incidents)} property/violent crimes reported within {radius_miles} miles in the last 12 months."

                 return {
                     "status": "Success",
                     "radius_miles": radius_miles,
                     "timeframe_days": 365,
                     "count": len(relevant_incidents),
                     "message": message
                 }
        except Exception as e:
             logger.error(f"CrimeAgent fetch failed: {e}")
             return {"status": "Error", "message": "Could not connect to crime data.", "count": 0}
