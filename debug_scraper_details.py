import asyncio
from playwright.async_api import async_playwright
import logging
import re
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_hcad(account_number):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to HCAD search...")
            await page.goto("https://search.hcad.org/", wait_until="networkidle", timeout=60000)
            
            # Simple wait for security
            await asyncio.sleep(5)
            
            logger.info(f"Searching for {account_number}...")
            # Select Account Number radio
            radio = await page.query_selector("text='Account Number'")
            if radio: await radio.click()
            
            input_selector = "input[placeholder*='Search like']"
            await page.fill(input_selector, account_number)
            await page.keyboard.press("Enter")
            
            logger.info("Waiting for result...")
            await page.wait_for_selector(f"text='{account_number}'", timeout=15000)
            
            link = await page.query_selector(f"text='{account_number}'")
            if link:
                logger.info("Found result, taking screenshot...")
                await page.screenshot(path="debug_search_results.png")
                logger.info("Clicking result...")
                # Try clicking and wait for navigation or new page
                try:
                    async with context.expect_page(timeout=15000) as new_page_info:
                        await link.click()
                    page = await new_page_info.value
                    logger.info("New tab opened.")
                except Exception as e:
                    logger.info(f"No new tab detected ({e}), attempting to stay on current page...")
                    # Link might have changed or page refreshed
                    link = await page.query_selector(f"text='{account_number}'")
                    if link:
                        await link.click()
                    else:
                        logger.error("Link disappeared!")
                
                logger.info("Waiting for detail page content...")
                # Wait for something that appears on the property detail page
                # e.g. "Valuation", "Land", "Building", "Location"
                try:
                    await page.wait_for_selector("text='Location'", timeout=20000)
                except:
                    logger.warning("Location not found, checking for Valuation...")
                    await page.wait_for_selector("text='Valuation'", timeout=10000)

                await asyncio.sleep(5) # Final settle
                
                # Check for year switcher
                years = await page.query_selector_all("text='2025'")
                for y in years:
                    logger.info("Found '2025' text, attempting to click it if it's a tab/link...")
                    try:
                        await y.click()
                        await asyncio.sleep(3)
                        logger.info("Clicked 2025.")
                        break
                    except: continue

                # Save full HTML
                html = await page.content()
                with open("debug_hcad_full.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info("Saved full HTML.")

                # Inspect Valuation History section
                valuation_section = await page.evaluate("""() => {
                    const el = Array.from(document.querySelectorAll('*')).find(e => e.innerText === 'Valuation History');
                    if (el && el.parentElement) {
                        return el.parentElement.innerHTML;
                    }
                    return "Not Found";
                }""")
                print("\n=== VALUATION SECTION HTML ===\n")
                print(valuation_section)
                
                # Try to find any $ values even without $ sign
                all_numbers = re.findall(r"\b\d{1,3}(?:,\d{3})+\b", text)
                print(f"All large numbers found: {all_numbers}")
                
                # Print all tables
                table_texts = await page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('table')).map(t => t.innerText);
                }""")
                for i, t in enumerate(table_texts):
                    print(f"\n--- TABLE {i} ---\n")
                    print(t)
                    print("\n---------------\n")
                    with open(f"debug_table_{i}.txt", "w", encoding="utf-8") as f:
                        f.write(t)

                # Save full HTML
                html = await page.content()
                with open("debug_hcad_full.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info("Saved full HTML.")
                
        except Exception as e:
            logger.error(f"Error: {e}")
            await page.screenshot(path="debug_error.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    acc = "0660460360026" # From user screenshot
    asyncio.run(debug_hcad(acc))
