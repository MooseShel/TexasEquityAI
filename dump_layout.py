import pandas as pd
import json

df = pd.read_csv('layout_full.csv')
file_starts = df[df.iloc[:, 0].str.startswith('File #', na=False)].index.tolist()
file_starts.append(len(df))

data = {}

for i in range(len(file_starts)-1):
    start = file_starts[i]
    end = file_starts[i+1]
    file_name = df.iloc[start, 0]
    
    if pd.isna(file_name): continue
    
    # We care about APPRAISAL_INFO and APPRAISAL_ENTITY_TOTALS
    if 'APPRAISAL_INFO.TXT' in file_name or 'APPRAISAL_ENTITY_TOTALS.TXT' in file_name:
        sub_df = df.iloc[start:end].copy()
        header_idx = sub_df[sub_df.iloc[:, 0] == 'Field Name'].index
        if len(header_idx) > 0:
            h_idx = header_idx[0]
            fields = df.iloc[h_idx+1:end].dropna(subset=[df.columns[0]])
            
            file_key = 'INFO' if 'APPRAISAL_INFO.TXT' in file_name else 'TOTALS'
            data[file_key] = []
            
            for _, row in fields.iterrows():
                try:
                    data[file_key].append({
                        "field": str(row.iloc[0]),
                        "start": int(row.iloc[2]),
                        "end": int(row.iloc[3]),
                        "len": int(row.iloc[4]),
                        "desc": str(row.iloc[5])
                    })
                except:
                    pass

with open('bcad_layout.json', 'w') as f:
    json.dump(data, f, indent=2)
