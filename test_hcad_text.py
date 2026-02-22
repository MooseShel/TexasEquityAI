import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://search.hcad.org/")
        await page.click("#PROPERTYADDRESS")
        await page.fill("input[type='search']", "8100 Washington")
        await page.keyboard.press("Enter")
        await asyncio.sleep(8)
        text = await page.evaluate("document.body.innerText")
        with open("debug/hcad_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
        await browser.close()

asyncio.run(run())
