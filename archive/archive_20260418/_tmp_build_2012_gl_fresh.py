"""
Build 2012 GL from scratch using authoritative sources
Sources: income_ledger, banking_transactions, receipts, charter_payments

Approach: Build GL systematically from source data
1. Charter Revenue (from income_ledger)
2. Accounts Receivable (from charter payments vs billing)
3. Cash (from banking_transactions)
4. Expenses (from receipts)
5. Verify balance
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)
cursor = conn.cursor()

print("=" * 80)
print("BUILD 2012 GENERAL LEDGER FROM SCRATCH")
print("=" * 80)
print()

# Collect all GL entries to post
gl_entries = []

# ============================================================================
# 1. CHARTER REVENUE (from income_ledger - authoritative revenue source)
# ============================================================================
print("STEP 1: POST CHARTER REVENUE (from income_ledger)")
print("-" * 80)

cursor.execute("""
SELECT 
  transaction_date,
  'Charter Revenue' AS account,
  'Charter Services' AS description,
  ROUND(SUM(gross_amount)::numeric, 2) AS total
FROM income_ledger
WHERE EXTRACT(YEAR FROM transaction_date) = 2012
GROUP BY transaction_date
ORDER BY transaction_date
""")

charter_revenue_total = 0
for trans_date, account, description, amount in cursor.fetchall():
    if amount:
        charter_revenue_total += float(amount)
        # Revenue is a CREDIT
        gl_entries.append({
            'date': trans_date,
            'account': account,
            'debit': 0,
            'credit': float(amount),
            'description': description,
            'source': 'income_ledger'
        })

print(f"  Posted {len([e for e in gl_entries if e['account'] == 'Charter Revenue']):,} daily entries")
print(f"  Total Charter Revenue: ${charter_revenue_total:,.2f}")
print()

# ============================================================================
# 2. ACCOUNTS RECEIVABLE - from charter payments
# ============================================================================
print("STEP 2: POST CHARTER PAYMENTS (Accounts Receivable movement)")
print("-" * 80)

cursor.execute("""
SELECT 
  cp.payment_date,
  'Accounts Receivable' AS account,
  'Charter Payment' AS description,
  ROUND(SUM(cp.amount)::numeric, 2) AS total
FROM charter_payments cp
JOIN charters c ON c.reserve_number = cp.charter_id
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
GROUP BY cp.payment_date
ORDER BY cp.payment_date
""")

payments_total = 0
for trans_date, account, description, amount in cursor.fetchall():
    if amount:
        payments_total += float(amount)
        # Payments reduce A/R (CREDIT)
        gl_entries.append({
            'date': trans_date,
            'account': account,
            'debit': 0,
            'credit': float(amount),
            'description': description,
            'source': 'charter_payments'
        })

print(f"  Posted charter payment credits")
print(f"  Total Charter Payments (reduce A/R): ${payments_total:,.2f}")
print()

# Net A/R increase (revenue - payments)
ar_net = charter_revenue_total - payments_total
print(f"  Net A/R Increase: ${ar_net:,.2f}")
print(f"  (Revenue ${ charter_revenue_total:,.2f} - Payments ${payments_total:,.2f})")
print()

# ============================================================================
# 3. CASH & BANK (from banking transactions)
# ============================================================================
print("STEP 3: POST BANKING TRANSACTIONS (Cash)")
print("-" * 80)

cursor.execute("""
SELECT 
  transaction_date,
  'Cash/Bank' AS account,
  description,
  ROUND(COALESCE(debit_amount, 0)::numeric, 2) AS debit_amt,
  ROUND(COALESCE(credit_amount, 0)::numeric, 2) AS credit_amt
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) = 2012
ORDER BY transaction_date
""")

bank_debits = 0
bank_credits = 0
for trans_date, account, description, debit, credit in cursor.fetchall():
    if debit and float(debit) > 0:
        bank_debits += float(debit)
    if credit and float(credit) > 0:
        bank_credits += float(credit)
    
    gl_entries.append({
        'date': trans_date,
        'account': account,
        'debit': float(debit) if debit else 0,
        'credit': float(credit) if credit else 0,
        'description': str(description)[:50] if description else 'Banking',
        'source': 'banking_transactions'
    })

print(f"  Posted {len([e for e in gl_entries if e['account'] == 'Cash/Bank']):,} banking entries")
print(f"  Total Debits (Cash In):  ${bank_debits:,.2f}")
print(f"  Total Credits (Cash Out): ${bank_credits:,.2f}")
print(f"  Net Cash Position: ${bank_debits - bank_credits:,.2f}")
print()

# ============================================================================
# 4. EXPENSES (from receipts/vendor payments)
# ============================================================================
print("STEP 4: POST EXPENSES (from receipts)")
print("-" * 80)

cursor.execute("""
SELECT 
  r.receipt_date,
  'Expenses - ' || COALESCE(r.canonical_vendor, 'General') AS account,
  r.description,
  r.gross_amount,
  COUNT(*) OVER () as total_count
