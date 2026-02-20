import asyncio
from playwright.async_api import async_playwright

async def test_firefox():
    account = "0660460360030"
    url = f"https://public.hcad.org/records/details.asp?account={account}"
    
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        print(f"Opening {url} with Firefox...")
        try:
            response = await page.goto(url, wait_until="load", timeout=60000)
            print(f"Status: {response.status}")
            
            text = await page.evaluate("() => document.body.innerText")
            if "500" in text and "Internal" in text:
                print("Result: Still 500 error.")
            elif "0660460360030" in text or "Account" in text:
                print("Result: SUCCESS! Firefox worked.")
                print(f"Snippet: {text[:200].replace('\n', ' ')}")
            else:
                print(f"Result: No error, but no data. Length: {len(text)}")
                print(f"Snippet: {text[:200].replace('\n', ' ')}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_firefox())
