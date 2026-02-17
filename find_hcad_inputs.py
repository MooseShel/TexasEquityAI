import asyncio
from playwright.async_api import async_playwright

async def find_inputs():
    url = "https://public.hcad.org/records/QuickSearch.asp"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print(f"Opening {url}...")
        try:
            await page.goto(url, wait_until="load", timeout=60000)
            
            frames = page.frames
            print(f"Found {len(frames)} frames.")
            for i, frame in enumerate(frames):
                print(f"Frame {i}: Name={frame.name}, URL={frame.url}")
                inputs = await frame.query_selector_all("input")
                print(f" - Found {len(inputs)} inputs in this frame.")
                for inp in inputs:
                    name = await inp.get_attribute("name")
                    print(f"   - Name: {name}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(find_inputs())
