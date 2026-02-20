import asyncio
from playwright.async_api import async_playwright
import os

async def search_street(street="LAMONTE"):
    url = "https://search.hcad.org/"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        try:
            print(f"Opening {url}...")
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(5)
            
            input_selector = "input[placeholder*='Search like']"
            print(f"Filling street search: {street}...")
            await page.fill(input_selector, street)
            await page.keyboard.press("Enter")
            
            print("Search submitted. Waiting for results...")
            await asyncio.sleep(15) # Results might be slow
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Result Snippet (800-1600): {text[800:1600].replace('\n', ' ')}")
            
            # Look for typical result tokens like '066046' (base of the account number)
            if "066046" in text:
                print("SUCCESS: Found account number snippet in results!")
            else:
                print("No account number snippet found.")
            
            await page.screenshot(path="debug/street_search_result.png")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if not os.path.exists("debug"): os.makedirs("debug")
    asyncio.run(search_street())
