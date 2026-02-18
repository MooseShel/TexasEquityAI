import asyncio
import logging
import re
from typing import Dict, List, Optional
from playwright.async_api import async_playwright
from .base_connector import AppraisalDistrictConnector

logger = logging.getLogger(__name__)

class TCADConnector(AppraisalDistrictConnector):
    """
    Connector for Travis Central Appraisal District (TCAD) using Playwright for scraping.
    TCAD uses the Prodigy CAD (True Automation) platform at travis.prodigycad.com.
    """
    DISTRICT_NAME = "TCAD"

    def __init__(self):
        self.base_url = "https://travis.prodigycad.com"
        self.search_url = f"{self.base_url}/property-search"

    async def _get_search_input(self, page):
        """Robust search input finder — tries multiple selectors."""
        search_input = page.get_by_placeholder(re.compile(r"Search by Address, Owner Name, or Property ID", re.IGNORECASE))
        if await search_input.count() > 0:
            return search_input
        # Fallback to any visible text input
        return page.locator("input[type='text']").first

    async def _submit_search(self, page):
        """Robust search submission — tries button then Enter."""
        search_button = page.locator("button >> .MuiSvgIcon-root").first
        if await search_button.count() > 0:
            await search_button.click()
        else:
            await page.keyboard.press("Enter")

    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Dict:
        """
        Scrapes property details from TCAD given an account number (PROP_ID).
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                logger.info(f"TCAD: Navigating to search for {account_number or address}")
                await page.goto(self.search_url, timeout=60000, wait_until="networkidle")
                await asyncio.sleep(3)  # Wait for React hydration

                search_val = account_number or address
                if not search_val:
                    raise ValueError("Must provide account_number or address")

                search_input = await self._get_search_input(page)
                await search_input.fill(search_val)
                await self._submit_search(page)

                # Smart wait: wait for result link or detail page
                try:
                    await page.wait_for_selector('[col-id="pid"] a, .property-detail', timeout=20000)
                except Exception:
                    logger.warning("TCAD: Timed out waiting for results")
                    return {}

                if "/property-detail/" not in page.url:
                    result_link = page.locator('[col-id="pid"] a').first
                    if await result_link.count() > 0:
                        logger.info("TCAD: Found result link in AG Grid, clicking...")
                        await result_link.click()
                        try:
                            await page.wait_for_url("**/property-detail/**", timeout=15000)
                        except: pass
                    else:
                        logger.warning("TCAD: No result link found")
                        return {}

                # 2. Extract Details
                details = {}
                details['account_number'] = account_number
                
                # Property Address — use semantic selectors, not brittle CSS classes
                body_text = await page.evaluate("() => document.body.innerText")
                
                # Try to find address from page title or header
                try:
                    # Look for "Situs Address" label pattern in the body text
                    addr_match = re.search(r"Situs Address\s*[\n\r]+\s*(.+?)[\n\r]", body_text)
                    if addr_match:
                        details['address'] = addr_match.group(1).strip()
                    else:
                        # Try the PID header pattern: "PID 12345 | 123 MAIN ST"
                        pid_match = re.search(r"PID\s+\d+\s*\|\s*(.+?)[\n\r]", body_text)
                        if pid_match:
                            details['address'] = pid_match.group(1).strip()
                        else:
                            # Last resort: try any visible h1/h2 text
                            header = page.locator("h1, h2").first
                            if await header.count() > 0:
                                header_text = await header.inner_text()
                                if "|" in header_text:
                                    details['address'] = header_text.split("|")[-1].strip()
                except Exception as e:
                    logger.warning(f"TCAD: Address extraction failed: {e}")

                # Market Value - Find all matches and pick the first non-zero one
                mkt_matches = re.finditer(r"Market\s*[\n\r]*\s*([\d,]+)", body_text)
                found_mkt = 0.0
                for match in mkt_matches:
                    val = self._parse_currency(match.group(1))
                    if val > 0:
                        found_mkt = val
                        break
                details['market_value'] = found_mkt
                
                app_matches = re.finditer(r"Appraised\s*[\n\r]*\s*([\d,]+)", body_text)
                found_app = 0.0
                for match in app_matches:
                    val = self._parse_currency(match.group(1))
                    if val > 0:
                        found_app = val
                        break
                details['appraised_value'] = found_app

                # Year Built
                yb_match = re.search(r"Year Built\s*[\n\r]*\s*(\d{4})", body_text)
                if yb_match:
                    details['year_built'] = int(yb_match.group(1))

                # Area - Multi-label robust extraction
                area_found = 0
                area_labels = ["Main Area", "Total Living Area", "Gross Area", "Building Area", "SQ FT", "Gross Building Area"]
                
                for label in area_labels:
                    match = re.search(f"{label}[:\\s]+([\\d,]+)", body_text, re.IGNORECASE)
                    if match:
                        val = self._parse_number(match.group(1))
                        if val > area_found: area_found = val
                
                details['building_area'] = area_found

                # Neighborhood
                nbhd_match = re.search(r"Neighborhood CD:?\s*[\n\r]*\s*([A-Z\d\.]+)", body_text)
                if not nbhd_match:
                    nbhd_match = re.search(r"Market Area CD:?\s*[\n\r]*\s*([A-Z\d\.]+)", body_text)
                
                if nbhd_match:
                    details['neighborhood_code'] = nbhd_match.group(1)

                details['district'] = "TCAD"
                
                return details

            except Exception as e:
                logger.error(f"TCAD: Error scraping details: {e}")
                return {}
            finally:
                await browser.close()

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Fetches neighbors by searching for the street name.
        Uses smart polling instead of fixed sleeps.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            neighbors = []
            try:
                await page.goto(self.search_url, timeout=60000)
                await asyncio.sleep(3)  # Wait for React hydration

                search_input = await self._get_search_input(page)
                await search_input.fill(street_name)
                await self._submit_search(page)

                # Smart wait for AG Grid rows
                try:
                    await page.wait_for_selector('.ag-row', timeout=20000)
                except Exception:
                    logger.warning(f"TCAD: Timed out waiting for street results for '{street_name}'")
                    return []

                rows = page.locator('.ag-row')
                count = await rows.count()
                limit = min(count, 50)
                
                for i in range(limit):
                    row = rows.nth(i)
                    try:
                        acc = await row.locator('[col-id="pid"]').inner_text()
                        addr = await row.locator('[col-id="address"]').inner_text()
                        val_str = await row.locator('[col-id="appraised_val"]').inner_text()
                        
                        neighbors.append({
                            "account_number": acc.strip(),
                            "address": addr.strip(),
                            "market_value": self._parse_currency(val_str),
                            "district": "TCAD"
                        })
                    except:
                        continue
                    
                logger.info(f"TCAD: Found {len(neighbors)} neighbors on '{street_name}'")
                return neighbors

            except Exception as e:
                logger.error(f"TCAD: Error fetching neighbors: {e}")
                return []
            finally:
                await browser.close()

    async def get_neighbors(self, neighborhood_code: str) -> List[Dict]:
        """
        Searches TCAD for all properties in a neighborhood code.
        ProdigyCad supports neighborhood code filtering in the search.
        """
        if self.is_commercial_neighborhood_code(neighborhood_code):
            logger.info(f"TCAD: Skipping neighborhood search for commercial code '{neighborhood_code}'")
            return []
        
        logger.info(f"TCAD: Searching for neighborhood code: {neighborhood_code}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            neighbors = []
            try:
                await page.goto(self.search_url, timeout=60000)
                await asyncio.sleep(3)

                search_input = await self._get_search_input(page)
                await search_input.fill(neighborhood_code)
                await self._submit_search(page)

                try:
                    await page.wait_for_selector('.ag-row', timeout=20000)
                except Exception:
                    logger.warning(f"TCAD: Timed out waiting for neighborhood results for '{neighborhood_code}'")
                    return []

                rows = page.locator('.ag-row')
                count = await rows.count()
                limit = min(count, 50)
                
                for i in range(limit):
                    row = rows.nth(i)
                    try:
                        acc = await row.locator('[col-id="pid"]').inner_text()
                        addr = await row.locator('[col-id="address"]').inner_text()
                        val_str = await row.locator('[col-id="appraised_val"]').inner_text()
                        
                        neighbors.append({
                            "account_number": acc.strip(),
                            "address": addr.strip(),
                            "market_value": self._parse_currency(val_str),
                            "district": "TCAD"
                        })
                    except:
                        continue
                
                logger.info(f"TCAD: Found {len(neighbors)} properties in neighborhood '{neighborhood_code}'")
                return neighbors

            except Exception as e:
                logger.error(f"TCAD: Error fetching neighborhood properties: {e}")
                return []
            finally:
                await browser.close()

    async def check_service_status(self) -> bool:
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
