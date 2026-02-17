import asyncio
import logging
from typing import Dict, List, Optional
from playwright.async_api import async_playwright
from .base_connector import AppraisalDistrictConnector

logger = logging.getLogger(__name__)

class TADConnector(AppraisalDistrictConnector):
    """
    Connector for Tarrant Appraisal District (TAD) using Playwright for scraping.
    """

    def __init__(self):
        self.base_url = "https://www.tad.org"

    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Dict:
        """
        Scrapes property details from TAD.org given an account number.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # Search Logic
                await page.goto(self.base_url, timeout=60000)
                
                search_val = account_number
                if not search_val and address:
                    search_val = address
                
                if not search_val:
                    raise ValueError("Must provide account_number or address")

                # Fill search form
                await page.fill("#query", search_val)
                
                # If searching by account, try to set the type, otherwise leave as All
                if account_number:
                     # Attempt to select AccountNumber if possible, but All works too
                     pass

                # Click Search
                async with page.expect_navigation(timeout=60000):
                    await page.click(".property-search-form button[type='submit']")

                # Check if we are on details page or results page
                # Results page has table.search-results
                # Details page has h1 containing "Account:"
                
                is_results_list = await page.is_visible("table.search-results")
                
                if is_results_list:
                    # If list, try to click the exact account match
                    # Helper to find link with text == account_number
                    # If not found, click the first one?
                    if account_number:
                        # Try exact match
                        # The account format in table is just numbers, e.g. 04657837
                        # Our account_number might need cleaning
                        clean_acc = account_number.replace("-", "").strip()
                        link = page.get_by_role("link", name=clean_acc, exact=True)
                        if await link.count() > 0:
                            async with page.expect_navigation(timeout=60000):
                                await link.first.click()
                        else:
                             # Fallback to first result
                            async with page.expect_navigation(timeout=60000):
                                await page.click("tr.property-header a")
                    else:
                        # Address search, just click first result
                        async with page.expect_navigation(timeout=60000):
                             await page.click("tr.property-header a")

                # Now scrape details
                details = {}
                
                # Header Info
                h1_text = await page.inner_text("h1") # Account: 04657837
                details['account_number'] = h1_text.replace("Account:", "").strip()
                
                h2_text = await page.inner_text("div.title-container h2") # Address: ...
                details['address'] = h2_text.replace("Address:", "").strip()
                
                # Owner
                # Locate "Current Owner:" then next p
                # Trying more robust selectors
                owner_locator = page.locator("p:has-text('Current Owner:') + p")
                if await owner_locator.count() > 0:
                     details['owner_name'] = (await owner_locator.inner_text()).strip()
                
                owner_addr_locator = page.locator("p:has-text('Primary Owner Address:') + p")
                if await owner_addr_locator.count() > 0:
                    details['mailing_address'] = (await owner_addr_locator.inner_text()).replace("\n", ", ").strip()

                # Legal Description
                legal_locator = page.locator("p:has-text('Legal Description:')")
                if await legal_locator.count() > 0:
                    txt = await legal_locator.inner_text()
                    details['legal_description'] = txt.replace("Legal Description:", "").strip()

                # Neighborhood Code
                nbhd_locator = page.locator("p:has-text('Neighborhood Code:') a")
                if await nbhd_locator.count() > 0:
                    details['neighborhood_code'] = (await nbhd_locator.inner_text()).strip()
                else:
                    details['neighborhood_code'] = "Unknown"

                # Values Table
                # Iterate through rows to find first non-pending value
                rows = page.locator("table.values tbody tr")
                count = await rows.count()
                
                found_val = False
                for i in range(min(count, 3)): # Check first 3 years
                    row = rows.nth(i)
                    tds = row.locator("td")
                    # index 3 = Total Market, 4 = Total Appraised
                    mkt_val_str = await tds.nth(3).inner_text()
                    app_val_str = await tds.nth(4).inner_text()
                    
                    if "Pending" not in mkt_val_str:
                        details['market_value'] = self._parse_currency(mkt_val_str)
                        details['appraised_value'] = self._parse_currency(app_val_str)
                        found_val = True
                        break
                
                if not found_val:
                    details['market_value'] = 0.0
                    details['appraised_value'] = 0.0

                # Year Built
                yb_locator = page.locator("p:has-text('Year Built:')")
                if await yb_locator.count() > 0:
                     txt = await yb_locator.inner_text()
                     clean_txt = txt.lower().replace("year built:", "").strip()
                     details['year_built'] = int(clean_txt) if clean_txt.isdigit() else 0

                # Building Sqft
                sqft_locator = page.locator("p:has-text('Gross Building Area')")
                if await sqft_locator.count() > 0:
                    txt = await sqft_locator.inner_text()
                    # format: Gross Building Area+++: 0
                    clean = txt.split(":")[-1].strip().replace(",", "")
                    details['building_area'] = int(clean) if clean.isdigit() else 0
                
                details['district'] = "TAD"
                
                return details

            except Exception as e:
                logger.error(f"Error scraping TAD details: {e}")
                raise
            finally:
                await browser.close()

    async def get_neighbors(self, neighborhood_code: str) -> List[Dict]:
        """
        Fetches neighbors by searching for the same Neighborhood Code.
        """
        if not neighborhood_code or neighborhood_code == "Unknown":
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            neighbors = []
            try:
                await page.goto(self.base_url, timeout=60000)
                
                # Select NeighborhoodCode search type
                await page.select_option("#search-type", "NeighborhoodCode")
                
                await page.fill("#query", neighborhood_code)
                
                async with page.expect_navigation(timeout=60000):
                    await page.click(".property-search-form button[type='submit']")

                # Parse Results Table
                # table.search-results tbody tr.property-header
                rows = page.locator("table.search-results tbody tr.property-header")
                count = await rows.count()
                
                # Limit to e.g., 50 to match other logic
                limit = min(count, 50)
                
                for i in range(limit):
                    row = rows.nth(i)
                    
                    # Account # is 2nd col (index 1)
                    # Neighborhood Code is 3rd col (index 2)
                    # Address is 4th col (index 3)
                    # City is 5th col (index 4)
                    # Owner is 6th col (index 5)
                    # Market Val is 7th col (index 6)
                    
                    tds = row.locator("td")
                    account = await tds.nth(1).inner_text()
                    address = await tds.nth(3).inner_text()
                    owner = await tds.nth(5).inner_text()
                    mkt_val_str = await tds.nth(6).inner_text()
                    
                    mkt_val = self._parse_currency(mkt_val_str)
                    
                    neighbors.append({
                        "account_number": account.strip(),
                        "address": address.strip(),
                        "owner_name": owner.strip(),
                        "market_value": mkt_val,
                        "district": "TAD"
                    })
                    
                return neighbors

            except Exception as e:
                logger.error(f"Error fetching TAD neighbors: {e}")
                return []
            finally:
                await browser.close()

    async def check_service_status(self) -> bool:
        """
        Checks if TAD website is reachable.
        """
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                response = await page.goto(self.base_url, timeout=30000)
                status = response.ok
                await browser.close()
                return status
            except Exception:
                return False

    async def get_neighbors_by_street(self, street_name: str, zip_code: str) -> List[Dict]:
        """
        Fetches neighbors by searching for the street name.
        """
        # TAD Search handles addresses.
        # We'll search by street name.
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            neighbors = []
            try:
                await page.goto(self.base_url, timeout=60000)
                
                # Default search type is All or Address, which works for street name
                await page.fill("#query", street_name)
                
                async with page.expect_navigation(timeout=60000):
                    await page.click(".property-search-form button[type='submit']")

                # Parse Results Table
                rows = page.locator("table.search-results tbody tr.property-header")
                count = await rows.count()
                limit = min(count, 50)
                
                for i in range(limit):
                    row = rows.nth(i)
                    tds = row.locator("td")
                    account = await tds.nth(1).inner_text()
                    address = await tds.nth(2).inner_text()
                    owner = await tds.nth(4).inner_text()
                    mkt_val_str = await tds.nth(5).inner_text() # Market Value
                    
                    mkt_val = self._parse_currency(mkt_val_str)
                    
                    neighbors.append({
                        "account_number": account.strip(),
                        "address": address.strip(),
                        "owner_name": owner.strip(),
                        "market_value": mkt_val,
                        "district": "TAD"
                    })
                    
                return neighbors

            except Exception as e:
                logger.error(f"Error fetching TAD neighbors by street: {e}")
                return []
            finally:
                await browser.close()

    def _parse_currency(self, val_str: str) -> float:
        """Helper to clean currency strings like '$638,920 (2025)'"""
        try:
            # Remove year info if present "(2025)"
            if "(" in val_str:
                val_str = val_str.split("(")[0]
            
            clean = val_str.replace("$", "").replace(",", "").strip()
            if clean == "Value Pending" or not clean:
                return 0.0
            return float(clean)
        except:
            return 0.0
