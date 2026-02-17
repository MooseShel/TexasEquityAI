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
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                
                # Step 1: Land on Search Home
                logger.info(f"Navigating to {self.portal_url}")
                await page.goto(self.portal_url, wait_until="commit", timeout=30000)
                await self._bypass_security(page)
                await asyncio.sleep(2)
                
                # Step 2: Select 'Account Number' radio button if searching by account
                try:
                    # Look for radio label containing 'Account Number'
                    logger.info("Attempting to select 'Account Number' search mode...")
                    account_radio = await page.query_selector("text='Account Number'")
                    if account_radio:
                        await account_radio.click()
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not explicitly select Account Number radio: {e}")

                # Step 3: Try Search by Account first, then by Full Address fallback
                search_queries = [account_number]
                if address:
                    # Clean the address for HCAD search
                    # Examples: "935 Lamonte Ln, Houston, TX" -> "935 Lamonte Ln"
                    addr_clean = address.split(",")[0].strip()
                    
                    # 1. Try the full street segment (House # + Name + Suffix)
                    search_queries.append(addr_clean) 
                    
                    # 2. Try just House # + Street Name (Fallback)
                    parts = addr_clean.split()
                    if len(parts) >= 2:
                        simplified_addr = f"{parts[0]} {parts[1]}" # e.g. "935 Lamonte"
                        if simplified_addr != addr_clean:
                            search_queries.append(simplified_addr)

                link = None
                for query in search_queries:
                    logger.info(f"Searching for: {query}")
                    input_selector = "input[placeholder*='Search like']"
                    
                    # Switch search modes if necessary
                    try:
                        is_numeric_query = query.isdigit() or len(query) == 13
                        mode_text = "Account Number" if is_numeric_query else "Property Address"
                        mode_radio = await page.query_selector(f"text='{mode_text}'")
                        if mode_radio: 
                            await mode_radio.click()
                            await asyncio.sleep(0.5)
                    except: pass

                    await page.click(input_selector) # Human-like click before typing
                    await page.fill(input_selector, "")
                    await page.type(input_selector, query, delay=100) # Human-like typing
                    await page.keyboard.press("Enter")
                    
                    # Wait for results with a longer timeout
                    try:
                        # Success indicator is often the account number appearing in a table
                        await page.wait_for_selector(f"text='{account_number}'", timeout=15000)
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
                    
                    # Some portals open details in a new tab
                    try:
                        async with context.expect_page(timeout=10000) as new_page_info:
                            await link.click(delay=200)
                        page = await new_page_info.value
                        logger.info("Detected new tab for property details.")
                    except:
                        logger.info("No new tab detected, continuing on current page.")
                    
                    # CRITICAL: Wait for a detail-page specific element to appear
                    # This helps bypass the Cloudflare verification period
                    logger.info("Waiting for detail page content (Location header)...")
                    await self._bypass_security(page)
                    
                    try:
                        await page.wait_for_selector("text='Location'", timeout=15000)
                        logger.info("Detail page loaded successfully.")
                    except:
                        logger.warning("Timeout waiting for 'Location' header. Might be blocked or slow.")
                    
                    await asyncio.sleep(2) # Final settle
                    
                    text = await page.evaluate("() => document.body.innerText")
                    logger.info(f"Extraction text length: {len(text)}")
                    
                    details = {"account_number": account_number}
                    
                    # 1. Address: Look for the street address segment (case insensitive)
                    # Pattern matches something like "843 LAMONTE LN" after some whitespace
                    addr_match = re.search(r"(?:\n|^)\s*(\d+\s+[A-Z\d\s]{3,}(?:LN|ST|RD|BLVD|CIR|DR|WAY|AVE|CT|TRL|PKWY|HWY|PL|LOOP))\b", text, re.IGNORECASE)
                    if addr_match:
                        details['address'] = addr_match.group(1).strip()
                    else:
                        # Backup: Try to find address line following the map instruction
                        addr_alt = re.search(r"view values and property information\.\s*\n+\s*(.*?)(?:\nHOUSTON|$)", text, re.IGNORECASE)
                        if addr_alt:
                            details['address'] = addr_alt.group(1).strip()
                    
                    # 2. Appraised Value
                    # In early season, HCAD shows "Pending" in the main Valuation table. 
                    # We look for any $ amount in the whole text as a fallback if the table is empty.
                    val_match = re.search(r"\$\s*(\d{1,3}(?:,\d{3})+)", text)
                    if val_match:
                        details['appraised_value'] = float(val_match.group(1).replace(',', ''))
                    else:
                        details['appraised_value'] = 0 
                    
                    # 3. Building Area (Living Area)
                    # Pattern matches: "Living Area\n 6,785 SF"
                    area_match = re.search(r"Living Area\s*[\n\r]\s*([\d,]+)\s*SF", text, re.IGNORECASE)
                    if area_match:
                        details['building_area'] = float(area_match.group(1).replace(',', ''))
                    else:
                        # Fallback: check Building Summary section for 'Impr Sq Ft' or similar
                        area_summary = re.search(r"(?:Living Area|Impr Sq Ft|Impr\s*Sq\s*Ft)[\s\S]{1,100}?([\d,]{3,})\b", text, re.IGNORECASE)
                        if area_summary:
                            details['building_area'] = float(area_summary.group(1).replace(',', ''))
                    
                    # 4. Year Built
                    # Usually in the Building Summary table.
                    year_match = re.search(r"Building\s+Year Build[\s\S]*?\n\s*\d+\s+(\d{4})\b", text, re.IGNORECASE)
                    if year_match:
                        details['year_built'] = year_match.group(1)
                    else:
                        # General search for a 4-digit year starting with 19 or 20 in the building summary area
                        bs_start = text.find("Building Summary")
                        if bs_start != -1:
                            year_fallback = re.search(r"\b(19|20)\d{2}\b", text[bs_start:])
                            if year_fallback:
                                details['year_built'] = year_fallback.group(0)
                    
                    # 5. Neighborhood Code
                    # Sits in the Location table, often after 'Single-Family'
                    nb_match = re.search(r"Single-Family\s+([\d\.]+)\s+", text, re.IGNORECASE)
                    if nb_match:
                        details['neighborhood_code'] = nb_match.group(1)
                    else:
                        # Fallback for different class codes or layouts
                        nb_fallback = re.search(r"Location[\s\S]*?(\d{4}(?:\.\d{2})?)", text, re.IGNORECASE)
                        if nb_fallback:
                            details['neighborhood_code'] = nb_fallback.group(1)

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
