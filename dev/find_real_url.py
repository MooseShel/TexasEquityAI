import asyncio
from playwright.async_api import async_playwright

async def find_real_url():
    url = "https://hcad.org"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print(f"Opening {url}...")
            await page.goto(url, wait_until="load", timeout=60000)
            
            # Find links containing "Search" or "Record"
            links = await page.query_selector_all("a")
            for link in links:
                text = await link.inner_text()
                href = await link.get_attribute("href")
                if "Search" in text or "Records" in text:
                    print(f"Link: Text='{text}', Href='{href}'")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(find_real_url())
