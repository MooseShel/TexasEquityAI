import asyncio
import sys
from playwright.async_api import async_playwright

async def test():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    print(f"Loop Policy: {asyncio.get_event_loop_policy()}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://example.com")
        print(f"Title: {await page.title()}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())
