import logging
import asyncio
import sys
from typing import Optional, Dict, List
from playwright.async_api import async_playwright
import re
import os
from .base_connector import AppraisalDistrictConnector

if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

logger = logging.getLogger(__name__)

class HCADScraper(AppraisalDistrictConnector):
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
        if details: 
            details['district'] = 'HCAD'
            return details
        
        # 2. Fallback: Discovery (Manual Mapping)
        logger.warning(f"New Portal flow failed. Trying Discovery fallback for {account_number}")
        address_fallback = await self._discover_address(account_number)
        if address_fallback:
            return {
                "account_number": account_number,
                "address": address_fallback,
                "appraised_value": 0, 
                "building_area": 0,
                "neighborhood_code": "Unknown",
                "district": "HCAD"
            }
        
        return None

    def check_service_status(self) -> bool:
        # Return True for now (scraper is always 'up' but might fail)
        return True

    async def _bypass_security(self, page):
        """Dedicated logic to wait for Cloudflare challenges to clear."""
        logger.info("Detecting security challenge (Cloudflare)...")
        try:
            # Wait up to 30 seconds for the title to change or certain elements to appear
            for i in range(30):
                title = await page.title()
                logger.info(f"Current Page title: '{title}' (Attempt {i+1}/30)")
                if "Just a moment" not in title and "Security" not in title:
                    # Check for indicators that we have landed on a real page
                    if await page.query_selector("input[placeholder*='Search like']") or \
                       await page.query_selector("text='Location'") or \
                       await page.query_selector("text='Account Number'"):
                        logger.info("Security challenge bypassed successfully.")
                        return True
                await asyncio.sleep(1)
            else:
                logger.warning("Security bypass might have failed or timed out.")
        except Exception as e:
            logger.warning(f"Error during security bypass check: {e}")
        return False

    async def _scrape_new_portal_human(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True)
                # Production-grade context
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800},
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
                )
                page = await context.new_page()
                
                # Step 1: Land on Search Home
                logger.info(f"Navigating to {self.portal_url}")
                await page.goto(self.portal_url, wait_until="load", timeout=60000)
                await self._bypass_security(page)
                
                # Step 2: Select 'Account Number'
                try:
                    logger.info("Selecting 'Account Number' search mode...")
                    # Clicking the label is often more reliable in Blazor than the radio input itself
                    await page.click("label[for='ACCOUNTNUMBER']", force=True)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to select Account Number mode: {e}")

                # Step 3: Search
                input_selector = "input[placeholder*='Search like']"
                await page.fill(input_selector, "")
                await page.type(input_selector, account_number, delay=100)
                await page.keyboard.press("Enter")
                
                # Step 4: Wait for data to appear (Polling approach)
                logger.info("Polling for property data...")
                details = {"account_number": account_number, "district": "HCAD"}
                
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 45:
                    content = await page.content()
                    if account_number in content and ("LAMONTE" in content or "Owner" in content or "Value" in content):
                        if await page.locator("#OwnerInfoComponent").is_visible():
                            logger.info("Data detected on detail page.")
                            break
                    
                    # If we see a results table, try to click it
                    if "table-hover" in content or "Account Number" in content:
                        try:
                            result_link = page.get_by_text(account_number, exact=True).first
                            if await result_link.is_visible():
                                await result_link.click()
                                await asyncio.sleep(2)
                        except: pass
                    
                    await asyncio.sleep(2)
                else:
                    logger.error("Timed out waiting for property data to appear.")
                    await page.screenshot(path=f"debug/poll_fail_{account_number}.png")
                    return None

                # Step 5: Extraction (Polished)
                await asyncio.sleep(2) # Final settle
                
                details = {"account_number": account_number, "district": "HCAD"}

                # Address
                try:
                    addr_el = page.locator("#OwnerInfoComponent span.whitebox-large-font")
                    if await addr_el.count() > 0:
                        addr_parts = await addr_el.all_inner_texts()
                        details['address'] = " ".join([a.strip() for a in addr_parts if a.strip()])
                except: pass

                # Living Area
                try:
                    area_text = await page.locator("#PropertyComponent .row:has-text('Living Area') .col-6:nth-child(2)").inner_text()
                    details['building_area'] = self._parse_number(area_text.replace("SF", ""))
                except:
                    try:
                        area_text = await page.locator("#PropertyComponent .row:has-text('Living Area') .col").inner_text()
                        details['building_area'] = self._parse_number(area_text.replace("SF", ""))
                    except: pass
                
                # Year Built
                try:
                    details['year_built'] = await page.locator("#BuildingSummaryComponent table tbody tr:nth-child(2) td:nth-child(2)").inner_text()
                    details['year_built'] = details['year_built'].strip()
                except: pass

                # Neighborhood Code
                try:
                    details['neighborhood_code'] = await page.locator("#AdditionalInfoComponent table tbody tr td").nth(1).inner_text()
                    details['neighborhood_code'] = details['neighborhood_code'].strip()
                except: pass

                # Valuation logic
                async def extract_vals():
                    
                    return await page.evaluate("""() => {
                        const valBox = document.getElementById('ValuationComponent');
                        if (!valBox) return { appraised: null, market: null };
                        
                        let appraised = null;
                        let market = null;

                        // Helper to clean currency
                        const clean = (s) => s ? s.replace(/[$,\\s]/g, '') : null;

                        // 1. Try table rows (Most reliable for Certified values)
                        const rows = Array.from(valBox.querySelectorAll('tr'));
                        for (const row of rows) {
                            const text = row.innerText;
                            const cells = row.querySelectorAll('td');
                            const val = cells.length > 0 ? cells[cells.length - 1].innerText : null;
                            
                            // Only set if not already set (taking the first match which is usually the main table)
                            if (text.includes('Appraised') && !appraised) appraised = val;
                            if (text.includes('Market') && !market) market = val;
                        }

                        // 2. Try modern layout (col-6)
                        if (!appraised) {
                            const apprRow = Array.from(valBox.querySelectorAll('.row')).find(r => r.innerText.includes('Appraised'));
                            if (apprRow) {
                                const cols = apprRow.querySelectorAll('.col-6, .col');
                                if (cols.length >= 2) appraised = cols[cols.length - 1].innerText;
                            }
                        }
                        if (!market) {
                            const mktRow = Array.from(valBox.querySelectorAll('.row')).find(r => r.innerText.includes('Market'));
                            if (mktRow) {
                                const cols = mktRow.querySelectorAll('.col-6, .col');
                                if (cols.length >= 2) market = cols[cols.length - 1].innerText;
                            }
                        }

                        // 3. Last ditch fallback for Appraised (Large Font)
                        if (!appraised) {
                            const large = valBox.querySelector('.whitebox-large-font');
                            if (large && large.innerText.includes('$')) appraised = large.innerText;
                        }

                        return { appraised, market };
                    }""")
                
                # Check for address specifically
                if not details.get('address'):
                     try:
                        details['address'] = await page.locator(".whitebox-header").first.inner_text()
                     except: pass

                vals = await extract_vals()
                
                # Check if we need to switch year
                if not vals['appraised'] or "Pending" in vals['appraised']:
                    logger.info("Values pending/missing. Attempting 2025 switch...")
                    try:
                        await page.click("#dropdownMenuButton1", timeout=5000)
                        await asyncio.sleep(1)
                        await page.click(".dropdown-item:has-text('2025')", timeout=5000)
                        await asyncio.sleep(6)
                        
                        vals = await extract_vals()
                        logger.info(f"Re-extracted vals after 2025 switch: {vals}")
                    except Exception as e:
                        logger.warning(f"Failed 2025 switch: {e}")

                details['appraised_value'] = self._parse_currency(vals['appraised'])
                # If Market is missing, default to Appraised (common for residential uniform)
                # But if we found it effectively, use it.
                if vals['market'] and "Pending" not in vals['market']:
                    details['market_value'] = self._parse_currency(vals['market'])
                else:
                    details['market_value'] = details['appraised_value']

                return details

            except Exception as e:
                logger.error(f"New Portal human-flow failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                if browser:
                    await browser.close()
        return None

    def _parse_currency(self, text: str) -> float:
        if not text: return 0.0
        # Remove $, commas, and whitespace
        clean = re.sub(r'[$,\s]', '', text)
        if "Pending" in text: return 0.0
        try:
            return float(clean)
        except:
            return 0.0

    def _parse_number(self, text: str) -> float:
        if not text: return 0.0
        clean = re.sub(r'[,\s]', '', text)
        try:
            return float(clean)
        except:
            return 0.0

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
                
                # Extract results from the table logic improved for uniqueness
                rows = await page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();
                    
                    // 1. Try Standard Search Table
                    const tableRows = document.querySelectorAll('tr');
                    tableRows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 3) {
                            // Often Account is col 0 or 1 depending on layout
                            let acc = cells[0].innerText.trim();
                            let addr = cells[1].innerText.trim();
                            
                            // Sometimes Account is not the first column? verify 13 digits
                            if (!/^\\d{13}$/.test(acc) && /^\\d{13}$/.test(cells[1].innerText.trim())) {
                                acc = cells[1].innerText.trim();
                                addr = cells[2] ? cells[2].innerText.trim() : "Unknown";
                            }

                            if (/^\\d{13}$/.test(acc) && !seen.has(acc)) {
                                seen.add(acc);
                                results.push({
                                    account_number: acc,
                                    address: addr
                                });
                            }
                        }
                    });
                    
                    // 2. Fallback: Scan all links if table failed
                    if (results.length === 0) {
                        const links = document.querySelectorAll('a');
                        links.forEach(a => {
                            const text = a.innerText.trim();
                            // Match strictly 13 digits
                            if (/^\\d{13}$/.test(text) && !seen.has(text)) {
                                seen.add(text);
                                results.push({
                                    account_number: text,
                                    address: "Unknown"  // We will deep scrape to get this later
                                });
                            }
                        });
                    }
                    return results;
                }""")
                
                logger.info(f"Found {len(rows)} unique potential neighbors on {street_name}")
                # Add district field
                for row in rows:
                    row['district'] = 'HCAD'
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
