import pandas as pd
from pathlib import Path

path = Path(r"L:\limo\reports\receipts table layout.xlsx")
xl = pd.ExcelFile(path)
print("Sheets:", xl.sheet_names)
for name in xl.sheet_names:
    df = xl.parse(name)
    print(f"\n=== {name} ===")
    print("Columns:", list(df.columns))
    print(df.head(10))

# Show rows with non-empty comment for receipts sheet
if 'receipts' in xl.sheet_names:
    df = xl.parse('receipts')
    comm = df[df['comment'].notna()]
    print(f"\nRows with comment: {len(comm)} of {len(df)}")
    cols = [c for c in ['id','receipt_date','vendor_name','expense','gross_amount','comment'] if c in comm.columns]
    print(comm[cols].head(40))

    # Focused view: comments mentioning CASH/PAID
    cash = comm[comm['comment'].str.contains('CASH', case=False, na=False)]
    if not cash.empty:
        print("\nComments mentioning CASH/PAID (first 40):")
        cols_cash = [c for c in ['id','receipt_date','vendor_name','expense','gross_amount','comment'] if c in cash.columns]
        print(cash[cols_cash].head(40))
        print("\nDetailed rows (index, date, vendor, expense, comment) for first 20:")
        for idx, row in cash.head(20).iterrows():
            print(f"idx={idx} | date={row.get('receipt_date')} | vendor={row.get('vendor_name')} | expense={row.get('expense')} | comment={row.get('comment')}")

    # Specific: PLENTY OF LIQUOR rows in 2019 with comments
    pol = df[(df['vendor_name'] == 'PLENTY OF LIQUOR') & (df['receipt_date'].dt.year == 2019)]
    if not pol.empty:
        print("\nPLENTY OF LIQUOR 2019 rows (with comments):")
        cols_pol = [c for c in ['id','receipt_date','vendor_name','expense','comment'] if c in pol.columns]
        print(pol[cols_pol])
