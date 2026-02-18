import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print("Navigating to TAD homepage...")
            await page.goto("https://www.tad.org/", timeout=60000)
            
            # Find any links containing "Search"
            print("Looking for search links...")
            search_links = await page.locator("a:has-text('Search')").evaluate_all("nodes => nodes.map(n => n.href)")
            print(f"Search links found: {search_links}")
            
            # Find "Property Search" explicitly
            prop_search = await page.locator("a:has-text('Property Search')").first.get_attribute("href")
            print(f"Explicit Property Search link: {prop_search}")

            target_url = prop_search if prop_search else (search_links[0] if search_links else "https://www.tad.org/property-search/")
            if target_url.startswith("/"): target_url = "https://www.tad.org" + target_url
            print(f"Targeting URL: {target_url}")

            await page.goto(target_url, timeout=60000)
            await page.wait_for_selector("#search-type", timeout=15000)
            
            # Get search types
            options = await page.locator("#search-type option").all_inner_texts()
            values = await page.locator("#search-type option").evaluate_all("nodes => nodes.map(n => n.value)")
            # ...
            print("Search Types Found:")
            for v, t in zip(values, options):
                print(f"  {v}: {t}")
            
            # ... (rest of the script)
                
            # Try a quick Neighborhood Code search for "Food Service General" if it's an option
            if "NeighborhoodCode" in values or "Neighborhood" in values:
                search_type = "NeighborhoodCode" if "NeighborhoodCode" in values else "Neighborhood"
                print(f"Testing search type: {search_type}")
                await page.select_option("#search-type", search_type)
                await page.fill("#query", "Food Service General")
                await page.click(".property-search-form button[type='submit']")
                await asyncio.sleep(5)
                
                # Check for "Results" or wait for table
                print(f"Current URL after search: {page.url}")
                rows_locator = page.locator("table.search-results tbody tr.property-header")
                count = await rows_locator.count()
                print(f"Results found for 'Food Service General': {count}")
                if count > 0:
                    first_row = await rows_locator.first.inner_text()
                    print(f"First result: {first_row.strip().replace('\n', ' ')}")
                else:
                    body_text = await page.evaluate("() => document.body.innerText")
                    if "No properties found" in body_text:
                        print("TAD explicitly said: No properties found.")
                    else:
                        print("No table results, but no 'not found' message either.")
            else:
                print("Neighborhood search type not found in values list.")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