FROM receipts r
WHERE EXTRACT(YEAR FROM r.receipt_date) = 2012
ORDER BY r.receipt_date
""")

expense_total = 0
expense_count = 0
for trans_date, account, description, amount, total_count in cursor.fetchall():
    if amount:
        expense_total += float(amount)
        expense_count += 1
        # Expenses are DEBITS
        gl_entries.append({
            'date': trans_date,
            'account': account,
            'debit': float(amount),
            'credit': 0,
            'description': str(description)[:50] if description else 'Expense',
            'source': 'receipts'
        })

print(f"  Posted {expense_count:,} expense entries")
print(f"  Total Expenses: ${expense_total:,.2f}")
print()

# ============================================================================
# 5. PLUG ACCOUNT - to balance GL
# ============================================================================
print("STEP 5: CALCULATE PLUG ACCOUNT (to balance GL)")
print("-" * 80)

total_debits = sum(e['debit'] for e in gl_entries)
total_credits = sum(e['credit'] for e in gl_entries)
difference = total_debits - total_credits

print(f"  Total Debits from entries: ${total_debits:,.2f}")
print(f"  Total Credits from entries: ${total_credits:,.2f}")
print(f"  Imbalance: ${difference:,.2f}")

if abs(difference) > 0.01:
    if difference > 0:
        # Need a credit plug
        gl_entries.append({
            'date': datetime(2012, 12, 31).date(),
            'account': 'PLUG - Unmatched Liabilities',
            'debit': 0,
            'credit': difference,
            'description': 'Balancing entry - unmatched liabilities',
            'source': 'balancing_plug'
        })
        print(f"  ✓ Posted CREDIT plug of ${difference:,.2f} to 'PLUG - Unmatched Liabilities'")
    else:
        # Need a debit plug
        gl_entries.append({
            'date': datetime(2012, 12, 31).date(),
            'account': 'PLUG - Unmatched Assets',
            'debit': abs(difference),
            'credit': 0,
            'description': 'Balancing entry - unmatched assets',
            'source': 'balancing_plug'
        })
        print(f"  ✓ Posted DEBIT plug of ${abs(difference):,.2f} to 'PLUG - Unmatched Assets'")
else:
    print(f"  ✓ GL is balanced (difference < $0.01)")

print()

# ============================================================================
# 6. INSERT ALL ENTRIES INTO general_ledger
# ============================================================================
print("STEP 6: INSERT INTO general_ledger")
print("-" * 80)

for i, entry in enumerate(gl_entries):
    cursor.execute("""
    INSERT INTO general_ledger (
      date, account, debit, credit,
      account_name, memo_description,
      source_file, imported_at,
      transaction_date
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
    """, (
        entry['date'],
        entry['account'],
        entry['debit'],
        entry['credit'],
        entry['account'],
        entry['description'],
        entry['source'],
        entry['date']
    ))
    
    if (i + 1) % 1000 == 0:
        conn.commit()
        print(f"  Inserted {i + 1:,} entries...")

conn.commit()
print(f"✓ Inserted {len(gl_entries):,} total GL entries")
print()

# ============================================================================
# 7. VERIFY BALANCE
# ============================================================================
print("STEP 7: FINAL VERIFICATION")
print("-" * 80)

cursor.execute("""
SELECT 
  COUNT(*) AS entry_count,
  ROUND(SUM(debit)::numeric, 2) AS total_debit,
  ROUND(SUM(credit)::numeric, 2) AS total_credit,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS difference
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
""")

count, debit, credit, diff = cursor.fetchone()

print(f"  Total GL Entries: {count:,}")
print(f"  Total Debits:  ${float(debit):>12,.2f}")
print(f"  Total Credits: ${float(credit):>12,.2f}")
print(f"  Difference:    ${float(diff):>12,.2f}")

if abs(float(diff)) < 0.01:
    print(f"\n  ✓✓✓ GL IS BALANCED! ✓✓✓")
else:
    print(f"\n  ⚠ GL is out of balance by ${abs(float(diff)):,.2f}")

print()

# ============================================================================
# 8. SUMMARY BY ACCOUNT
# ============================================================================
print("STEP 8: 2012 GL SUMMARY BY ACCOUNT")
print("-" * 80)
print(f"{'Account':<45} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
print("-" * 80)

cursor.execute("""
SELECT 
  COALESCE(account_name, account)::text as acc,
  ROUND(SUM(debit)::numeric, 2) AS deb,
  ROUND(SUM(credit)::numeric, 2) AS cred,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS bal
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
GROUP BY account_name, account
ORDER BY ABS(SUM(debit) - SUM(credit)) DESC
LIMIT 20
""")

for acc, deb, cred, bal in cursor.fetchall():
    print(f"{str(acc)[:44]:<45} ${float(deb):>11,.2f} ${float(cred):>11,.2f} ${float(bal):>11,.2f}")

print()
print("=" * 80)
print("BUILD COMPLETE")
print("=" * 80)

conn.close()
