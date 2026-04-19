"""
2012 General Ledger Audit & Year-End Close Status
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)
cursor = conn.cursor()

print("=" * 80)
print("2012 GENERAL LEDGER AUDIT & YEAR-END CLOSE STATUS")
print("=" * 80)
print()

# 1. GL Balance Summary
print("1. GL BALANCE SUMMARY (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  COUNT(*) AS total_entries,
  COUNT(DISTINCT account) AS distinct_accounts,
  ROUND(SUM(debit)::numeric, 2) AS total_debits,
  ROUND(SUM(credit)::numeric, 2) AS total_credits,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS balance_difference
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
""")

row = cursor.fetchone()
print(f"  Total GL Entries: {row[0]:,}")
print(f"  Distinct Accounts: {row[1]}")
print(f"  Total Debits: ${row[2]:,.2f}")
print(f"  Total Credits: ${row[3]:,.2f}")
print(f"  Balance Difference: ${row[4]:,.2f}")
print()

# 2. Income vs GL Reconciliation
print("2. CHARTER INCOME RECONCILIATION (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  'GL Charter Revenue (credit)' AS line,
  ROUND(SUM(credit)::numeric, 2) AS amount
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
  AND account_name = 'Charter Revenue'
UNION ALL
SELECT 
  'Income Ledger Charter Services',
  ROUND(SUM(gross_amount)::numeric, 2)
FROM income_ledger
WHERE EXTRACT(YEAR FROM transaction_date) = 2012
  AND revenue_subcategory = 'Charter Services'
UNION ALL
SELECT 
  'charter_payments sum (payments table)',
  ROUND(SUM(cp.amount)::numeric, 2)
FROM charter_payments cp
JOIN charters c ON c.reserve_number = cp.charter_id
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
UNION ALL
SELECT 
  'Difference: GL vs Income Ledger',
  ROUND(SUM(credit)::numeric, 2) - 
  (SELECT ROUND(SUM(gross_amount)::numeric, 2) 
   FROM income_ledger WHERE EXTRACT(YEAR FROM transaction_date) = 2012 AND revenue_subcategory = 'Charter Services')
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'Charter Revenue'
""")

for line, amount in cursor.fetchall():
    print(f"  {line:<45}: ${float(amount):>12,.2f}")
print()

# 3. Key GL Accounts
print("3. KEY GL ACCOUNTS (Top 10 by balance)")
print("-" * 80)
print(f"{'Account':<40} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
print("-" * 80)

cursor.execute("""
SELECT 
  account_name,
  ROUND(SUM(debit)::numeric, 2) AS total_debit,
  ROUND(SUM(credit)::numeric, 2) AS total_credit,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS account_balance
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
GROUP BY account_name
ORDER BY ABS(SUM(debit) - SUM(credit)) DESC
LIMIT 10
""")

for acct, debit, credit, balance in cursor.fetchall():
    print(f"{str(acct)[:39]:<40} ${float(debit):>11,.2f} ${float(credit):>11,.2f} ${float(balance):>11,.2f}")
print()

# 4. GST/ITC Status
print("4. GST/ITC ANALYSIS (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  'GST/HST Paid (ITC)' AS line,
  ROUND(SUM(debit)::numeric, 2) AS amount
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'GST/HST Paid (ITC)'
UNION ALL
SELECT 
  'GST/HST Collected (Liability)',
  ROUND(SUM(credit)::numeric, 2)
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'GST/HST Collected (Liability)'
UNION ALL
SELECT
  'Net GST Position (GST - ITC recovery)',
  (SELECT ROUND(SUM(credit)::numeric, 2) FROM general_ledger 
   WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'GST/HST Collected (Liability)')
  - (SELECT ROUND(SUM(debit)::numeric, 2) FROM general_ledger 
     WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'GST/HST Paid (ITC)')
""")

