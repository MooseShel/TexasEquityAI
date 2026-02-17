import asyncio
from playwright.async_api import async_playwright
import os

async def debug_hcad():
    account = "0660460360030"
    url = f"https://public.hcad.org/records/details.asp?account={account}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5) # Give it plenty of time
            
            # Save screenshot
            os.makedirs("debug", exist_ok=True)
            screenshot_path = "debug/hcad_debug.png"
            await page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")
            
            # Save HTML
            html = await page.content()
            with open("debug/hcad_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("HTML saved to debug/hcad_debug.html")
            
            # Get text
            text = await page.evaluate("() => document.body.innerText")
            with open("debug/hcad_debug.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("Text saved to debug/hcad_debug.txt")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_hcad())
