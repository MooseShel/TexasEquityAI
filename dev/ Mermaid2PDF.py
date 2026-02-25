import re
import base64
import requests
import os
import subprocess

def mermaid_to_image(mermaid_code):
    """Convert Mermaid code to a base64 string to use with mermaid.ink API"""
    encoded_string = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
    url = f"https://mermaid.ink/img/{encoded_string}"
    return url

def convert_markdown(md_path, out_pdf):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all mermaid code blocks
    pattern = r"```mermaid\n(.*?)\n```"
    
    def replacer(match):
        mermaid_code = match.group(1).strip()
        img_url = mermaid_to_image(mermaid_code)
        # Download the image to a local file
        img_data = requests.get(img_url).content
        img_name = f"mermaid_{hash(mermaid_code)}.png"
        img_path = os.path.join(os.path.dirname(out_pdf), img_name)
        with open(img_path, 'wb') as img_f:
            img_f.write(img_data)
        
        return f"![Mermaid Diagram]({img_name})"

    # Replace mermaid blocks with image links
    processed_content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    temp_md = os.path.join(os.path.dirname(out_pdf), "temp_walkthrough.md")
    with open(temp_md, 'w', encoding='utf-8') as f:
        f.write(processed_content)
        
    print(f"Generated intermediate markdown: {temp_md}")
    
    # Run mdpdf on the intermediate markdown
    cmd = f'mdpdf -o "{out_pdf}" "{temp_md}"'
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)
    print("Done!")

if __name__ == "__main__":
    md_in = r"C:\Users\Husse\.gemini\antigravity\brain\4e557e0f-8a76-4864-82ac-8d0061186d12\walkthrough.md"
    pdf_out = r"c:\Users\Husse\Documents\TexasEquityAI\outputs\Texas_Equity_AI_Logic_Walkthrough_Visual.pdf"
    os.makedirs(os.path.dirname(pdf_out), exist_ok=True)
    convert_markdown(md_in, pdf_out)
