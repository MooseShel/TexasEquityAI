import asyncio
import logging
import re
from typing import Dict, List, Optional
from playwright.async_api import async_playwright
from .base_connector import AppraisalDistrictConnector

logger = logging.getLogger(__name__)

class DCADConnector(AppraisalDistrictConnector):
    """
    Connector for Dallas Central Appraisal District (DCAD).
    DCAD uses a custom ASP.NET portal at dallascad.org.
    """

    def __init__(self):
        self.base_url = "https://www.dallascad.org"
        self.search_url = f"{self.base_url}/SearchAcct.aspx"

    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Dict:
        """
        Scrapes property details from DCAD given an account number.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. Search Logic
                logger.info(f"Navigating to DCAD search for {account_number or address}")
                if account_number:
                    await page.goto(f"{self.base_url}/SearchAcct.aspx", timeout=60000)
                    # Correct selector from explore: #txtAccountNumber
                    account_input = page.locator("#txtAccountNumber")
                    if await account_input.count() > 0:
                        await account_input.fill(account_number)
                        await page.click("#cmdSubmit")
                    else:
                        # Fallback for different page version
                        await page.fill("#txtAcctNum", account_number)
                        await page.click("#Button1")
                elif address:
                    await page.goto(f"{self.base_url}/SearchAddr.aspx", timeout=60000)
                    await page.locator("#txtStreetName").fill(address.split()[-1])
                    await page.click("#cmdSubmit")
                else:
                    return {}

                await asyncio.sleep(5)

                # Click result link
                if "AcctDetail" not in page.url:
                    result_link = page.locator("a[href*='AcctDetail']").first
                    if await result_link.count() > 0:
                        await result_link.click()
                        await asyncio.sleep(5)
                    else:
                        logger.warning(f"No result found for DCAD: {account_number}")
                        return {}

                # 2. Extract Details
                details = {}
                details['account_number'] = account_number
                
                # Use Location Address label
                addr_locator = page.locator("#PropAddr1_lblPropAddr")
                if await addr_locator.count() > 0:
                    details['address'] = (await addr_locator.inner_text()).strip()
                
                # Market Value
                mkt_val_locator = page.locator("#ValueSummary1_pnlValue_lblTotalVal")
                if await mkt_val_locator.count() > 0:
                    details['market_value'] = self._parse_currency(await mkt_val_locator.inner_text())
                
                details['appraised_value'] = details.get('market_value', 0.0)

                # Year Built & Area
                body_text = await page.evaluate("() => document.body.innerText")
                yb_match = re.search(r"Year Built:\s*(\d{4})", body_text)
                if yb_match:
                    details['year_built'] = int(yb_match.group(1))
                
                area_match = re.search(r"Total Area:\s*([\d,]+)", body_text)
                if area_match:
                    details['building_area'] = self._parse_number(area_match.group(1))

                # Neighborhood
                nbhd_locator = page.locator("#lblNbhd")
                if await nbhd_locator.count() > 0:
                    details['neighborhood_code'] = (await nbhd_locator.inner_text()).strip()

                details['district'] = "DCAD"
                
                return details

            except Exception as e:
                logger.error(f"Error scraping DCAD details: {e}")
                return {}
            finally:
                await browser.close()

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        DCAD street search returns a list.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            neighbors = []
            try:
                await page.goto(f"{self.base_url}/SearchAddr.aspx")
                await page.locator("#txtStreetName").fill(street_name)
                await page.click("#cmdSubmit")
                await asyncio.sleep(5)
                
                rows = page.locator("#SearchResults1_dgResults tr").skip(2)
                count = await rows.count()
                for i in range(min(count - 1, 50)):
                    row = rows.nth(i)
                    cols = row.locator("td")
                    if await cols.count() >= 5:
                        href = await cols.nth(1).locator("a").get_attribute("href")
                        acc_id = href.split("ID=")[-1] if href else ""
                        addr = await cols.nth(1).inner_text()
                        val_str = await cols.nth(4).inner_text()
                        
                        neighbors.append({
                            "account_number": acc_id.strip(),
                            "address": addr.strip(),
                            "market_value": self._parse_currency(val_str),
                            "district": "DCAD"
                        })
                return neighbors
            except Exception as e:
                logger.error(f"Error fetching DCAD neighbors: {e}")
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
            except:
                return False

    def _parse_currency(self, val_str: str) -> float:
        try:
            clean = val_str.replace("$", "").replace(",", "").strip()
            if clean == "N/A" or not clean: return 0.0
            return float(clean)
        except:
            return 0.0

    def _parse_number(self, val_str: str) -> float:
        try:
            clean = val_str.replace(",", "").strip()
            return float(clean)
        except:
            return 0.0
