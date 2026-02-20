import asyncio
from playwright.async_api import async_playwright
import os

async def human_flow_street_click(street="LAMONTE"):
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
            print(f"Searching for street: {street}...")
            await page.fill(input_selector, street)
            await page.keyboard.press("Enter")
            
            print("Waiting for results table...")
            await asyncio.sleep(12)
            
            # Find the first account number shaped thing and click it
            # The previous search_street showed results like "0660460360031"
            # Let's try to find any link containing "066046"
            link = await page.query_selector("a:text-matches('066046')")
            if not link:
                # Try clicking any cell in the first row if there's a table
                link = await page.query_selector("table tr td a")
            
            if link:
                print("Found match, clicking...")
                await link.click()
                await asyncio.sleep(10)
                
                text = await page.evaluate("() => document.body.innerText")
                print(f"Detail Text snippet: {text[:1000].replace('\n', ' ')}")
                
                # Capture everything for extraction analysis
                with open("debug/detail_dump_live.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                
                await page.screenshot(path="debug/human_flow_detail_success.png")
            else:
                print("No clickable result found.")
                await page.screenshot(path="debug/human_flow_fail.png")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if not os.path.exists("debug"): os.makedirs("debug")
    asyncio.run(human_flow_street_click())
