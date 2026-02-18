from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print("Navigating to tad.org...")
            page.goto("https://www.tad.org", timeout=60000)
            print(f"Loaded: {page.title()}")
            
            # Search for "100 Weatherford"
            print("Filling search form...")
            page.fill("#query", "100 Weatherford")
            # Select "Property Address" just in case, or leave All Categories
            # page.select_option("#search-type", "PropertyAddress") 
            
            print("Submitting search...")
            with page.expect_navigation(timeout=60000):
                page.click(".property-search-form button[type='submit']")
            
            print(f"Search Results URL: {page.url}")
            
            # Click first property link
            print("Clicking first property...")
            with page.expect_navigation(timeout=60000):
                page.click("tr.property-header a")
            
            print(f"Details URL: {page.url}")

            # Dump details
            with open("tad_details.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Saved tad_details.html")
                    
        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="tad_error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
