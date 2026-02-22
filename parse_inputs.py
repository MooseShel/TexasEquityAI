from html.parser import HTMLParser

class InputParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag in ('input', 'button'):
            d = dict(attrs)
            print(f"{tag} type={d.get('type','')} class={d.get('class','')} text=")
    def handle_data(self, data):
        if data.strip():
            print(f"  text: {data.strip()}")

parser = InputParser()
with open('debug/form_dump.html', 'r', encoding='utf-8') as f:
    parser.feed(f.read())
