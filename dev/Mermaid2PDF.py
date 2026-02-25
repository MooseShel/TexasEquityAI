import re
import base64
import requests
import os
import asyncio
from playwright.async_api import async_playwright
import markdown

def mermaid_to_image(mermaid_code):
    encoded_string = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
    url = f"https://mermaid.ink/img/{encoded_string}?type=png"
    return url

async def convert_markdown(md_path, out_pdf):
    out_dir = os.path.dirname(os.path.abspath(out_pdf))
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r"```mermaid\n(.*?)\n```"
    
    def replacer(match):
        mermaid_code = match.group(1).strip()
        img_url = mermaid_to_image(mermaid_code)
        print(f"Downloading chart: {img_url}")
        
        try:
            img_data = requests.get(img_url).content
            img_name = f"mermaid_{abs(hash(mermaid_code))}.png"
            img_path = os.path.join(out_dir, img_name)
            with open(img_path, 'wb') as img_f:
                img_f.write(img_data)
            
            # Use absolute file UI for HTML rendering
            return f'<img src="file:///{img_path.replace(chr(92), "/")}" style="max-width: 100%; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 20px 0;" />'
        except Exception as e:
            print(f"Error downloading image: {e}")
            return "*(Mermaid chart could not be loaded)*"

    print("Extracting Mermaid blocks and downloading images...")
    processed_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    # Convert MD to HTML
    print("Converting Markdown to HTML...")
    # Add some basic GitHub-like CSS
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; line-height: 1.6; color: #24292e; max-width: 900px; margin: 0 auto; padding: 40px; }}
            h1, h2, h3 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; margin-bottom: 16px; }}
            code {{ font-family: SFMono-Regular,Consolas,"Liberation Mono",Menlo,monospace; background-color: rgba(27,31,35,0.05); padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%; }}
            pre {{ background-color: #f6f8fa; padding: 16px; border-radius: 3px; overflow: auto; }}
            pre code {{ background-color: transparent; padding: 0; }}
            table {{ border-spacing: 0; border-collapse: collapse; margin-top: 0; margin-bottom: 16px; width: 100%; }}
            table th, table td {{ padding: 6px 13px; border: 1px solid #dfe2e5; }}
            table th {{ background-color: #f6f8fa; font-weight: 600; }}
            table tr:nth-child(2n) {{ background-color: #f6f8fa; }}
            blockquote {{ padding: 0 1em; color: #6a737d; border-left: 0.25em solid #dfe2e5; margin: 0 0 16px 0; }}
        </style>
    </head>
    <body>
        {markdown.markdown(processed_content, extensions=['tables', 'fenced_code'])}
    </body>
    </html>
    """
    
    temp_html = os.path.join(out_dir, "temp_walkthrough.html")
    with open(temp_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print("Using Playwright to render PDF...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Navigate using file URI
        file_uri = f"file:///{temp_html.replace(chr(92), '/')}"
        await page.goto(file_uri, wait_until="networkidle")
        await page.pdf(path=out_pdf, format="Letter", print_background=True, margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"})
        await browser.close()
        
    print(f"Done! PDF saved to: {out_pdf}")

if __name__ == "__main__":
    md_in = r"C:\Users\Husse\.gemini\antigravity\brain\4e557e0f-8a76-4864-82ac-8d0061186d12\walkthrough.md"
    pdf_out = r"c:\Users\Husse\Documents\TexasEquityAI\outputs\Texas_Equity_AI_Logic_Walkthrough_Visual.pdf"
    os.makedirs(os.path.dirname(pdf_out), exist_ok=True)
    asyncio.run(convert_markdown(md_in, pdf_out))
