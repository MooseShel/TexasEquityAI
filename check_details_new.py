import asyncio
from playwright.async_api import async_playwright
import os

async def check_details_new(account="0660460360030"):
    url = f"https://search.hcad.org/property-details/{account}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        try:
            print(f"Opening {url}...")
            # Establishing a session/cookies from the home page might be required
            await page.goto("https://search.hcad.org/", wait_until="load")
            await asyncio.sleep(2)
            
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(8)
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Text length: {len(text)}")
            
            # Look for keywords in the detail page
            keywords = ["Neighborhood", "Building Area", "Year Built", "Appraised Value"]
            found = {}
            for k in keywords:
                import re
                match = re.search(f"{k}[:\\s]+(.*?)(?:\\n|$)", text, re.IGNORECASE)
                found[k] = match.group(1).strip() if match else "Not found"
            
            print(f"Extraction results: {found}")
            
            if len(text) < 1000:
                print(f"Snippet: {text[:500].replace('\n', ' ')}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_details_new())
