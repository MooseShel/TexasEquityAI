import asyncio
import logging
import re
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

                # Neighborhood Code - Robust extraction
                nbhd_found = "Unknown"
                nbhd_labels = ["Neighborhood Code", "Neighborhood", "NBHD"]
                for label in nbhd_labels:
                    loc = page.locator(f"p:has-text('{label}')")
                    if await loc.count() > 0:
                        txt = await loc.first.inner_text()
                        if ":" in txt:
                            val = txt.split(":")[-1].strip()
                            # Clean up characters like +++ or spaces
                            val = re.sub(r'[^a-zA-Z0-9\s\.\-]', '', val).strip()
                            if val and val != "0": 
                                nbhd_found = val
                                break
                details['neighborhood_code'] = nbhd_found

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
                        mkt_val = self._parse_currency(mkt_val_str)
                        if mkt_val > 0:
                            details['market_value'] = mkt_val
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

                 # Building Area - Multi-label robust extraction
                area_found = 0
                area_labels = [
                    "Gross Building Area", "Living Area", "Main Area", 
                    "Net Area", "Total Building Area", "Improvements SQ FT",
                    "Total Area", "Building Area"
                ]
                
                body_text = await page.evaluate("() => document.body.innerText")
                
                # 1. Try specific locators
                for label in area_labels:
                    loc = page.locator(f"p:has-text('{label}')")
                    if await loc.count() > 0:
                        txt = await loc.first.inner_text()
                        logger.info(f"TAD Area Trace: Found label '{label}' with text '{txt}'")
                        if ":" in txt:
                            clean = txt.split(":")[-1].strip().replace(",", "")
                            match = re.search(r"(\d+)", clean)
                            if match:
                                val = int(match.group(1))
                                if val > area_found: area_found = val

                # 2. Regex fallback on full text if still 0
                if area_found == 0:
                    logger.info("TAD Area Trace: No specific label locators found. Trying regex fallback on body text...")
                    for label in area_labels:
                        match = re.search(f"{label}[:\\s]+([\\d,]+)", body_text, re.IGNORECASE)
                        if match:
                            val = int(match.group(1).replace(",", ""))
                            logger.info(f"TAD Area Trace: Regex found '{label}' value: {val}")
                            if val > area_found: area_found = val
                
                logger.info(f"TAD Extraction Result for {account_number}: Area={area_found}, YearBuilt={details.get('year_built')}")
                details['building_area'] = area_found
                
                # 3. Land Area Fallback
                land_area = 0
                # format often: Land Area: 10,000 SQ FT or Acres
                land_match = re.search(r"Land Area[:\s]+([\d,]+)\s*(?:SQ FT|Sqft)", body_text, re.IGNORECASE)
                if land_match:
                    land_area = int(land_match.group(1).replace(",", ""))
                
                details['land_area'] = land_area
                # If building area is 0, we can use land area if appropriate, but let's keep them separate for now 
                # and let the equity agent decide.
                
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
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"TAD Discovery: Searching for Neighborhood Code '{neighborhood_code}' (Attempt {attempt+1})...")
                    
                    # Navigation Retry Loop for ERR_ABORTED
                    for nav_attempt in range(2):
                        try:
                            await page.goto(self.base_url, timeout=60000, wait_until="load")
                            break
                        except Exception as e:
                            if "ERR_ABORTED" in str(e) and nav_attempt < 1:
                                logger.warning(f"TAD Discovery: Navigation aborted, retrying... ({e})")
                                await asyncio.sleep(2)
                                continue
                            raise

                    # Selection Hardening Loop for NeighborhoodCode
                    slct_harden = 0
                    while slct_harden < 3:
                        try:
                            await page.wait_for_selector("#search-type", timeout=20000)
                            await page.select_option("#search-type", "NeighborhoodCode")
                            await asyncio.sleep(2) # Buffer for hydration
                            current_val = await page.eval_on_selector("#search-type", "el => el.value")
                            if current_val == "NeighborhoodCode":
                                break
                        except Exception as e:
                            logger.warning(f"TAD Discovery: NBHD selection try {slct_harden+1} failed: {e}")
                        slct_harden += 1
                        await asyncio.sleep(2)
                    
                    await page.fill("#query", neighborhood_code)
                    await page.keyboard.press("Enter")
                    
                    try:
                        await page.wait_for_load_state("load", timeout=45000)
                        await page.wait_for_selector("table.search-results", timeout=15000)
                    except:
                        pass

                    # Parse Results Table
                    rows = page.locator("table.search-results tbody tr.property-header")
                    count = await rows.count()
                    
                    if count == 0:
                        body_text = await page.evaluate("() => document.body.innerText")
                        if "No properties found" in body_text:
                            logger.info(f"TAD Discovery: Confirmed 0 results for NBHD '{neighborhood_code}'")
                            return []
                        elif attempt < max_retries:
                            logger.warning(f"TAD Discovery: Found 0 results unexpectedly. Retrying whole search...")
                            continue
                        else:
                            logger.warning(f"TAD Discovery: Still 0 results after {max_retries} retries.")
                            return []

                    logger.info(f"TAD Discovery: Found {count} results for NBHD {neighborhood_code}")
                    limit = min(count, 50)
                    for i in range(limit):
                        try:
                            row = rows.nth(i)
                            tds = row.locator("td")
                            td_count = await tds.count()
                            if td_count < 7: # TAD nbhd search results usually have ~7-8 columns
                                continue
                                
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
                        except: continue
                    return neighbors

                except Exception as e:
                    logger.error(f"Error fetching TAD neighbors: {e}")
                    if attempt < max_retries:
                        continue
                    return []
            
            await browser.close()
            return neighbors

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

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Custom Discovery: Search by street name directly on TAD.org
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            async def run_single_search(query_text):
                logger.info(f"TAD Discovery: Searching for street '{query_text}'...")
                
                # Navigation Retry Loop for ERR_ABORTED
                for nav_attempt in range(2):
                    try:
                        await page.goto(self.base_url, timeout=60000, wait_until="load")
                        break
                    except Exception as e:
                        if "ERR_ABORTED" in str(e) and nav_attempt < 1:
                            logger.warning(f"TAD Discovery: Navigation aborted, retrying... ({e})")
                            await asyncio.sleep(2)
                            continue
                        raise

                # Selection Hardening Loop
                slct_harden = 0
                while slct_harden < 3:
                    try:
                        await page.wait_for_selector("#search-type", timeout=20000)
                        await page.select_option("#search-type", "PropertyAddress")
                        await asyncio.sleep(2) # Long buffer for hydration
                        current_val = await page.eval_on_selector("#search-type", "el => el.value")
                        if current_val == "PropertyAddress":
                            break
                    except Exception as e:
                        logger.warning(f"TAD Discovery: Street selection try {slct_harden+1} failed: {e}")
                    slct_harden += 1
                    await asyncio.sleep(2)

                await page.fill("#query", query_text)
                await page.keyboard.press("Enter")
                
                try:
                    await page.wait_for_load_state("load", timeout=45000)
                    await page.wait_for_selector("table.search-results", timeout=15000)
                except:
                    logger.warning("TAD Discovery: Results table did not appear in time.")

                # Parse Results Table
                rows = page.locator("table.search-results tbody tr.property-header")
                count = await rows.count()
                limit = min(count, 50)
                
                found = []
                for i in range(limit):
                    try:
                        row = rows.nth(i)
                        tds = row.locator("td")
                        account = await tds.nth(1).inner_text()
                        address = await tds.nth(2).inner_text()
                        owner = await tds.nth(4).inner_text()
                        mkt_val_str = await tds.nth(5).inner_text()
                        mkt_val = self._parse_currency(mkt_val_str)
                        
                        found.append({
                            "account_number": account.strip(),
                            "address": address.strip(),
                            "owner_name": owner.strip(),
                            "market_value": mkt_val,
                            "district": "TAD"
                        })
                    except: continue 
                return found

            try:
                # 1. Try original street name
                neighbors = await run_single_search(street_name)
                
                # 2. Fallback: If no results and name has directional (e.g. "N WATSON"), try without directional
                if not neighbors and " " in street_name:
                    parts = street_name.split()
                    if parts[0].upper() in ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]:
                        fallback_query = " ".join(parts[1:])
                        logger.info(f"TAD Discovery: No results for '{street_name}'. Trying fallback: '{fallback_query}'")
                        neighbors = await run_single_search(fallback_query)

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
