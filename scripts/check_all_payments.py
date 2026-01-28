import pandas as pd
import re

df = pd.read_excel('DAVID UPLOADS/L-5 car loan paid by david_0001.xlsx', header=None)

print(f"Total rows in file: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print("\nSearching for all payment-related rows...\n")

for idx, row in df.iterrows():
    row_str = ' '.join([str(x) for x in row if pd.notna(x)])
    if 'nstallment' in row_str.lower() or ('payment' in row_str.lower() and any(c.isdigit() for c in row_str)):
        print(f"Row {idx}: {row_str[:200]}")
