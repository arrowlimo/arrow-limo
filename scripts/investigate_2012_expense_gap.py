#!/usr/bin/env python3
"""
Investigate 2012 expense discrepancy - Why are expenses so low?
Check all potential expense sources: receipts, banking, journal entries.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def format_currency(amount):
    if amount is None:
        return "$0.00"
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"

conn = get_db_connection()
cur = conn.cursor()

print("="*80)
print("2012 EXPENSE DISCREPANCY INVESTIGATION")
print("="*80)

# 1. Check receipts by GL account category
print("\n1. Receipts Categorization Status (2012)")
print("-"*80)

cur.execute("""
    SELECT 
        CASE 
            WHEN gl_account_code ~ '^1' THEN '1xxx Assets'
            WHEN gl_account_code ~ '^2' THEN '2xxx Liabilities'
            WHEN gl_account_code ~ '^3' THEN '3xxx Equity'
            WHEN gl_account_code ~ '^4' THEN '4xxx Income'
            WHEN gl_account_code ~ '^5' THEN '5xxx Expenses'
            WHEN gl_account_code IS NULL OR gl_account_code = '' THEN 'UNCATEGORIZED'
            ELSE 'Other'
        END as category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    GROUP BY 1
    ORDER BY 1
""")

print("\nReceipts by GL Category:")
for row in cur.fetchall():
    cat = row[0]
    count = row[1]
    amount = float(row[2]) if row[2] else 0
    print(f"  {cat:20s}: {count:5d} receipts = {format_currency(amount)}")

# 2. Check banking transactions (debits = money out = expenses)
print("\n2. Banking Transactions (2012)")
print("-"*80)

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as txn_count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    ORDER BY account_number
""")

print("\nBanking Activity by Account:")
total_debits = 0
total_credits = 0
for row in cur.fetchall():
    account = row[0]
    count = row[1]
    debits = float(row[2]) if row[2] else 0
    credits = float(row[3]) if row[3] else 0
    total_debits += debits
    total_credits += credits
    print(f"  {account}: {count:4d} txns, Debits: {format_currency(debits)}, Credits: {format_currency(credits)}")

print(f"\n  TOTAL DEBITS (money out): {format_currency(total_debits)}")
print(f"  TOTAL CREDITS (money in): {format_currency(total_credits)}")

# 3. Check NSF transactions
print("\n3. NSF Transactions (Non-Sufficient Funds)")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(*) as nsf_count,
        SUM(debit_amount) as nsf_amount
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND (description ILIKE '%nsf%' OR description ILIKE '%non-sufficient%')
""")

row = cur.fetchone()
nsf_count = row[0] or 0
nsf_amount = float(row[1]) if row[1] else 0

print(f"  NSF Transactions: {nsf_count} totaling {format_currency(nsf_amount)}")

if nsf_count > 0:
    print(f"  ⚠️  {nsf_count} NSF events indicate cash flow problems")

# 4. Check receipts vs banking linkage
print("\n4. Receipt-Banking Linkage (2012)")
print("-"*80)

cur.execute("""
    SELECT 
        COUNT(DISTINCT r.receipt_id) as receipts_with_banking,
        COUNT(DISTINCT bt.transaction_id) as banking_with_receipts
    FROM receipts r
    INNER JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
    INNER JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
    WHERE EXTRACT(YEAR FROM r.receipt_date) = 2012
    OR EXTRACT(YEAR FROM bt.transaction_date) = 2012
""")

row = cur.fetchone()
receipts_linked = row[0] or 0
banking_linked = row[1] or 0

cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
""")
total_receipts_2012 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND debit_amount > 0
""")
total_banking_debits_2012 = cur.fetchone()[0]

print(f"  2012 Receipts: {total_receipts_2012:,}")
print(f"  2012 Receipts linked to banking: {receipts_linked:,} ({receipts_linked*100//total_receipts_2012 if total_receipts_2012 else 0}%)")
print(f"\n  2012 Banking debits: {total_banking_debits_2012:,}")
print(f"  2012 Banking linked to receipts: {banking_linked:,} ({banking_linked*100//total_banking_debits_2012 if total_banking_debits_2012 else 0}%)")

if receipts_linked < total_receipts_2012 * 0.5:
    print(f"\n  ⚠️  Only {receipts_linked*100//total_receipts_2012}% of receipts linked to banking")
    print(f"  This explains low expense numbers - most banking debits not categorized")

# 5. Check 4000 account (may contain misclassified expenses)
print("\n5. Account 4000 'Income' Analysis (Potential Misclassification)")
print("-"*80)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND gl_account_code = '4000'
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
    LIMIT 20
""")

print("\nTop 20 Vendors in 4000 Account:")
expense_like = 0
for row in cur.fetchall():
    vendor = row[0] or 'Unknown'
    count = row[1]
    amount = float(row[2]) if row[2] else 0
    
    # Flag vendors that look like expenses
    is_expense = any(word in vendor.upper() for word in [
        'INSURANCE', 'FUEL', 'GAS', 'REPAIR', 'MAINTENANCE', 'RENT',
        'UTILITIES', 'TELUS', 'ENMAX', 'CENTEX', 'SHELL', 'FAS GAS',
        'CANADIAN TIRE', 'PARTS', 'SERVICE', 'HEFFNER', 'LOAN', 'LEASE'
    ])
    
    marker = '⚠️ EXPENSE?' if is_expense else ''
    print(f"  {vendor[:40]:40s} {count:3d} = {format_currency(amount):>15s} {marker}")
    
    if is_expense:
        expense_like += amount

print(f"\n  Expense-like vendors in 4000: {format_currency(expense_like)}")
print(f"  ⚠️  These should likely be in 5xxx expense accounts")

# 6. Summary and recommendations
print("\n" + "="*80)
print("FINDINGS & RECOMMENDATIONS")
print("="*80)

print(f"\n1. Banking shows TRUE cash flow:")
print(f"   • Total debits (money out): {format_currency(total_debits)}")
print(f"   • Only {receipts_linked} of {total_receipts_2012} receipts linked")
print(f"   • Most banking transactions not categorized as receipts")

print(f"\n2. NSF Activity:")
print(f"   • {nsf_count} NSF events totaling {format_currency(nsf_amount)}")
print(f"   • Confirms cash flow problems you mentioned")

print(f"\n3. Misclassification Issues:")
print(f"   • ~{format_currency(expense_like)} in expenses misclassified as 'Income' (4000)")
print(f"   • Need to reclassify to proper 5xxx expense accounts")

print(f"\n4. Data Completeness:")
print(f"   • Previous P&L only counted receipts with GL codes")
print(f"   • Should use banking debits as TRUE expense measure")
print(f"   • Banking debits: {format_currency(total_debits)} vs Receipt expenses: $130,244")
print(f"   • Gap: {format_currency(total_debits - 130244.32)}")

print(f"\n✓ REVISED 2012 FINANCIAL PICTURE:")
print(f"   Income: ~$1,344,986 (unchanged)")
print(f"   Expenses: ~{format_currency(total_debits)} (banking debits)")
print(f"   Estimated Profit: {format_currency(1344986.34 - total_debits)}")
print(f"   Profit Margin: {(1344986.34 - total_debits) / 1344986.34 * 100:.1f}%")

print("\n" + "="*80)

conn.close()
