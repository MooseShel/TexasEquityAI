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

    def __init__(self):
        self.base_url = "https://travis.prodigycad.com"
        self.search_url = f"{self.base_url}/property-search"

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
                # 1. Search Logic
                logger.info(f"Navigating to TCAD search for {account_number or address}")
                await page.goto(self.search_url, timeout=60000, wait_until="networkidle")
                await asyncio.sleep(5) # Wait for React

                search_val = account_number
                if not search_val and address:
                    search_val = address
                
                if not search_val:
                    raise ValueError("Must provide account_number or address")

                search_input = page.get_by_placeholder(re.compile(r"Search by Address, Owner Name, or Property ID", re.IGNORECASE))
                if await search_input.count() == 0:
                    search_input = page.locator("input[type='text']").first
                
                await search_input.fill(search_val)
                search_button = page.locator("button >> .MuiSvgIcon-root").first
                if await search_button.count() > 0:
                    await search_button.click()
                else:
                    await page.keyboard.press("Enter")

                await asyncio.sleep(5)

                if "/property-detail/" not in page.url:
                    result_link = page.locator('[col-id="pid"] a').first
                    if await result_link.count() > 0:
                        logger.info("Found result link in AG Grid, clicking...")
                        await result_link.click()
                        await asyncio.sleep(10)
                    else:
                        logger.warning("No result link found in TCAD results")
                        return {}

                # 2. Extract Details
                details = {}
                details['account_number'] = account_number
                
                # Property Address - Usually class .sc-bMJoCw.eiwhdn in Location section
                prop_addr = page.locator(".sc-bMJoCw.eiwhdn").first
                if await prop_addr.count() > 0:
                    details['address'] = (await prop_addr.inner_text()).strip()
                else:
                    header_span = page.locator("span:has-text('PID')").first
                    if await header_span.count() > 0:
                        text = await header_span.inner_text()
                        if "|" in text:
                            details['address'] = text.split("|")[-1].strip()

                # Values & More - Use Regex on full body text for robustness
                body_text = await page.evaluate("() => document.body.innerText")
                
                # Market Value - Find all matches and pick the first non-zero one
                # This prevents picking up 2026 $0 values if they appear first.
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
                area_labels = ["Main Area", "Total Living Area", "Gross Area", "Building Area", "SQ FT"]
                
                for label in area_labels:
                    # Match pattern: "Label: 1,234"
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
                logger.error(f"Error scraping TCAD details: {e}")
                return {}
            finally:
                await browser.close()

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Fetches neighbors by searching for the street name.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            neighbors = []
            try:
                await page.goto(self.search_url, timeout=60000)
                await asyncio.sleep(5)

                search_input = page.get_by_placeholder(re.compile(r"Search by Address, Owner Name, or Property ID", re.IGNORECASE))
                if await search_input.count() == 0:
                    search_input = page.locator("input[type='text']").first
                
                await search_input.fill(street_name)
                search_button = page.locator("button >> .MuiSvgIcon-root").first
                if await search_button.count() > 0:
                    await search_button.click()
                else:
                    await page.keyboard.press("Enter")

                await asyncio.sleep(5)

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
                    
                return neighbors

            except Exception as e:
                logger.error(f"Error fetching TCAD neighbors: {e}")
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

    def _parse_currency(self, val_str: str) -> float:
        try:
            clean = val_str.replace("$", "").replace(",", "").strip()
            if "N/A" in clean: return 0.0
            return float(clean)
        except:
            return 0.0

    def _parse_number(self, val_str: str) -> float:
        try:
            clean = val_str.replace(",", "").strip()
            return float(clean)
        except:
            return 0.0