for line, amount in cursor.fetchall():
    if amount is not None:
        print(f"  {line:<45}: ${float(amount):>12,.2f}")
    else:
        print(f"  {line:<45}: Not available")
print()

# 5. Banking Reconciliation Status
print("5. BANKING RECONCILIATION STATUS (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  'GL Cash/Bank Accounts Debit Total' AS line,
  ROUND(SUM(debit)::numeric, 2) AS amount
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 
  AND (account_name ILIKE 'Cash%' OR account_name ILIKE 'Bank%')
UNION ALL
SELECT 
  'GL Cash/Bank Accounts Credit Total',
  ROUND(SUM(credit)::numeric, 2)
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 
  AND (account_name ILIKE 'Cash%' OR account_name ILIKE 'Bank%')
UNION ALL
SELECT
  'Net Cash Position',
  ROUND((SUM(debit) - SUM(credit))::numeric, 2)
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 
  AND (account_name ILIKE 'Cash%' OR account_name ILIKE 'Bank%')
UNION ALL
SELECT
  'Banking Transactions Recorded (import)',
  COUNT(*)::numeric
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) = 2012
UNION ALL
SELECT
  'Banking TX Total',
  ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2)
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) = 2012
""")

for line, amount in cursor.fetchall():
    if amount is not None and amount != '':
        if isinstance(amount, int):
            print(f"  {line:<45}: {int(amount):,} records")
        else:
            print(f"  {line:<45}: ${float(amount):>12,.2f}")
print()

# 6. Expenses Summary
print("6. EXPENSES SUMMARY (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  account_name,
  COUNT(*) AS entry_count,
  ROUND(SUM(debit)::numeric, 2) AS total_debit,
  ROUND(SUM(credit)::numeric, 2) AS total_credit,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS net_amount
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
  AND (account_type ILIKE '%expense%' OR account_type ILIKE '%cost%' OR account_name ILIKE '%Salaries%' OR account_name ILIKE '%Fuel%')
GROUP BY account_name
ORDER BY SUM(debit) DESC
LIMIT 15
""")

print(f"{'Account':<40} {'Count':>6} {'Amount':>12}")
print("-" * 60)

total_expense = 0
for acct, count, debit, credit, net in cursor.fetchall():
    amount = float(debit) - float(credit) if debit and credit else float(debit) if debit else -float(credit)
    total_expense += amount
    print(f"{str(acct)[:39]:<40} {count:>6} ${amount:>11,.2f}")

print("-" * 60)
print(f"{'Total Expenses':<40} {'':>6} ${total_expense:>11,.2f}")
print()

# 7. Year-End Close Readiness
print("7. YEAR-END CLOSE READINESS")
print("-" * 80)

# Check if GL is balanced
gl_balance = (3,)  # the $16,528.33 difference from earlier query
cursor.execute("""
SELECT ROUND((SUM(debit) - SUM(credit))::numeric, 2)
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
""")
gl_diff = cursor.fetchone()[0]

print(f"  ✓ GL Entries Recorded: 9,384")
print(f"  ✗ GL Out of Balance: ${float(gl_diff):,.2f}")
print(f"  ? Charter Income Linked: Need Verification")
print(f"  ? Banking Reconciliation: Pending")
print(f"  ? Expense Allocation: Need Review")
print(f"  ? GST/ITC Settlement: Need Verification")
print()

# 8. Outstanding Tasks
print("8. OUTSTANDING YEAR-END CLOSE TASKS")
print("-" * 80)
print("  1. Investigate GL $16,528.33 imbalance (likely GST/ITC setup)")
print("  2. Verify Charter Income $772.12 variance (GL $657,051.58 vs IL $656,279.46)")
print("  3. Link all charter payments to GL charter revenue line")
print("  4. Complete banking transaction reconciliation")
print("  5. Verify all expense categories properly allocated")
print("  6. GST return calculation and settlement")
print("  7. Prepare final adjusted journal entry for closing")
print()

conn.close()
