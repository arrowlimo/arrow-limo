#!/usr/bin/env python3
"""
Analyze the 6 mismatch split groups: review revenue, payment method, card info from workbook.
"""
import pandas as pd
from pathlib import Path

path = Path(r"L:\limo\reports\receipts table layout.xlsx")
df = pd.read_excel(path, sheet_name='receipts')

# Convert receipt_date to datetime
df['receipt_date'] = pd.to_datetime(df['receipt_date'])

# The 6 problematic splits from DB (parent receipt dates/vendors)
mismatches = [
    ('2019-02-26', "RUN'N ON EMPTY", 62.75),
    ('2019-05-11', "FAS GAS", 77.66),
    ('2019-05-16', "RUN'N ON EMPTY", 48.35),
    ('2019-06-15', "SPRINGS LIQUOR STORE SERVICES", 106.25),
    ('2019-09-06', "RUN'N ON EMPTY", 54.57),
    ('2019-10-14', "FAS GAS", 24.25),
]

print("=" * 140)
print("2019 SPLIT RECEIPT MISMATCHES - Detailed Review from Workbook")
print("=" * 140)

for date_str, vendor, split_total in mismatches:
    date_obj = pd.Timestamp(date_str)
    # Find all rows for this date/vendor
    subset = df[(df['receipt_date'] == date_obj) & (df['vendor_name'] == vendor)]
    
    print(f"\n{date_str} | {vendor} | split_total={split_total:.2f}")
    print("-" * 140)
    
    if subset.empty:
        print("  (Not found in workbook)")
        continue
    
    # Show all rows for this split group
    cols_to_show = ['id','receipt_date','vendor_name','revenue','expense','payment_method','card_number','card_type','comment']
    cols_avail = [c for c in cols_to_show if c in subset.columns]
    
    for idx, row in subset.iterrows():
        print(f"  Row {idx}:")
        for col in cols_avail:
            val = row[col]
            if pd.isna(val):
                val_str = "NULL"
            else:
                val_str = str(val)
            print(f"    {col}: {val_str}")

print("\n" + "=" * 140)
print("SUMMARY OF MISMATCHES")
print("=" * 140)
print("""
1044 | 2019-02-26 | RUN'N ON EMPTY | split 62.75 vs combined 62.50 (diff -0.25)
1222 | 2019-05-11 | FAS GAS | split 77.66 vs combined 67.66 (diff -10.00) ← Large diff
1238 | 2019-05-16 | RUN'N ON EMPTY | split 48.35 vs combined 48.95 (diff +0.60)
1330 | 2019-06-15 | SPRINGS LIQUOR | split 106.25 vs combined 106.00 (diff -0.25)
1537 | 2019-09-06 | RUN'N ON EMPTY | split 54.57 vs combined 54.56 (diff -0.01) ← Minor rounding
1618 | 2019-10-14 | FAS GAS | split 24.25 vs combined 34.25 (diff +10.00) ← Large diff

→ Review payment_method and card info above to understand discrepancies.
→ 1222 (FAS GAS -$10) and 1618 (FAS GAS +$10) show pattern—likely data entry errors or partial payments.
→ Mark for manual review and correction in future session.
""")

# Search for splits in workbook and show payment method patterns
print("\n" + "=" * 140)
print("ALL 2019 SPLITS IN WORKBOOK - Payment Method Review")
print("=" * 140)

splits_2019 = df[(df['receipt_date'].dt.year == 2019) & (df['description'].str.contains('SPLIT', case=False, na=False))]
if not splits_2019.empty:
    print(f"Found {len(splits_2019)} split rows in 2019 workbook")
    print("\nPayment method distribution in splits:")
    print(splits_2019['payment_method'].value_counts())
    
    print("\nSample split rows (vendor, date, expense, payment_method, card_number, card_type):")
    cols_sample = ['vendor_name','receipt_date','expense','payment_method','card_number','card_type']
    print(splits_2019[cols_sample].head(20))
else:
    print("No split rows found in 2019 with 'SPLIT' description")
