import asyncio
from playwright.async_api import async_playwright
import os
import re

async def scrape_via_search(account_number="0660460360030"):
    search_url = "https://public.hcad.org/records/Real.asp"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Opening {search_url}...")
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Look for taxacc in frames or main page
            target_frame = page
            for frame in page.frames:
                if await frame.query_selector('input[name="taxacc"]'):
                    target_frame = frame
                    break
            
            print(f"Filling account {account_number}...")
            await target_frame.fill('input[name="taxacc"]', account_number)
            await target_frame.click('button[type="submit"]')
            
            print("Searching...")
            await asyncio.sleep(8) # Wait for it to land
            
            # Check if we landed on a details page or a result list
            current_url = page.url
            print(f"Current URL: {current_url}")
            
            # Some HCAD pages use frames for details too
            text = ""
            for frame in page.frames:
                frame_text = await frame.evaluate("() => document.body.innerText")
                text += "\n--- FRAME ---\n" + frame_text
                
            os.makedirs("debug", exist_ok=True)
            with open("debug/hcad_search_dump.txt", "w", encoding="utf-8") as f:
                f.write(text)
            
            print("Search result saved to debug/hcad_search_dump.txt")
            
            # Simple keyword check
            keywords = ["Address", "Appraised Value", "Neighborhood", "Building Area", "Year Built", "Land Area"]
            for k in keywords:
                if k.lower() in text.lower():
                    print(f"FOUND KEYWORD: {k}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_via_search())
