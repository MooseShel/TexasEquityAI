import pandas as pd
df = pd.read_csv('layout_full.csv')

def parse_layout(file_name_filter):
    # Find rows that start with 'File #'
    file_starts = df[df.iloc[:, 0].str.startswith('File #', na=False)].index.tolist()
    file_starts.append(len(df))

    for i in range(len(file_starts)-1):
        start = file_starts[i]
        end = file_starts[i+1]
        file_name = df.iloc[start, 0]
        
        if file_name_filter in file_name:
            print(f'\n--- {file_name} ---')
            sub_df = df.iloc[start:end].copy()
            header_idx = sub_df[sub_df.iloc[:, 0] == 'Field Name'].index
            if len(header_idx) > 0:
                h_idx = header_idx[0]
                fields = df.iloc[h_idx+1:end].dropna(subset=[df.columns[0]])
                for _, row in fields.iterrows():
                    print(f"{row.iloc[0]}: start={row.iloc[2]} end={row.iloc[3]} (Len {row.iloc[4]}) - {row.iloc[5]}")

parse_layout('APPRAISAL_INFO')
parse_layout('APPRAISAL_ENTITY_TOTALS')
parse_layout('APPRAISAL_IMPROVEMENT_DETAIL')
