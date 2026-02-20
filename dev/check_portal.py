import asyncio
from playwright.async_api import async_playwright

async def check_portal():
    url = "https://public.hcad.org/records/Real.asp"
    async with async_playwright() as p:
        # Try Firefox - sometimes less suspicious
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
        )
        page = await context.new_page()
        try:
            print(f"Opening {url}...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Wait for any content
            await asyncio.sleep(5)
            
            print(f"Frames found: {len(page.frames)}")
            for i, frame in enumerate(page.frames):
                print(f"Frame {i}: Name='{frame.name}', URL='{frame.url}'")
                
                # Print all elements that look like they might contain data or forms
                elements = await frame.query_selector_all("input, select, button, a")
                print(f"  Interactive elements count: {len(elements)}")
                for el in elements[:10]: # Just first few
                    tag = await el.evaluate("el => el.tagName")
                    name = await el.get_attribute("name")
                    text = await el.inner_text()
                    print(f"    {tag} name='{name}' text='{text}'")
                
                # If no elements, look for raw text
                content = await frame.evaluate("() => document.body.innerText")
                print(f"  Text count: {len(content)}")
                if len(content) > 0:
                    print(f"  Snippet: {content[:100].replace('\n', ' ')}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_portal())
