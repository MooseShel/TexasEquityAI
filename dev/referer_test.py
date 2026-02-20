import asyncio
from playwright.async_api import async_playwright
import os

async def referer_test():
    account = "0660460360030"
    url = f"https://public.hcad.org/records/details.asp?account={account}"
    referer = "https://public.hcad.org/records/Real.asp"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={"Referer": referer}
        )
        page = await context.new_page()
        
        print(f"Testing URL with Referer header: {url}")
        try:
            response = await page.goto(url, wait_until="load", timeout=30000)
            print(f"Status code: {response.status}")
            await asyncio.sleep(5)
            
            text = await page.evaluate("() => document.body.innerText")
            if "Internal server error" in text:
                print("Result: Still 500 Error.")
            elif "Appraisal District" in text or "Account" in text:
                print("Result: SUCCESS! Referer header worked!")
                print(f"Snippet: {text[:500].replace('\n', ' ')}")
                os.makedirs("debug", exist_ok=True)
                await page.screenshot(path="debug/hcad_referer_success.png")
            else:
                print(f"Result: No error, but no keywords. Length: {len(text)}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(referer_test())
