import asyncio
from playwright.async_api import async_playwright
import os

async def try_direct_access():
    account = "0660460360030"
    # Try different URL patterns
    urls = [
        f"https://search.hcad.org/property-details/{account}",
        f"https://search.hcad.org/property/{account}",
        f"https://public.hcad.org/records/details.asp?account={account}" # Old but maybe only needs session
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for url in urls:
            try:
                print(f"Trying {url}...")
                response = await page.goto(url, wait_until="load", timeout=20000)
                print(f"Status: {response.status}")
                await asyncio.sleep(3)
                text = await page.evaluate("() => document.body.innerText")
                if len(text) > 200:
                    print(f"Success/Partial: {text[:200].replace('\n', ' ')}")
                    # Save HTML
                    filename = url.replace("https://", "").replace("/", "_").replace(".", "_") + ".html"
                    with open(f"debug/{filename}", "w", encoding="utf-8") as f:
                        f.write(await page.content())
                else:
                    print("Empty or small page.")
            except Exception as e:
                print(f"Error for {url}: {e}")
        await browser.close()

if __name__ == "__main__":
    if not os.path.exists("debug"): os.makedirs("debug")
    asyncio.run(try_direct_access())
