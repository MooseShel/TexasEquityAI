import asyncio
from playwright.async_api import async_playwright
import os

async def try_all_paths():
    account = "0660460360030"
    paths = [
        "https://mobile.hcad.org/property/details.php?account=" + account,
        "https://public.hcad.org/records/QuickSearch.asp",
        "https://public.hcad.org/records/Real.asp"
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        for url in paths:
            print(f"\n--- Trying Path: {url} ---")
            try:
                await page.goto(url, wait_until="load", timeout=30000)
                await asyncio.sleep(3)
                
                text = await page.evaluate("() => document.body.innerText")
                if "500" in text and "Internal" in text:
                    print("Status: 500 Internal Error")
                elif "0660460360030" in text or "Account" in text:
                    print("Status: SUCCESS OR PARTIAL SUCCESS!")
                    print(f"Snippet: {text[:300].replace('\n', ' ')}")
                    # Screenshot
                    clean_name = url.split('/')[-1].split('.')[0]
                    await page.screenshot(path=f"debug/hcad_try_{clean_name}.png")
                else:
                    print(f"Status: Loaded but no data. Keywords not found.")
                
            except Exception as e:
                print(f"Error: {e}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(try_all_paths())
