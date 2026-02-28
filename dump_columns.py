import json
with open('bcad_layout.json') as f: data = json.load(f)
for field in data['INFO']:
    name = field['field'].lower()
    if 'situs' in name or 'owner' in name:
        print(f"{field['field']}: {field['start']-1}:{field['end']} - {field['desc'][:40]}")
