"""
Properly extract and analyze Perron Ventures charter data from multiinvoice.xls
"""
import pandas as pd
from decimal import Decimal

print("="*80)
print("PERRON VENTURES CHARTER INVOICE ANALYSIS")
print("="*80)

# Read the Excel file
df = pd.read_excel(r'Z:\multiinvoice.xls', engine='xlrd')

# Find rows where column 9 contains "Perron Ventures Ltd."
perron_mask = df.iloc[:, 9].astype(str).str.contains('Perron Ventures Ltd', case=False, na=False)
charter_rows = df[perron_mask]

print(f"\n📋 Found {len(charter_rows)} Perron Ventures charter rows\n")

# Extract charter data
charters = []
for idx, row in charter_rows.iterrows():
    reserve_num = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None
    date = row.iloc[5]
    total = row.iloc[26] if pd.notna(row.iloc[26]) else 0
    
    if reserve_num and reserve_num != 'nan':
        charters.append({
            'row': idx,
            'reserve_number': reserve_num,
            'date': date,
            'total': Decimal(str(total))
        })

# Sort by reserve number
charters.sort(key=lambda x: x['reserve_number'])

print("CHARTER DETAILS:")
print("-" * 80)
print(f"{'Reserve':<10} {'Date':<12} {'Amount':>12}")
print("-" * 80)

total_amount = Decimal('0')
for charter in charters:
    total_amount += charter['total']
    date_str = str(charter['date'])[:10] if pd.notna(charter['date']) else 'N/A'
    print(f"{charter['reserve_number']:<10} {date_str:<12} ${charter['total']:>10,.2f}")

print("-" * 80)
print(f"{'TOTAL:':<10} {'':<12} ${total_amount:>10,.2f}")
print("-" * 80)
print()

# User's checks
check1_num = '004859'
check1_date = '2012-02-21'
check1_amt = Decimal('42940.00')

check2_num = '005094'
check2_date = '2012-04-17'
check2_amt = Decimal('15057.50')

total_checks = check1_amt + check2_amt

print("="*80)
print("PAYMENT COMPARISON")
print("="*80)
print(f"\n💰 USER'S CHECKS:")
print(f"  Check #{check1_num} ({check1_date}): ${check1_amt:>12,.2f}")
print(f"  Check #{check2_num} ({check2_date}): ${check2_amt:>12,.2f}")
print(f"  {'':>40} {'─'*15}")
print(f"  Total Checks:                      ${total_checks:>12,.2f}")
print()

print(f"📊 INVOICE COMPARISON:")
print(f"  Invoice Total (multiinvoice.xls):  ${total_amount:>12,.2f}")
print(f"  Check Total:                        ${total_checks:>12,.2f}")
diff = total_amount - total_checks
print(f"  {'':>40} {'─'*15}")
print(f"  Difference:                         ${diff:>12,.2f}")
print()

if abs(diff) < Decimal('1.00'):
    print("✅ AMOUNTS MATCH! Checks cover the invoice total.")
elif diff > 0:
    print(f"⚠️  INVOICE IS ${abs(diff):,.2f} HIGHER than checks")
    print("   Additional payment may be needed or charters should be reviewed.")
else:
    print(f"⚠️  CHECKS ARE ${abs(diff):,.2f} HIGHER than invoice")
    print("   Overpayment or additional charters may be included.")

print()
print("="*80)
print("CHARTER RANGE:")
print("="*80)
print(f"  Count:         {len(charters)} charters")
print(f"  First Charter: {charters[0]['reserve_number']}")
print(f"  Last Charter:  {charters[-1]['reserve_number']}")
print(f"  Date Range:    {str(charters[0]['date'])[:10]} to {str(charters[-1]['date'])[:10]}")
