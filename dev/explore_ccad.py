import asyncio
from playwright.async_api import async_playwright
import re

async def explore_ccad():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print("Navigating to CCAD search...")
            await page.goto("https://www.collincad.org/property-search", timeout=60000, wait_until="networkidle")
            await asyncio.sleep(5)
            
            with open("ccad_search_home.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            
            # Check if it's the same portal as TCAD
            print("Finished exploration.")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(explore_ccad())
