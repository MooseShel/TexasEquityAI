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
    DISTRICT_NAME = "DCAD"

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

            for attempt in range(2):  # Retry once on transient failures
              try:
                # 1. Search Logic
                logger.info(f"DCAD: Navigating to search for {account_number or address} (attempt {attempt+1})")
                if account_number:
                    await page.goto(f"{self.base_url}/SearchAcct.aspx", timeout=60000, wait_until="domcontentloaded")
                    # Wait for the form input to be visible before interacting
                    try:
                        await page.wait_for_selector("#txtAccountNumber, #txtAcctNum", timeout=15000)
                    except:
                        logger.warning("DCAD: Account input not found after page load.")
                        if attempt < 1: continue
                        return {}

                    account_input = page.locator("#txtAccountNumber")
                    try:
                        if await account_input.count() > 0:
                            await account_input.fill(account_number)
                            await page.click("#cmdSubmit")
                        else:
                            fallback_input = page.locator("#txtAcctNum")
                            if await fallback_input.count() > 0:
                                await fallback_input.fill(account_number)
                                await page.click("#Button1")
                            else:
                                logger.warning("DCAD Account Input not found.")
                                return {}
                    except Exception as e:
                        logger.warning(f"DCAD Input Interaction Failed: {e}")
                        if attempt < 1: continue
                        return {}
                elif address:
                    await page.goto(f"{self.base_url}/SearchAddr.aspx", timeout=60000, wait_until="domcontentloaded")
                    await page.wait_for_selector("#txtStreetName", timeout=10000)
                    await page.locator("#txtStreetName").fill(address.split()[-1])
                    await page.click("#cmdSubmit")
                else:
                    return {}

                # Smart wait: wait for result link or detail page
                try:
                    await page.wait_for_selector("a[href*='AcctDetail'], #PropAddr1_lblPropAddr", timeout=25000)
                except Exception:
                    logger.warning("DCAD: Timed out waiting for results.")
                    if attempt < 1: continue
                    return {}

                # Click result link if on list page
                if "AcctDetail" not in page.url:
                    result_link = page.locator("a[href*='AcctDetail']").first
                    if await result_link.count() > 0:
                        await result_link.click()
                        try:
                            await page.wait_for_selector("#PropAddr1_lblPropAddr", timeout=20000)
                        except: pass
                    else:
                        logger.warning(f"DCAD: No result found for {account_number}")
                        return {}

                # 2. Extract Details
                details = {}
                details['account_number'] = account_number
                
                # Address
                addr_locator = page.locator("#PropAddr1_lblPropAddr")
                if await addr_locator.count() > 0:
                    details['address'] = (await addr_locator.inner_text()).strip()
                
                # Market Value - Try summary label first
                mkt_val = 0.0
                mkt_val_locator = page.locator("#ValueSummary1_pnlValue_lblTotalVal")
                if await mkt_val_locator.count() > 0:
                    mkt_val = self._parse_currency(await mkt_val_locator.inner_text())
                
                # FALLBACK: If summary is 0, check for table rows containing 2025/2024
                if mkt_val == 0.0:
                    logger.info("DCAD: Summary Value is 0. Searching for historical rows...")
                    for target_year in ["2025", "2024", "2023"]:
                        year_row = page.locator(f"tr:has-text('{target_year}')").first
                        if await year_row.count() > 0:
                            tds = year_row.locator("td")
                            td_count = await tds.count()
                            if td_count >= 4:
                                for j in range(td_count - 1, 1, -1):
                                    cell_text = await tds.nth(j).inner_text()
                                    h_val = self._parse_currency(cell_text)
                                    if h_val > 500:
                                        logger.info(f"DCAD: Found historical value for {target_year}: {h_val}")
                                        mkt_val = h_val
                                        break
                            if mkt_val > 0: break
                
                # FINAL FALLBACK: Regex on body text
                if mkt_val == 0.0:
                    logger.info("DCAD: DOM/Table search failed. Trying regex on body text...")
                    body_text = await page.evaluate("() => document.body.innerText")
                    regex_patterns = [
                        r"(?:Total|Market)\s+Value[:\s]*\$([\d,]+)",
                        r"Total\s+Appraised\s+Value[:\s]*\$([\d,]+)"
                    ]
                    for pattern in regex_patterns:
                        match = re.search(pattern, body_text)
                        if match:
                            mkt_val = self._parse_currency(match.group(1))
                            if mkt_val > 0:
                                logger.info(f"DCAD: Picked value via Regex: {mkt_val}")
                                break

                details['market_value'] = mkt_val
                details['appraised_value'] = mkt_val 

                # Year Built & Area - Robust Extraction
                body_text = await page.evaluate("() => document.body.innerText")
                
                # Year Built
                yb_match = re.search(r"Year Built:\s*(\d{4})", body_text)
                if yb_match:
                    details['year_built'] = int(yb_match.group(1))
                
                # Building Area - Multi-label fallback
                area_found = 0
                area_labels = ["Total Area", "Building Area", "Net Area", "Gross Area", "Living Area", "Gross Building Area"]
                
                for label in area_labels:
                    match = re.search(f"{label}[:\\s]+([\\d,]+)", body_text, re.IGNORECASE)
                    if match:
                        val = self._parse_number(match.group(1))
                        if val > area_found: area_found = val
                
                details['building_area'] = area_found

                # Neighborhood
                nbhd_locator = page.locator("#lblNbhd")
                if await nbhd_locator.count() > 0:
                    details['neighborhood_code'] = (await nbhd_locator.inner_text()).strip()

                details['district'] = "DCAD"
                
                return details

              except Exception as e:
                logger.error(f"DCAD: Error scraping details (attempt {attempt+1}): {e}")
                if attempt < 1:
                    logger.info("DCAD: Retrying...")
                    await asyncio.sleep(2)
                    continue
                return {}
            
            await browser.close()
            return {}

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        DCAD street search returns a list of neighbors.
        Uses smart polling instead of fixed sleeps.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            neighbors = []
            try:
                await page.goto(f"{self.base_url}/SearchAddr.aspx", timeout=60000, wait_until="domcontentloaded")
                try:
                    await page.wait_for_selector("#txtStreetName, input[type='text']", timeout=15000)
                except: pass
                
                street_input = page.locator("#txtStreetName")
                inputs = page.locator("input[type='text']")
                
                if await street_input.count() > 0:
                    await street_input.fill(street_name)
                    await page.click("#cmdSubmit")
                elif await inputs.count() > 0:
                    await inputs.last.fill(street_name)
                    await page.keyboard.press('Enter')
                else:
                    return []
                
                # Smart wait for results
                try:
                    await page.wait_for_selector("#SearchResults1_dgResults tr", timeout=20000)
                except Exception:
                    logger.warning(f"DCAD: Timed out waiting for street results for '{street_name}'")
                    return []
                
                rows = page.locator("#SearchResults1_dgResults tr")
                count = await rows.count()
                
                # Skip first 2 rows (headers)
                for i in range(2, min(count, 52)):
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
                logger.error(f"DCAD: Error fetching neighbors: {e}")
                return []
            finally:
                await browser.close()

    async def get_neighbors(self, neighborhood_code: str) -> List[Dict]:
        """
        Searches DCAD for all properties in a neighborhood code.
        DCAD has a neighborhood search at /SearchNbhd.aspx.
        """
        if self.is_commercial_neighborhood_code(neighborhood_code):
            logger.info(f"DCAD: Skipping neighborhood search for commercial code '{neighborhood_code}'")
            return []
        
        logger.info(f"DCAD: Searching for neighborhood code: {neighborhood_code}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            neighbors = []
            try:
                await page.goto(f"{self.base_url}/SearchNbhd.aspx", timeout=60000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except: pass
                
                # Try to find neighborhood code input
                nbhd_input = page.locator("#txtNbhd, #txtNeighborhood, input[type='text']").first
                if await nbhd_input.count() > 0:
                    await nbhd_input.fill(neighborhood_code)
                    submit = page.locator("#cmdSubmit, input[type='submit']").first
                    if await submit.count() > 0:
                        await submit.click()
                    else:
                        await page.keyboard.press("Enter")
                else:
                    logger.warning("DCAD: Could not find neighborhood search input")
                    return []
                
                try:
                    await page.wait_for_selector("#SearchResults1_dgResults tr", timeout=20000)
                except Exception:
                    logger.warning(f"DCAD: Timed out waiting for neighborhood results for '{neighborhood_code}'")
                    return []
                
                rows = page.locator("#SearchResults1_dgResults tr")
                count = await rows.count()
                
                for i in range(2, min(count, 52)):
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
                
                logger.info(f"DCAD: Found {len(neighbors)} properties in neighborhood '{neighborhood_code}'")
                return neighbors
            except Exception as e:
                logger.error(f"DCAD: Error fetching neighborhood properties: {e}")
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
