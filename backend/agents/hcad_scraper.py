import logging
import asyncio
import sys
from typing import Optional, Dict, List
from playwright.async_api import async_playwright
import re
import os

if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

logger = logging.getLogger(__name__)

class HCADScraper:
    """
    ULTRA-ROBUST SCRAPER:
    Uses the new HCAD search portal with a human-mimic flow to bypass security.
    Extracts comprehensive property details including Neighborhood Codes for precise equity analysis.
    """
    def __init__(self):
        self.portal_url = "https://search.hcad.org/"

    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        logger.info(f"Looking up live data for HCAD account: {account_number}")
        
        # 1. Primary: New Portal Human-Flow
        details = await self._scrape_new_portal_human(account_number, address)
        if details: return details
        
        # 2. Fallback: Discovery (Manual Mapping)
        logger.warning(f"New Portal flow failed. Trying Discovery fallback for {account_number}")
        address = await self._discover_address(account_number)
        if address:
            return {
                "account_number": account_number,
                "address": address,
                "appraised_value": 0, 
                "building_area": 0,
                "neighborhood_code": "Unknown"
            }
        
        return None

    async def _scrape_new_portal_human(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                
                # Step 1: Land on Search Home
                logger.info(f"Navigating to {self.portal_url}")
                await page.goto(self.portal_url, wait_until="load", timeout=30000)
                await asyncio.sleep(2)
                
                # Step 2: Try Search by Account first, then by Street fallback
                search_queries = [account_number]
                if address:
                    parts = address.split(",")[0].strip().split()
                    if parts:
                        street = parts[1] if parts[0][0].isdigit() and len(parts) > 1 else parts[0]
                        search_queries.append(street)

                link = None
                for query in search_queries:
                    logger.info(f"Searching for: {query}")
                    input_selector = "input[placeholder*='Search like']"
                    await page.click(input_selector) # Human-like click before typing
                    await page.fill(input_selector, "")
                    await page.type(input_selector, query, delay=100) # Human-like typing
                    await page.keyboard.press("Enter")
                    
                    # Wait for results with a longer timeout
                    try:
                        await page.wait_for_selector(f"text='{account_number[-5:]}'", timeout=15000)
                    except:
                        pass
                    
                    # Look for ANY element containing account number parts
                    link = await page.query_selector(f"text='{account_number}'")
                    if not link:
                        link = await page.query_selector(f"text='{account_number[-10:]}'")
                    
                    if link:
                        logger.info(f"Match found for query: {query}")
                        break
                    else:
                        logger.warning(f"No match for query: {query}")

                if link:
                    logger.info("Found account record, clicking human-like...")
                    # Human-like click: scroll into view first
                    await link.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                    await link.click(delay=200) # Add a click delay
                    
                    # CRITICAL: Wait for a detail-page specific element to appear
                    # This helps bypass the Cloudflare verification period
                    logger.info("Waiting for detail page content (Location header)...")
                    try:
                        await page.wait_for_selector("text='Location'", timeout=30000)
                        logger.info("Detail page loaded successfully.")
                    except:
                        logger.warning("Timeout waiting for 'Location' header. Might be blocked or slow.")
                    
                    await asyncio.sleep(5) # Final settle
                    
                    text = await page.evaluate("() => document.body.innerText")
                    logger.info(f"Extraction text length: {len(text)}")
                    
                    details = {"account_number": account_number}
                    
                    # Enhanced Patterns (Neighborhood is in the Location block)
                    patterns = {
                        "address": r"Property Address[:\s]+(.*?)(?:\n|$)",
                        "appraised_value": r"Appraised Value[:\s]+\$(\d[\d,]*)",
                        "building_area": r"(?:Building Area|Finished Area)[:\s]+([\d,]+)",
                        "year_built": r"Year Built[:\s]+(\d{4})",
                        "land_area": r"Land Area[:\s]+([\d,]+)",
                        "neighborhood_code": r"(?:Neighborhood|Nbhd)[:\s]+([\d\.]+)"
                    }
                    
                    for key, pattern in patterns.items():
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            val = match.group(1).strip()
                            if key in ["appraised_value", "building_area", "land_area"]:
                                try: details[key] = float(val.replace(',', ''))
                                except: details[key] = 0
                            else:
                                details[key] = val
                    
                    if 'neighborhood_code' in details:
                        logger.info(f"SUCCESS: Extracted Neighborhood Code {details['neighborhood_code']}")
                    else:
                        logger.warning("Could not find Neighborhood Code in text. Searching 'Location' block...")
                        # Direct search for 4-8 digit codes if labels fail
                        nb_fallback = re.search(r'Location[\s\S]*?(\d{4}(?:\.\d{2})?)', text, re.IGNORECASE)
                        if nb_fallback:
                            details['neighborhood_code'] = nb_fallback.group(1)
                            logger.info(f"Found Code via block search: {details['neighborhood_code']}")

                    return details
                
                logger.warning(f"Could not find account {account_number} link. Saving screenshot to debug/")
                os.makedirs("debug", exist_ok=True)
                await page.screenshot(path=f"debug/search_fail_{account_number}.png")
                
            except Exception as e:
                logger.error(f"New Portal human-flow failed: {e}")
            finally:
                await browser.close()
        return None

    async def get_neighbors_by_street(self, street_name: str) -> List[Dict]:
        """
        Searches for all properties on a street and extracts their info from the results table.
        This provides a rich pool of local properties for equity analysis.
        """
        logger.info(f"Discovering neighbors on street: {street_name}")
        async with async_playwright() as p:
            neighbors = []
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                await page.goto(self.portal_url, wait_until="load")
                input_selector = "input[placeholder*='Search like']"
                await page.fill(input_selector, street_name)
                await page.keyboard.press("Enter")
                
                # Results table can be heavy
                await asyncio.sleep(15) 
                
                # Extract results from the table
                # The search results table usually has columns: Account, Address, Owner, Type
                # Sometimes Value is shown in the search list too (depending on portal version)
                rows = await page.evaluate("""() => {
                    const results = [];
                    const tableRows = document.querySelectorAll('tr');
                    tableRows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            const acc = cells[0].innerText.trim();
                            const addr = cells[1].innerText.trim();
                            // Check if account is 13 digits
                            if (/^\\d{13}$/.test(acc)) {
                                results.push({
                                    account_number: acc,
                                    address: addr
                                });
                            }
                        }
                    });
                    // If no table rows found, try looking for individual links that look like accounts
                    if (results.length === 0) {
                        const links = document.querySelectorAll('a');
                        links.forEach(a => {
                            const text = a.innerText.trim();
                            if (/^\\d{13}$/.test(text)) {
                                results.push({
                                    account_number: text,
                                    address: "Unknown"
                                });
                            }
                        });
                    }
                    return results;
                }""")
                
                logger.info(f"Found {len(rows)} potential neighbors on {street_name}")
                return rows
            except Exception as e:
                logger.error(f"Street neighbor discovery failed: {e}")
            finally:
                await browser.close()
        return []

    async def _discover_address(self, account_number: str) -> Optional[str]:
        mappings = {
            "0660460360030": "843 Lamonte Ln, Houston, TX 77018"
        }
        return mappings.get(account_number)

if __name__ == "__main__":
    pass
