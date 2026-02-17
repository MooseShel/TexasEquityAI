import asyncio
from playwright.async_api import async_playwright
import os

async def hcad_full_path():
    account = "0660460360030"
    start_url = "https://hcad.org"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Starting at {start_url}...")
        try:
            await page.goto(start_url, wait_until="networkidle", timeout=60000)
            
            # Navigate to Property Search -> Real Property
            # This is complex, let's try direct Real Property search page instead
            # but maybe it sets a cookie
            real_search_url = "https://public.hcad.org/records/Real.asp"
            print(f"Navigating to {real_search_url}...")
            await page.goto(real_search_url, wait_until="networkidle")
            
            # Fill account number
            print("Filling account number...")
            await page.fill('input[name="taxacc"]', account)
            await page.click('button[type="submit"]')
            
            await asyncio.sleep(5)
            print(f"Final URL: {page.url}")
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Text length: {len(text)}")
            
            if "500 - Internal server error" in text:
                print("STILL 500 ERROR!")
            else:
                # Save first 500 chars to see what it is
                print(f"Contents: {text[:500].replace('\n', ' ')}")
                # Screenshot
                await page.screenshot(path="debug/hcad_final_attempt.png")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(hcad_full_path())
