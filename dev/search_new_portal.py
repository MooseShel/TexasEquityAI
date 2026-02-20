import asyncio
from playwright.async_api import async_playwright
import os

async def search_new_portal(query="0660460360030"):
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
            
            # Use a more specific selector for the text input
            input_selector = "input[placeholder*='Search like']"
            print(f"Filling search query: {query}...")
            await page.fill(input_selector, query)
            await page.keyboard.press("Enter")
            
            print("Search submitted. Waiting for results...")
            # Results might take a few seconds to load
            await asyncio.sleep(10)
            
            text = await page.evaluate("() => document.body.innerText")
            print(f"Result Snippet: {text[:800].replace('\n', ' ')}")
            
            # Check for "Neighborhood" or "Area" in the text
            found = []
            for k in ["Neighborhood", "Area", "Year Built", "Value"]:
                if k.lower() in text.lower():
                    found.append(k)
            print(f"Found keywords: {found}")
            
            await page.screenshot(path="debug/new_portal_result.png")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if not os.path.exists("debug"): os.makedirs("debug")
    asyncio.run(search_new_portal())
