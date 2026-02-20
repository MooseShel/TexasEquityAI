import asyncio
from playwright.async_api import async_playwright

async def check_search_portal():
    url = "https://search.hcad.org/"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print(f"Opening {url}...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            await asyncio.sleep(5) # Wait for SPA load
            
            print(f"URL: {page.url}")
            text = await page.evaluate("() => document.body.innerText")
            print(f"Text snippet: {text[:500].replace('\n', ' ')}")
            
            inputs = await page.query_selector_all("input")
            for inp in inputs:
                name = await inp.get_attribute("name")
                placeholder = await inp.get_attribute("placeholder")
                print(f"Input: name='{name}' placeholder='{placeholder}'")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_search_portal())
