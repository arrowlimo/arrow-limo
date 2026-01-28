#!/usr/bin/env python3
"""Check how auto loans and NSF fees are currently categorized."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

# Check receipts for loan and NSF patterns
print("\n" + "="*80)
print("AUTO LOAN & NSF FEE CATEGORIZATION IN RECEIPTS")
print("="*80)

cur.execute("""
    SELECT category, COUNT(*) as count, 
           SUM(gross_amount) as total, 
           SUM(gst_amount) as gst,
           MAX(CASE WHEN gst_amount > 0 THEN 1 ELSE 0 END)::boolean as has_gst
    FROM receipts 
    WHERE LOWER(vendor_name) LIKE '%loan%' 
       OR LOWER(vendor_name) LIKE '%nsf%'
       OR LOWER(description) LIKE '%loan%'
       OR LOWER(description) LIKE '%nsf%'
       OR LOWER(description) LIKE '%financing%'
       OR LOWER(vendor_name) LIKE '%heffner%'
       OR LOWER(vendor_name) LIKE '%woodridge%'
    GROUP BY category 
    ORDER BY total DESC
""")

rows = cur.fetchall()
print(f"\n{'Category':<30} {'Count':>8} {'Total Amount':>15} {'GST':>12} {'Taxable'}")
print("-"*75)
total_amount = 0
total_gst = 0
for r in rows:
    category = r[0] or 'UNCATEGORIZED'
    print(f"{category:<30} {r[1]:>8,} ${r[2]:>13,.2f} ${r[3]:>10,.2f} {r[4]}")
    total_amount += float(r[2])
    total_gst += float(r[3])

print("-"*75)
print(f"{'TOTAL':<30} {' ':>8} ${total_amount:>13,.2f} ${total_gst:>10,.2f}")

# Sample some loan transactions
print("\n" + "="*80)
print("SAMPLE LOAN TRANSACTIONS")
print("="*80)
cur.execute("""
    SELECT receipt_date, vendor_name, gross_amount, gst_amount, category, description
    FROM receipts 
    WHERE LOWER(vendor_name) LIKE '%loan%' 
       OR LOWER(vendor_name) LIKE '%heffner%'
       OR LOWER(vendor_name) LIKE '%woodridge%'
    ORDER BY gross_amount DESC
    LIMIT 20
""")

rows = cur.fetchall()
print(f"\n{'Date':<12} {'Vendor':<30} {'Amount':>12} {'GST':>10} {'Category':<20}")
print("-"*95)
for r in rows:
    category = r[4] or 'UNCATEGORIZED'
    vendor = (r[1] or '')[:30]
    print(f"{r[0]} {vendor:<30} ${r[2]:>10,.2f} ${r[3]:>8,.2f} {category:<20}")

# Sample NSF transactions
print("\n" + "="*80)
print("SAMPLE NSF FEE TRANSACTIONS")
print("="*80)
cur.execute("""
    SELECT receipt_date, vendor_name, gross_amount, gst_amount, category, description
    FROM receipts 
    WHERE LOWER(vendor_name) LIKE '%nsf%'
       OR LOWER(description) LIKE '%nsf%'
    ORDER BY receipt_date DESC
    LIMIT 20
""")

rows = cur.fetchall()
if rows:
    print(f"\n{'Date':<12} {'Vendor':<30} {'Amount':>12} {'GST':>10} {'Category':<20}")
    print("-"*95)
    for r in rows:
        category = r[4] or 'UNCATEGORIZED'
        vendor = (r[1] or '')[:30]
        print(f"{r[0]} {vendor:<30} ${r[2]:>10,.2f} ${r[3]:>8,.2f} {category:<20}")
else:
    print("\nNo NSF fee transactions found in receipts")

# Check banking for NSF
print("\n" + "="*80)
print("NSF IN BANKING TRANSACTIONS")
print("="*80)
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions 
    WHERE LOWER(description) LIKE '%nsf%'
    ORDER BY transaction_date DESC
    LIMIT 20
""")

rows = cur.fetchall()
if rows:
    print(f"\n{'Date':<12} {'Description':<60} {'Debit':>12} {'Credit':>12}")
    print("-"*100)
    for r in rows:
        print(f"{r[0]} {r[1][:60]:<60} ${r[2] or 0:>10,.2f} ${r[3] or 0:>10,.2f}")
else:
    print("\nNo NSF transactions found in banking")

cur.close()
conn.close()

print("\n" + "="*80)
print("ANALYSIS:")
print("="*80)
print("""
CRA TAX TREATMENT:

AUTO LOANS:
- Loan PRINCIPAL payments: NOT deductible, NOT expensed
- Loan INTEREST payments: DEDUCTIBLE business expense
- GST on loan payments: NO GST (financial services exempt)
- Should be categorized as: 'loan_principal' (not expensed) or 'loan_interest' (expensed)

NSF FEES:
- Bank NSF fees: DEDUCTIBLE business expense
- No GST on bank fees (financial services exempt)
- Should be categorized as: 'bank_fee' (deductible)

CURRENT ISSUE:
If loans are being treated as regular expenses with GST, this inflates ITCs claimed.
Need to separate:
1. Loan principal (not deductible, no GST)
2. Loan interest (deductible, no GST)
3. NSF fees (deductible, no GST)
""")
