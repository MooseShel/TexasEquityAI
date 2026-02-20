import asyncio
from playwright.async_api import async_playwright
import os
import random

async def final_attempt():
    account = "0660460360030"
    # Try the most direct search form URL
    url = "https://public.hcad.org/records/QuickSearch.asp"
    
    async with async_playwright() as p:
        # Use a real device descriptor
        iphone = p.devices['iPhone 13']
        browser = await p.chromium.launch(headless=True)
        # iPhone 13 already has a user_agent, so we don't need to specify it separately
        # unless we want to override it.
        context = await browser.new_context(**iphone)
        page = await context.new_page()
        
        print(f"Emulating iPhone and navigating to {url}...")
        try:
            # Go to home first to set cookies
            await page.goto("https://hcad.org", wait_until="load", timeout=60000)
            await asyncio.sleep(random.uniform(2, 4))
            
            # Now go to the search page
            await page.goto(url, wait_until="load", timeout=60000)
            await asyncio.sleep(5)
            
            # Check for Cloudflare or Error
            content = await page.content()
            if "Internal server error" in content:
                print("Landed on 500 error page immediately.")
            
            # Try to find the taxacc input
            # In some views, 'taxacc' is the name
            await page.wait_for_selector('input[name="taxacc"]', timeout=5000)
            await page.fill('input[name="taxacc"]', account)
            await page.press('input[name="taxacc"]', "Enter")
            
            print("Submitted search. Waiting 10 seconds for results...")
            await asyncio.sleep(10)
            
            print(f"Final URL after search: {page.url}")
            
            # Capture results
            os.makedirs("debug", exist_ok=True)
            await page.screenshot(path="debug/hcad_iphone_final.png")
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Final Text length: {len(text)}")
            if len(text) > 100:
                print(f"Snippet: {text[:1000].replace('\n', ' ')}")
            
            # Check if we have the specific data
            if "Appraised Value" in text or "Property Address" in text:
                print("SUCCESS! DATA FOUND!")
                
        except Exception as e:
            print(f"Error during search: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(final_attempt())
