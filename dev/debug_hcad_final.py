import asyncio
from playwright.async_api import async_playwright
import os

async def debug_hcad():
    account = "0660460360030"
    url = "https://public.hcad.org/records/Real.asp"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"Opening {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Find the input
            await page.fill('input[name="taxacc"]', account)
            await page.click('button[type="submit"]')
            
            print("Search submitted. Waiting for results...")
            await asyncio.sleep(10) # Heavy wait
            
            # Check results
            html = await page.content()
            os.makedirs("debug", exist_ok=True)
            with open("debug/real_results.html", "w", encoding="utf-8") as f:
                f.write(html)
            
            await page.screenshot(path="debug/real_results.png")
            print("Screenshot and HTML saved to debug/")
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Results text snippet: {text[:500].replace('\n', ' ')}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_hcad())
