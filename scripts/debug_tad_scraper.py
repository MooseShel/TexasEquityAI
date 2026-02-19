import asyncio
from playwright.async_api import async_playwright
import os

async def debug_tad():
    os.makedirs("debug", exist_ok=True)
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True) # Visible for debugging if possible? No, headless for script.
        page = await browser.new_page()
        
        print("Navigating to https://www.tad.org ...")
        try:
            await page.goto("https://www.tad.org", timeout=60000)
            print("Page loaded.")
            
            # Screenshot
            await page.screenshot(path="debug/tad_search_page.png")
            print("Screenshot saved to debug/tad_search_page.png")
            
            # Dump HTML
            content = await page.content()
            with open("debug/tad_search_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("HTML saved to debug/tad_search_page.html")
            
            # Check selectors
            search_type = await page.query_selector("#search-type")
            print(f"Selector #search-type found: {search_type is not None}")
            
            query = await page.query_selector("#query")
            print(f"Selector #query found: {query is not None}")
            
            search_btn = await page.query_selector("button[type='submit']")
            print(f"Selector button[type='submit'] found: {search_btn is not None}")

            # Also check base URL redirect?
            if page.url != "https://www.tad.org/property-search":
                print(f"Redirected to: {page.url}")

        except Exception as e:
            print(f"Error: {e}")
            await page.screenshot(path="debug/tad_error.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_tad())
