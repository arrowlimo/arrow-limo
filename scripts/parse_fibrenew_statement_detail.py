#!/usr/bin/env python3
"""
Parse the Fibrenew statement screenshot in detail.

CRITICAL OBSERVATION: The AMOUNT and OPEN ACCOUNT columns are IDENTICAL,
showing all invoices as fully paid. But the aging summary shows $14,734.56 owed.

This is inconsistent and suggests either:
1. The statement is incorrectly formatted/exported
2. The "OPEN ACCOUNT" column doesn't mean what we think
3. There's an aging calculation error

Let me extract all visible transactions to analyze.
"""
from decimal import Decimal

# Page 1 visible transactions (2019-2020)
page1_transactions = [
    ('2019-01-02', 'Invoice #8696', Decimal('301.48'), Decimal('193.84')),
    ('2019-01-23', 'Invoice #8693', Decimal('682.50'), Decimal('682.50')),
    ('2019-01-30', 'Invoice #8697', Decimal('946.98'), Decimal('946.98')),
    ('2019-03-08', 'Invoice #8765', Decimal('682.50'), Decimal('682.50')),
    ('2019-07-05', 'Invoice #8890', Decimal('295.69'), Decimal('295.69')),
    ('2019-07-05', 'Invoice #8891', Decimal('682.50'), Decimal('682.50')),
    ('2019-07-31', 'Invoice #8743', Decimal('682.50'), Decimal('682.50')),
    ('2019-08-31', 'Invoice #8744', Decimal('254.32'), Decimal('254.32')),
    ('2019-09-01', 'Invoice #8932', Decimal('682.50'), Decimal('682.50')),
    ('2019-11-07', 'Invoice #8933', Decimal('153.13'), Decimal('153.13')),
    ('2019-06-06', 'Invoice #8894', Decimal('144.89'), Decimal('144.89')),
    ('2019-06-06', 'Invoice #8895', Decimal('682.50'), Decimal('682.50')),
    ('2019-04-09', 'Invoice #8942', Decimal('682.50'), Decimal('682.50')),
    ('2019-04-09', 'Invoice #8943', Decimal('183.91'), Decimal('183.91')),
    ('2019-01-10', 'Invoice #8979', Decimal('682.50'), Decimal('682.50')),
    ('2019-01-10', 'Invoice #8980', Decimal('152.62'), Decimal('152.62')),
    ('2019-01-11', 'Invoice #9325', Decimal('163.46'), Decimal('163.46')),
    ('2019-06-11', 'Invoice #9066', Decimal('682.50'), Decimal('682.50')),
    ('2019-06-11', 'Invoice #9067', Decimal('157.88'), Decimal('157.88')),
    ('2019-08-12', 'Invoice #9103', Decimal('126.60'), Decimal('126.60')),
    ('2019-01-01', 'Invoice #9135', Decimal('682.50'), Decimal('682.50')),
    ('2020-08-01', 'Invoice #9139', Decimal('190.20'), Decimal('190.20')),
    ('2020-08-31', 'Invoice #9239', Decimal('682.50'), Decimal('682.50')),
    ('2020-02-14', 'Invoice #5001', Decimal('228.12'), Decimal('228.12')),
    ('2020-02-03', 'Invoice #9239', Decimal('682.50'), Decimal('682.50')),
    ('2020-03-30', 'Invoice #0288', Decimal('304.47'), Decimal('304.47')),
]

page1_bottom_transactions = [
    ('2020-01-04', 'Invoice #9287', Decimal('682.50'), Decimal('682.50')),
    ('2020-04-14', 'Invoice #9326', Decimal('199.26'), Decimal('199.26')),
    ('2020-06-23', 'Invoice #9390', Decimal('156.64'), Decimal('156.64')),
    ('2020-02-07', 'Invoice #9407', Decimal('840.00'), Decimal('840.00')),
    ('2020-07-22', 'Invoice #9436', Decimal('134.81'), Decimal('134.81')),
    ('2020-08-05', 'Invoice #9490', Decimal('840.00'), Decimal('840.00')),
]

all_visible_invoices = page1_transactions + page1_bottom_transactions

print("\n" + "="*100)
print("FIBRENEW STATEMENT ANALYSIS")
print("="*100)

print("\n📋 VISIBLE INVOICES FROM STATEMENT:")
print("-" * 100)
print(f"{'Date':<12} {'Invoice':<20} {'Amount':>12} {'Open Account':>15}")
print("-" * 100)

total_amount = Decimal('0')
total_open = Decimal('0')

for date, inv, amount, open_acct in all_visible_invoices:
    print(f"{date:<12} {inv:<20} ${amount:>10,.2f} ${open_acct:>12,.2f}")
    total_amount += amount
    total_open += open_acct

print("-" * 100)
print(f"{'TOTALS':<32} ${total_amount:>10,.2f} ${total_open:>12,.2f}")

print("\n" + "="*100)
print("KEY OBSERVATIONS:")
print("="*100)

print("\n1. AMOUNT vs OPEN ACCOUNT columns:")
print(f"   Total invoiced: ${total_amount:,.2f}")
print(f"   Total shown as 'open': ${total_open:,.2f}")
print(f"   Difference: ${abs(total_amount - total_open):,.2f}")

if total_amount == total_open:
    print("   ⚠️  IDENTICAL - This suggests NO payments were applied to these invoices")
    print("      OR the 'OPEN ACCOUNT' column is mislabeled")

print("\n2. Statement aging summary shows:")
print("   Current Due: $1,260.00")
print("   1-30 Days Past Due: $160.00")
print("   31-60 Days Past Due: -$740.00 (CREDIT)")
print("   61-90 Days Past Due: $760.00")
print("   90+ Days Past Due: $13,294.56")
print("   TOTAL: $14,734.56")

print("\n3. Math check:")
aging_total = Decimal('1260.00') + Decimal('160.00') - Decimal('740.00') + Decimal('760.00') + Decimal('13294.56')
print(f"   1,260.00 + 160.00 - 740.00 + 760.00 + 13,294.56 = ${aging_total:,.2f}")
print(f"   Statement shows: $14,734.56")
print(f"   ✓ MATCHES" if aging_total == Decimal('14734.56') else f"   ✗ DISCREPANCY")

print("\n" + "="*100)
print("CONCLUSION:")
print("="*100)
print("""
The statement appears to be an INVOICE LISTING, not a balance report.
The 'OPEN ACCOUNT' column shows the invoice amounts, not outstanding balances.

The actual outstanding balance is shown in the AGING SUMMARY: $14,734.56

This means:
1. These are ALL unpaid/partially-paid invoices
2. The statement is NOT showing payment history
3. We need to track the $14,734.56 as the true amount owed

The database calculation of $37,992.26 is based on:
- Opening balance $16,119.69
- Plus all monthly charges
- Minus all payments we've recorded

The $23,257.70 difference suggests either:
A) Opening balance is wrong (should be much lower)
B) We're missing payment records
C) There were credits/write-offs not in our system
""")

print("\n" + "="*100)
