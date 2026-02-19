with open(r"C:\Users\Husse\Documents\TexasEquityAI\hcad_2025_data\real_acct.txt", "r", encoding="latin-1") as f:
    header = f.readline().strip().split("\t")
    row1 = f.readline().strip().split("\t")
    row2 = f.readline().strip().split("\t")

print("Columns:", header)
print("\nRow 1:")
for col, val in zip(header, row1):
    print(f"  {col}: {repr(val.strip())}")
