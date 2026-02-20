import asyncio
from playwright.async_api import async_playwright
import re

async def explore_dcad():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Search Page
            print("Navigating to DCAD account search...")
            await page.goto("https://www.dallascad.org/SearchAcct.aspx", timeout=60000)
            await asyncio.sleep(2)
            
            with open("dcad_search_acct_page.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            
            # DCAD Account input ID is usually 'txtAccountNumber'
            print("Filling account number...")
            account_input = page.locator("#txtAccountNumber")
            if await account_input.count() > 0:
                await account_input.fill("00000776533000000")
                await page.click("#cmdSubmit")
            else:
                # Try generic input
                account_input = page.locator("input[type='text']").first
                if await account_input.count() > 0:
                    await account_input.fill("00000776533000000")
                    await page.keyboard.press("Enter")
                else:
                    print("Account input not found.")
            
            print("Waiting for results...")
            await asyncio.sleep(5)
            
            with open("dcad_results.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            
            # Click the result
            # DCAD results are usually in a table with links
            result_link = page.locator("a[href*='AcctDetail']").first
            if await result_link.count() > 0:
                print("Clicking result link...")
                await result_link.click()
                await asyncio.sleep(5)
                
                with open("dcad_property_details.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
            else:
                print("No result link found.")

            print("Finished exploration.")
            
        except Exception as e:
            print(f"Error: {e}")
            with open("dcad_error.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(explore_dcad())
