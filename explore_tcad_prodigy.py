import asyncio
from playwright.async_api import async_playwright

async def explore_tcad():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Search Page
            print("Navigating to search page...")
            await page.goto("https://travis.prodigycad.com/property-search", timeout=90000, wait_until="networkidle")
            await page.wait_for_selector("#searchInput", timeout=30000)
            
            print("Filling search input...")
            await page.fill("#searchInput", "177373")
            await asyncio.sleep(1)
            
            # Find the search button specifically
            print("Clicking search button...")
            # Usually the only button with an icon in that area
            await page.click("button >> .MuiSvgIcon-root")
            
            print("Waiting for results...")
            # Wait for either detail page or grid
            try:
                await page.wait_for_function(
                    "() => window.location.href.includes('/property-detail/') || document.querySelectorAll('.ag-cell').length > 0",
                    timeout=20000
                )
            except Exception as e:
                print(f"Wait failed or timed out: {e}")

            print(f"Current URL: {page.url}")
            
            if "/property-detail/" in page.url:
                print("Directly on details page!")
            else:
                print("Still on search/results page. Capturing content...")
                with open("tcad_results_state.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                
                # Check if we can see the result link in AG Grid
                print("Looking for result in AG Grid...")
                # col-id="pid" contains the property ID link
                result_link = page.locator('[col-id="pid"] a').first
                if await result_link.count() > 0:
                    print("Clicking result link in AG Grid...")
                    await result_link.click()
                    # Wait for navigation or URL change
                    try:
                        await page.wait_for_url("**/property-detail/**", timeout=30000)
                    except Exception as e:
                        print(f"Navigation wait failed: {e}. Current URL: {page.url}")
                else:
                    print("Result link '[col-id=\"pid\"] a' not found.")

            print("Final Details Page Captured.")
            # Extra wait for React to populate values
            await asyncio.sleep(10)
            with open("tcad_property_details.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            
            print("Finished exploration.")
            
        except Exception as e:
            print(f"Error: {e}")
            with open("tcad_error.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(explore_tcad())
