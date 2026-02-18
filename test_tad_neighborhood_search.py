import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("Navigating to tad.org...")
            await page.goto("https://www.tad.org", timeout=60000)
            
            # Select NeighborhoodCode search type
            print("Selecting NeighborhoodCode...")
            await page.select_option("#search-type", "NeighborhoodCode")
            
            print("Filling search form...")
            await page.fill("#query", "OFC-Central Business District")
            
            print("Submitting search...")
            async with page.expect_navigation(timeout=60000):
                await page.click(".property-search-form button[type='submit']")
            
            print(f"Search Results URL: {page.url}")
            
            # Dump results
            with open("tad_neighborhood_results.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            print("Saved tad_neighborhood_results.html")
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
