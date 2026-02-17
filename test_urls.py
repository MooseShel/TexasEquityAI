import asyncio
from playwright.async_api import async_playwright
import os

async def test_urls():
    account = "0660460360030"
    urls = [
        f"https://public.hcad.org/records/details.asp?account={account}",
        f"https://public.hcad.org/records/details.asp?account={account}&year=2025",
        f"https://public.hcad.org/records/details.asp?account={account}&year=2024",
        f"https://public.hcad.org/records/details.asp?account={account}&year=2023"
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        for url in urls:
            print(f"\nTesting URL: {url}")
            try:
                response = await page.goto(url, wait_until="load", timeout=30000)
                print(f"Status: {response.status if response else 'No Response'}")
                await asyncio.sleep(3)
                
                text = await page.evaluate("() => document.body.innerText")
                if "Internal server error" in text:
                    print("Result: 500 Internal Server Error")
                elif "Appraisal District" in text or "Account" in text:
                    print("Result: POTENTIAL SUCCESS! Found keywords.")
                    # Save a snippet
                    print(f"Snippet: {text[:200].replace('\n', ' ')}")
                    # Save a screenshot for this successful one
                    await page.screenshot(path=f"debug/success_{url.split('=')[-1]}.png")
                else:
                    print(f"Result: Unknown content. Length: {len(text)}")
            except Exception as e:
                print(f"Error testing {url}: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_urls())
