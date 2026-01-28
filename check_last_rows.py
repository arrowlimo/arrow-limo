import pandas as pd

df = pd.read_excel('L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx')

print(f"Total rows: {len(df)}")
print(f"\nLast 5 rows (2626-2630):")
print("="*100)

for idx in range(2626, min(2631, len(df))):
    row = df.iloc[idx]
    print(f"\nRow {idx}:")
    print(f"  date: {row['date']}")
    print(f"  Description: {row['Description']}")
    print(f"  debit/withdrawal: {row['debit/withdrawal']}")
    print(f"  deposit/credit: {row['deposit/credit']}")
    print(f"  balance: {row['balance']}")
