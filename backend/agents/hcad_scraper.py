import logging
import asyncio
import sys
from typing import Optional, Dict, List
from playwright.async_api import async_playwright
import re
import os
from .base_connector import AppraisalDistrictConnector

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

logger = logging.getLogger(__name__)

async def _launch_browser(p):
    """Launch Chromium with robust stealth flags to bypass Cloudflare."""
    kwargs = dict(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--hide-scrollbars",
            "--mute-audio",
            "--disable-extensions",
            "--disable-infobars",
            "--window-size=1920,1080",
        ],
        ignore_default_args=["--enable-automation"]
    )
    if sys.platform == 'win32':
        kwargs['handle_sigint'] = False
    return await p.chromium.launch(**kwargs)

class HCADScraper(AppraisalDistrictConnector):
    """
    ULTRA-ROBUST SCRAPER for Harris County Appraisal District (HCAD).
    Uses the new HCAD search portal with a human-mimic flow to bypass security.
    Extracts comprehensive property details including Neighborhood Codes for precise equity analysis.
    """
    DISTRICT_NAME = "HCAD"

    def __init__(self):
        self.portal_url = "https://search.hcad.org/"

    async def get_property_details(self, account_number: str, address: Optional[str] = None) -> Optional[Dict]:
        logger.info(f"Looking up live data for HCAD account: {account_number}")

        # 0. Supabase bulk-data lookup (fastest — no browser needed, works on cloud)
        #    Populated by scripts/hcad_bulk_import.py from HCAD's annual data files.
        try:
            from backend.db.supabase_client import supabase_service
            cached = await supabase_service.get_property_by_account(account_number)
            if cached and cached.get('address') and cached.get('district') == 'HCAD':
                # Only trust this cache if it has real scraped fields — not a ghost/placeholder record
                has_real_value = cached.get('appraised_value') and cached.get('appraised_value') not in (450000, 0)
                has_real_area  = cached.get('building_area') and cached.get('building_area') != 2500
                has_year       = bool(cached.get('year_built'))
                has_nbhd       = bool(cached.get('neighborhood_code'))
                if has_real_value or has_year or has_nbhd or has_real_area:
                    # Cache freshness: if key enrichment fields are missing, force re-scrape to self-heal
                    missing_fields = []
                    if not cached.get('year_built'): missing_fields.append('year_built')
                    if not cached.get('building_grade'): missing_fields.append('building_grade')
                    if not cached.get('land_area'): missing_fields.append('land_area')
                    if missing_fields and (has_real_value or has_real_area):
                        logger.info(f"HCAD: Cache hit but missing {missing_fields} — forcing re-scrape to enrich.")
                    else:
                        logger.info(f"HCAD: Returning bulk-data record for {account_number} (no scraping needed).")
                        return cached
                else:
                    logger.warning(f"HCAD: Supabase record for {account_number} looks like a ghost/placeholder (appraised={cached.get('appraised_value')}, year={cached.get('year_built')}) — skipping cache, forcing scrape.")
        except Exception as e:
            logger.warning(f"HCAD: Supabase bulk lookup failed: {e}")

        # 1. Primary: New Portal Human-Flow (works locally, blocked by Cloudflare on cloud)
        details = await self._scrape_new_portal_human(account_number, address)
        if details:
            details['district'] = 'HCAD'
            # Write-back to Supabase so next lookup is instant (self-healing cache)
            try:
                from backend.db.supabase_client import supabase_service
                cache_record = {k: v for k, v in details.items() if v is not None}
                await supabase_service.upsert_property(cache_record)
                logger.info(f"HCAD: Cached scraped data for {account_number} to Supabase.")
            except Exception as e:
                logger.warning(f"HCAD: Failed to cache scraped data: {e}")
            return details

        # 2. Fallback: Discovery via Street Search (if address is known)
        # If primary scrape failed but we have an address (e.g. from manual input or global DB),
        # try to find the property by searching its street.
        if not details and address:
            logger.info(f"HCAD: Primary lookup failed. Attempting fallback discovery for address: {address}")
            try:
                # Extract street name from address
                import re
                # Simple logic: remove house number, get street
                street_search = address
                match = re.search(r'^\d+\s+(.*)', address)
                if match:
                    street_search = match.group(1).strip()
                
                logger.info(f"HCAD: Discovery fallback searching for neighbors on '{street_search}'")
                neighbors = await self.get_neighbors_by_street(street_search)
                
                # Look for our account or address in the results
                target_clean = account_number.strip().replace('-', '')
                for n in neighbors:
                    if n.get('account_number') == target_clean:
                        logger.info(f"HCAD: Discovery found target account {account_number} in street results!")
                        # We found basic info (address, maybe owner) from the table
                        # We can try to promote this to a full record or just return what we have
                        return {
                            "account_number": account_number,
                            "address": n.get('address', address),
                            "district": "HCAD",
                            "fallback_method": "street_discovery"
                        }
            except Exception as e:
                logger.warning(f"HCAD: Discovery fallback failed: {e}")

        # 3. Final Fallback: Manual Mapping (Last Resort)
        logger.warning(f"New Portal flow failed. Trying hardcoded Discovery fallback for {account_number}")
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
        return True

    async def _bypass_security(self, page):
        """Dedicated logic to wait for Cloudflare challenges to clear."""
        logger.info("Detecting security challenge (Cloudflare)...")
        try:
            for i in range(45):
                title = await page.title()
                logger.info(f"Current Page title: '{title}' (Attempt {i+1}/45)")
                if "Just a moment" not in title and "Security" not in title:
                    if await page.query_selector("input[type='search']") or \
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
                browser = await _launch_browser(p)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                    locale="en-US",
                    timezone_id="America/Chicago",
                    color_scheme="dark",
                )
                
                # Defeat simple webdriver detection properties
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                """)
                
                page = await context.new_page()
                
                # Apply playwright-stealth patches to evade Cloudflare
                if HAS_STEALTH:
                    await stealth_async(page)
                    logger.info("Playwright stealth mode applied.")
                
                # Step 1: Land on Search Home
                logger.info(f"Navigating to {self.portal_url}")
                await page.goto(self.portal_url, wait_until="load", timeout=60000)
                await self._bypass_security(page)

                
                # Step 2: Select Search Mode (Account vs Property Address)
                # Actual portal radio IDs discovered via DOM inspection:
                #   Property Address: input#PROPERTYADDRESS  (value='PROPERTYADDRESS')
                #   Account Number:   input#ACCOUNTID        (value='ACCOUNTID')
                is_address = any(c.isalpha() for c in account_number)
                if is_address:
                    logger.info("Selecting 'Property Address' search mode...")
                    for sel in ["#PROPERTYADDRESS", "input[value='PROPERTYADDRESS']", "label[for='PROPERTYADDRESS']",
                                "label[for='LOCATION']", "input[value='LOCATION']"]:
                        try:
                            await page.click(sel, timeout=5000, force=True)
                            logger.info(f"Clicked address selector: {sel}")
                            break
                        except Exception:
                            continue
                    else:
                        logger.warning("Could not click Property Address radio — proceeding anyway.")
                    await asyncio.sleep(0.5)
                else:
                    logger.info("Selecting 'Account Number' search mode...")
                    for sel in ["#ACCOUNTID", "input[value='ACCOUNTID']", "label[for='ACCOUNTID']",
                                "label[for='ACCOUNTNUMBER']", "input[value='ACCOUNTNUMBER']"]:
                        try:
                            await page.click(sel, timeout=5000, force=True)
                            logger.info(f"Clicked account selector: {sel}")
                            break
                        except Exception:
                            continue
                    await asyncio.sleep(0.5)

                # Step 3: Search
                html_before = await page.content()
                os.makedirs("debug", exist_ok=True)
                with open("debug/form_dump.html", "w", encoding="utf-8") as f:
                    f.write(html_before)

                input_selector = "input[type='search']"
                await page.fill(input_selector, "")
                
                search_term = account_number
                if is_address:
                    # Strip city/state 
                    search_term = search_term.split(',')[0].strip()
                    # Strip common street suffixes that break HCAD search
                    search_term = re.sub(r'(?i)\b(Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Boulevard|Blvd|Parkway|Pkwy|Lane|Ln|Court|Ct|Circle|Cir|Trail|Trl|Highway|Hwy|Freeway|Fwy)\b[\.]?', '', search_term).strip()
                    logger.info(f"Normalized address search term: {search_term}")
                    
                await page.type(input_selector, search_term, delay=80)
                await page.keyboard.press("Enter")
                
                # Step 4: Wait for data to appear (Polling approach)
                logger.info("Polling for property data...")
                
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 45:
                    content = await page.content()
                    
                    # Detection level 1: Detail page already loaded
                    if await page.locator("#OwnerInfoComponent").is_visible():
                        logger.info("Data detected on detail page.")
                        break

                    # Detection level 1.5: No results found
                    if "No matching records found" in content or "No data available in table" in content or "No accounts found" in content or "No results" in content:
                        logger.warning(f"Fast fail: 'No records found' in table for {search_term}")
                        return None

                    # Detection level 2: Search results table found
                    if "table-hover" in content or "Account Number" in content:
                        try:
                            # Fast fail check: If table contains only 7-digit accounts (Business Personal Property)
                            # and no 13-digit accounts, we should return None immediately rather than polling until timeout
                            has_real_property = await page.evaluate("""() => {
                                const texts = Array.from(document.querySelectorAll('td')).map(td => td.innerText.trim());
                                return texts.some(t => /^\\d{13}$/.test(t) || t.includes('13-digit'));
                            }""")
                            
                            has_table_rows = await page.locator("tr").count() > 1
                            if has_table_rows and not has_real_property and "Account Number" in content:
                                logger.warning(f"Fast fail: Only personal property accounts found for '{account_number}' (no 13-digit accounts)")
                                return None
                            
                            if is_address:
                                result_link = page.locator("tr.resulttr").first
                                if not await result_link.is_visible():
                                    result_link = page.locator("tr.table-hover td a").first
                            else:
                                result_link = page.get_by_text(account_number, exact=True).first
                                
                            if await result_link.is_visible():
                                logger.info("Clicking result link from table...")
                                await result_link.click()
                                await asyncio.sleep(2)
                        except Exception as e: 
                            pass  # Still polling
                    
                    await asyncio.sleep(2)
                else:
                    logger.error("Timed out waiting for property data to appear.")
                    os.makedirs("debug", exist_ok=True)
                    with open(f"debug/poll_fail_{account_number.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
                        f.write(content)
                    await page.screenshot(path=f"debug/poll_fail_{account_number.replace(' ', '_')}.png")
                    return None

                # Step 5: Extraction
                await asyncio.sleep(2)  # Final settle
                
                # Extract the REAL account number from the page if we searched by address
                detected_account = account_number
                try:
                    header_text = await page.locator(".whitebox-header").first.inner_text()
                    acc_match = re.search(r'(\d{13})', header_text)
                    if acc_match:
                        detected_account = acc_match.group(1)
                        logger.info(f"Detected 13-digit account: {detected_account}")
                except: pass

                details = {"account_number": detected_account, "district": "HCAD"}

                # Address
                try:
                    addr_el = page.locator("#OwnerInfoComponent span.whitebox-large-font")
                    if await addr_el.count() > 0:
                        addr_parts = await addr_el.all_inner_texts()
                        details['address'] = " ".join([a.strip() for a in addr_parts if a.strip()])
                except: pass

                # Owner Name, Mailing Address, Legal Description
                try:
                    # Robust Owner Name Extraction for New Portal
                    owner_found = False
                    
                    # Strategy 1: Look for table row with "Owner"
                    # New portal often has <th>Owner Name</th><td>NAME</td>
                    owner_row = page.locator("tr").filter(has_text=re.compile(r"Owner Name|Owner:", re.IGNORECASE)).first
                    if await owner_row.count() > 0:
                        val_cell = owner_row.locator("td").first
                        if await val_cell.count() > 0:
                            details['owner_name'] = (await val_cell.inner_text()).strip()
                            owner_found = True
                    
                    # Strategy 2: Look for specific Owner info container classes
                    if not owner_found:
                         owner_el = page.locator(".owner-name, td[data-label='Owner Name']").first
                         if await owner_el.count() > 0:
                             details['owner_name'] = (await owner_el.inner_text()).strip()
                             owner_found = True

                    # Strategy 3: Parsing the text block (Fallback)
                    if not owner_found:
                        owner_info = await page.locator("#OwnerInfoComponent").inner_text()
                        lines = [l.strip() for l in owner_info.split('\n') if l.strip()]
                        for line in lines:
                            if 'Owner' in line and ':' in line:
                                details['owner_name'] = line.split(':', 1)[1].strip()
                                break
                        # If still not found, try the first non-numeric line (often name)
                        if not details.get('owner_name') and len(lines) >= 2:
                            for line in lines:
                                if not line.startswith('Account') and not any(c.isdigit() for c in line[:3]):
                                    details['owner_name'] = line
                                    break
                except Exception as e:
                    logger.warning(f"Owner info extraction error: {e}")

                # Robust Owner Name & Address Extraction
                try:
                    # Strategy 1: Table header adjacency (common in HCAD standard view)
                    owner_th = page.locator("th", has_text=re.compile(r"^Owner Name", re.IGNORECASE))
                    if await owner_th.count() > 0:
                        details['owner_name'] = (await owner_th.locator("xpath=following-sibling::td").first.inner_text()).strip()
                    
                    addr_th = page.locator("th", has_text=re.compile(r"Mailing Address", re.IGNORECASE))
                    if await addr_th.count() > 0:
                        details['mailing_address'] = (await addr_th.locator("xpath=following-sibling::td").first.inner_text()).strip()
                        
                    # Strategy 2: Label finding in cards (new portal style)
                    if not details.get('owner_name'):
                        card_text = await page.locator("#OwnerInfoComponent").inner_text()
                        for line in card_text.split('\n'):
                            if "Owner Name:" in line:
                                details['owner_name'] = line.split("Owner Name:")[1].strip()
                            if "Mailing Address:" in line:
                                details['mailing_address'] = line.split("Mailing Address:")[1].strip()

                except Exception as e:
                    logger.warning(f"Owner extraction fallback failed: {e}")

                # Last resort: HCAD legacy API (returns JSON with real owner data)
                if not details.get('owner_name') or details.get('owner_name', '').lower() in ('on file', ''):
                    try:
                        import httpx
                        acct_clean = details.get('account_number', account_number).replace('-', '').replace(' ', '')
                        api_url = f"https://hcad.org/api/hcad/appraisalData/{acct_clean}"
                        async with httpx.AsyncClient(timeout=8) as client:
                            resp = await client.get(api_url, headers={"Accept": "application/json"})
                            if resp.status_code == 200:
                                api_data = resp.json()
                                # Try top-level keys
                                real_owner = (
                                    api_data.get('ownerName') or
                                    api_data.get('owner_name') or
                                    api_data.get('OwnerName') or
                                    (api_data.get('owner', {}) or {}).get('name')
                                )
                                real_addr = (
                                    api_data.get('mailingAddress') or
                                    api_data.get('mailing_address') or
                                    api_data.get('MailingAddress')
                                )
                                if real_owner and real_owner.lower() not in ('on file', ''):
                                    details['owner_name'] = real_owner.strip()
                                    logger.info(f"Got owner name from HCAD API: {real_owner}")
                                if real_addr and real_addr.lower() not in ('on file', ''):
                                    details['mailing_address'] = real_addr.strip()
                    except Exception as e:
                        logger.debug(f"HCAD API owner lookup failed: {e}")

                # Area - Multi-label robust extraction
                area_found = 0
                area_labels = ["Living Area", "Gross Area", "Net Area", "Main Area", "SQ FT"]
                
                for label in area_labels:
                    try:
                        row_locator = page.locator(f"#PropertyComponent .row:has-text('{label}')")
                        if await row_locator.count() > 0:
                            for selector in [".col-6:nth-child(2)", ".col", "span"]:
                                val_locator = row_locator.locator(selector).last
                                if await val_locator.count() > 0:
                                    area_text = await val_locator.inner_text()
                                    val = self._parse_number(area_text.replace("SF", ""))
                                    if val > area_found:
                                        area_found = val
                                        break
                        if area_found > 0: break
                    except: continue

                # Last ditch fallback: Regex on property component text
                if area_found == 0:
                    try:
                        prop_text = await page.locator("#PropertyComponent").inner_text()
                        for label in area_labels:
                            match = re.search(f"{label}[:\\s]*([\\d,]+)", prop_text, re.IGNORECASE)
                            if match:
                                val = self._parse_number(match.group(1))
                                if val > area_found: area_found = val
                    except: pass

                details['building_area'] = area_found
                
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

                # Property Type / State Class
                try:
                    # Try to find "State Class" or "Land Use"
                    state_class_row = page.locator("tr", has_text=re.compile(r"State Class|Land Use", re.IGNORECASE)).first
                    if await state_class_row.count() > 0:
                        # Value is usually the last cell
                        details['property_type'] = (await state_class_row.locator("td").last.inner_text()).strip()
                    else:
                        # Fallback: Check for generic type in header
                        header_text = await page.locator(".card-header").first.inner_text()
                        if "Commercial" in header_text: details['property_type'] = "Commercial"
                        elif "Residential" in header_text: details['property_type'] = "Residential"
                except: 
                    details['property_type'] = "Unknown"

                # Valuation logic
                async def extract_vals():
                    return await page.evaluate("""() => {
                        const valBox = document.getElementById('ValuationComponent');
                        if (!valBox) return { appraised: null, market: null };
                        
                        let appraised = null;
                        let market = null;

                        const clean = (s) => s ? s.replace(/[$,\\s]/g, '') : null;

                        // 1. Try table rows (Most reliable for Certified values)
                        const rows = Array.from(valBox.querySelectorAll('tr'));
                        for (const row of rows) {
                            const text = row.innerText;
                            const cells = row.querySelectorAll('td');
                            const val = cells.length > 0 ? cells[cells.length - 1].innerText : null;
                            
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
                        // Modern Layout (Cards / Rows)
                        if (valBox.innerText.includes('All Values Pending')) {
                            return { appraised: 'Pending', market: 'Pending' };
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
                
                # Phase B: Detailed Enrichment
                logger.info("Extracting detailed building, valuation, and land details...")
                
                # 1. Building Details (Grade/Quality)
                try:
                    expand_btn = page.locator("#imgExpand").first
                    if await expand_btn.is_visible():
                        await expand_btn.click()
                        await asyncio.sleep(1)
                        details['building_grade'] = await page.locator("#BuildingDataView tr:has-text('Grade Adjustment') td.data").first.inner_text()
                        details['building_quality'] = await page.locator("#BuildingDataView tr:has-text('Cond / Desir / Util') td.data").first.inner_text()
                        # Style (from main table)
                        style_text = await page.locator("#BuildingSummaryComponent table tbody tr:nth-child(2) td:nth-child(6)").inner_text()
                        details['style'] = style_text.strip()
                except: pass

                # 2. Land Details (Breakdown & Total Area)
                try:
                    land_table = page.locator("#LandDetailsDiv table")
                    if await land_table.is_visible():
                        rows = await land_table.locator("tbody tr").all()
                        breakdown = []
                        total_land_area = 0
                        for row in rows:
                            text = await row.inner_text()
                            if "SF" in text:
                                cells = await row.locator("td").all_inner_texts()
                                if len(cells) >= 10:
                                    use = cells[1].strip().replace("\n", " ")
                                    units = self._parse_number(cells[3].replace(",", ""))
                                    breakdown.append({"use": use, "units": units})
                                    total_land_area += units
                        details['land_breakdown'] = breakdown
                        details['land_area'] = total_land_area
                except: pass

                # 3. Multi-Year Valuation History
                history = {}
                # Capture current year first
                current_year_el = page.locator("#dropdownMenuButton1")
                current_year = await current_year_el.inner_text()
                history[current_year.strip()] = vals
                
                # Try Switching Years
                try:
                    await current_year_el.click(timeout=5000)
                    await asyncio.sleep(1)
                    dropdown_items = page.locator(".dropdown-item")
                    item_texts = await dropdown_items.all_inner_texts()
                    years = sorted([t.strip() for t in item_texts if t.strip().isdigit()], reverse=True)
                    
                    # Look for up to 4 years of history
                    for year_to_try in years[:4]:
                        if year_to_try == current_year.strip(): continue
                        
                        logger.info(f"Switching to year {year_to_try} for history...")
                        await page.click(f".dropdown-item:has-text('{year_to_try}')", timeout=5000)
                        await asyncio.sleep(4) # Allow Blazor to settle
                        
                        new_vals = await extract_vals()
                        history[year_to_try] = new_vals
                        
                        # Set primary vals to most recent NON-PENDING year if current is pending
                        if ("Pending" in vals['appraised'] or self._parse_currency(vals['appraised']) == 0) and \
                           ("Pending" not in new_vals['appraised'] and self._parse_currency(new_vals['appraised']) > 0):
                            vals = new_vals
                            logger.info(f"Using {year_to_try} as primary value (current was pending)")

                        await page.click("#dropdownMenuButton1", timeout=5000)
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Failed to extract history: {e}")

                details['valuation_history'] = history
                details['appraised_value'] = self._parse_currency(vals['appraised'])
                details['market_value'] = self._parse_currency(vals['market']) or details['appraised_value']

                return details

            except Exception as e:
                logger.error(f"New Portal human-flow failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                if browser:
                    await browser.close()
        return None

    async def get_neighbors_by_street(self, street_name: str, search_term: str = None) -> List[Dict]:
        """
        Searches for all properties on a street and extracts their info from the results table.
        Uses smart polling instead of fixed sleeps for reliability.
        
        Args:
            street_name: Used for logging only (the conceptual street being searched).
            search_term: The actual string typed into HCAD search box. Defaults to street_name.
                         Pass a full address like '2504 N Loop W' to filter by street number range.
        """
        actual_search = search_term or street_name
        logger.info(f"HCAD: Discovering neighbors on street: {street_name} (search: '{actual_search}')")
        async with async_playwright() as p:
            neighbors = []
            browser = None
            try:
                browser = await _launch_browser(p)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                await page.goto(self.portal_url, wait_until="load", timeout=60000)
                await self._bypass_security(page)
                
                input_selector = "input[type='search']"
                await page.wait_for_selector(input_selector, timeout=30000)
                await page.fill(input_selector, actual_search)
                await page.keyboard.press("Enter")
                
                # Smart polling: wait for results table or timeout
                logger.info(f"HCAD: Waiting for results table for '{actual_search}'...")
                try:
                    await page.wait_for_selector("tr", timeout=30000)
                    await asyncio.sleep(2)  # Brief settle for full render
                except Exception:
                    logger.warning(f"HCAD: Timed out waiting for results table for '{actual_search}'")
                    return []
                
                # Extract results from the table
                rows = await page.evaluate("""() => {
                    const results = [];
                    const seen = new Set();
                    
                    // 1. Try Standard Search Table
                    // HCAD table layout: [Account Number] | [Owner Name] | [Property Address]
                    const tableRows = document.querySelectorAll('tr');
                    tableRows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        const texts = [...cells].map(td => td.innerText.trim());
                        if (texts.length < 2) return;
                        
                        // Find the 13-digit account number cell
                        let accIdx = texts.findIndex(t => /^\\d{13}$/.test(t));
                        if (accIdx === -1) return;
                        let acc = texts[accIdx];
                        if (seen.has(acc)) return;
                        seen.add(acc);
                        
                        // Property address: prefer a cell starting with a digit (house number)
                        let addr = 'Unknown';
                        for (let i = accIdx + 1; i < texts.length; i++) {
                            if (/^\\d/.test(texts[i])) { addr = texts[i]; break; }
                        }
                        // Fallback: cell at accIdx+2 (skip owner name)
                        if (addr === 'Unknown' && texts.length > accIdx + 2) {
                            addr = texts[accIdx + 2];
                        }
                        
                        results.push({ account_number: acc, address: addr });
                    });
                    
                    // 2. Fallback: Scan all links if table failed
                    if (results.length === 0) {
                        const links = document.querySelectorAll('a');
                        links.forEach(a => {
                            const text = a.innerText.trim();
                            if (/^\\d{13}$/.test(text) && !seen.has(text)) {
                                seen.add(text);
                                results.push({
                                    account_number: text,
                                    address: "Unknown"
                                });
                            }
                        });
                    }
                    return results;
                }""")
                
                logger.info(f"HCAD: Found {len(rows)} unique potential neighbors on {street_name}")
                for row in rows:
                    row['district'] = 'HCAD'
                return rows
            except Exception as e:
                logger.error(f"HCAD: Street neighbor discovery failed: {e}")
                return []
            finally:
                if browser:
                    await browser.close()

    async def get_neighbors(self, neighborhood_code: str) -> List[Dict]:
        """
        HCAD does NOT support neighborhood code searches via the public portal.
        Codes like '8014.02' are internal HCAD market area codes not exposed in
        the search UI.

        However, the ETL pipeline (scripts/hcad_bulk_import.py) populates Supabase
        with neighborhood codes from HCAD's annual data files. We query that first
        for instant neighborhood discovery.
        """
        if not neighborhood_code or neighborhood_code == "Unknown":
            return []

        if self.is_commercial_neighborhood_code(neighborhood_code):
            logger.info(f"HCAD: Skipping neighborhood search for commercial code '{neighborhood_code}'")
            return []

        # Supabase DB-powered neighborhood search (ETL data)
        try:
            from backend.db.supabase_client import supabase_service
            db_neighbors = await supabase_service.get_neighbors_from_db(
                account_number="", neighborhood_code=neighborhood_code,
                building_area=1, district="HCAD", tolerance=10.0, limit=50
            )
            if db_neighbors:
                logger.info(f"HCAD: Returning {len(db_neighbors)} neighbors from Supabase for nbhd '{neighborhood_code}'")
                return db_neighbors
        except Exception as e:
            logger.warning(f"HCAD: Supabase neighbor lookup failed: {e}")

        logger.info(
            f"HCAD: No DB neighbors found for '{neighborhood_code}'. "
            f"Portal does not support market area code search. "
            f"Relying on street-level discovery only."
        )
        return []


    async def _discover_address(self, account_number: str) -> Optional[str]:
        mappings = {
            "0660460360030": "843 Lamonte Ln, Houston, TX 77018"
        }
        return mappings.get(account_number)

if __name__ == "__main__":
    pass
