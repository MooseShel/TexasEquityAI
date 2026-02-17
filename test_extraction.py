import asyncio
from playwright.async_api import async_playwright
import re

async def get_details(account="0660460360030"):
    # Try the search-engine snippet trick too if portal fails
    url = f"https://public.hcad.org/records/details.asp?account={account}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            # Establishing a session might be needed
            await page.goto("https://hcad.org", wait_until="load")
            await page.goto(url, wait_until="load")
            
            text = await page.evaluate("() => document.body.innerText")
            
            # Neighborhood Code extraction
            nb_match = re.search(r'Neighborhood[:\s]+([\d\.]+)', text)
            nb_code = nb_match.group(1) if nb_match else "Unknown"
            
            # Area extraction
            area_match = re.search(r'Building Area[:\s]+([\d,]+)', text)
            area = area_match.group(1).replace(',', '') if area_match else "0"
            
            print(f"Account: {account}")
            print(f"Neighborhood Code: {nb_code}")
            print(f"Building Area: {area}")
            
            if nb_code == "Unknown":
                print("Dumping full text to see why it failed...")
                print(text[:1000])

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_details())
