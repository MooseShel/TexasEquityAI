import asyncio
from playwright.async_api import async_playwright
import os

async def search_hcad():
    account = "0660460360030"
    search_url = "https://public.hcad.org/records/Real.asp"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to search page: {search_url}...")
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Look for the account input. Often called 'taxacc' or similar.
            # Let's list inputs to be sure
            inputs = await page.query_selector_all("input")
            for inp in inputs:
                name = await inp.get_attribute("name")
                # print(f"Found input: {name}")
            
            # Fill the taxacc field (Common HCAD name)
            await page.fill('input[name="taxacc"]', account)
            await page.press('input[name="taxacc"]', "Enter")
            
            print("Search submitted. Waiting for results...")
            await asyncio.sleep(5)
            
            # Check current URL
            current_url = page.url
            print(f"Current URL: {current_url}")
            
            # Capture screenshot of whatever we got
            os.makedirs("debug", exist_ok=True)
            await page.screenshot(path="debug/hcad_after_search.png")
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Page text (first 500 chars): {text[:500].replace('\n', ' ')}")
            
            if "details.asp" in current_url or "details.asp" in text:
                print("LANDED ON DETAILS OR FOUND LINK!")
            else:
                print("Did not land on details page directly.")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(search_hcad())
