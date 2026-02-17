import asyncio
from playwright.async_api import async_playwright
import os

async def check_new_portal():
    url = "https://search.hcad.org/"
    account = "0660460360030"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a more realistic browser context
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        try:
            print(f"Opening {url}...")
            # Use 'load' instead of 'networkidle' to avoid timeout if some analytics fail
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(5)
            
            # Look for ANY input
            inputs = await page.query_selector_all("input")
            print(f"Found {len(inputs)} inputs.")
            for i, inp in enumerate(inputs):
                placeholder = await inp.get_attribute("placeholder")
                name = await inp.get_attribute("name")
                print(f"Input {i}: placeholder='{placeholder}' name='{name}'")
            
            # Try to search for the account number in the first input if no labels
            if inputs:
                await inputs[0].fill(account)
                await page.keyboard.press("Enter")
                print("Search submitted. Waiting for results...")
                await asyncio.sleep(10)
                
                text = await page.evaluate("() => document.body.innerText")
                print(f"Result Snippet: {text[:500].replace('\n', ' ')}")
                
                await page.screenshot(path="debug/new_portal_result.png")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if not os.path.exists("debug"): os.makedirs("debug")
    asyncio.run(check_new_portal())
