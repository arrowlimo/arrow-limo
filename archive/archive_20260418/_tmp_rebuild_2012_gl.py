"""
Rebuild 2012 General Ledger from authoritative sources
Objective: Clean GL with proper GST/ITC handling, balanced close
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)
cursor = conn.cursor()

print("=" * 80)
print("REBUILD 2012 GENERAL LEDGER")
print("=" * 80)
print()

# Step 1: Backup current GL
print("STEP 1: BACKUP CURRENT 2012 GL")
print("-" * 80)

cursor.execute("""
DROP TABLE IF EXISTS backup_general_ledger_2012_pre_rebuild_20260410;
CREATE TABLE backup_general_ledger_2012_pre_rebuild_20260410 AS
SELECT * FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012;
""")

cursor.execute("SELECT COUNT(*) FROM backup_general_ledger_2012_pre_rebuild_20260410")
backup_count = cursor.fetchone()[0]
print(f"✓ Backed up {backup_count:,} GL entries")
conn.commit()
print()

# Step 2: Delete 2012 GL entries
print("STEP 2: DELETE 2012 GL ENTRIES (from general_ledger)")
print("-" * 80)

cursor.execute("DELETE FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012")
cursor.execute("SELECT COUNT(*) FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012")
remaining = cursor.fetchone()[0]
print(f"✓ Deleted 2012 entries; remaining: {remaining}")
conn.commit()
print()

# Step 3: Rebuild GL from QB Journal Entries (authoritative source)
print("STEP 3: REBUILD 2012 GL FROM QB JOURNAL ENTRIES")
print("-" * 80)

cursor.execute("""
INSERT INTO general_ledger (
  date, transaction_type, num, name, memo_description, 
  account, debit, credit, balance,
  source_file, imported_at,
  account_name, account_type,
  account_number, account_description
)
SELECT 
  qe.transaction_date AS date,
  qe.transaction_type,
  qe.check_number AS num,
  COALESCE(qe.vendor_name, qe.customer_name, qe.employee_name, '') AS name,
  qe.memo,
  qe.account_name AS account,
  COALESCE(qe.debit_amount, 0) AS debit,
  COALESCE(qe.credit_amount, 0) AS credit,
  NULL AS balance,
  qe.source_file,
  NOW(),
  qe.account_name,
  qe.account_name,
  qe.gl_account AS account_number,
  qe.description
FROM qb_journal_entries qe
WHERE EXTRACT(YEAR FROM qe.transaction_date) = 2012
  AND qe.is_duplicate IS NOT TRUE
ORDER BY qe.transaction_date, qe.account_name
""")

cursor.execute("SELECT COUNT(*) FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012")
new_count = cursor.fetchone()[0]
print(f"✓ Inserted {new_count:,} GL entries from QB source")
conn.commit()
print()

# Step 4: Verify GL Balance
print("STEP 4: VERIFY GL BALANCE")
print("-" * 80)

cursor.execute("""
SELECT 
  ROUND(SUM(debit)::numeric, 2) AS total_debit,
  ROUND(SUM(credit)::numeric, 2) AS total_credit,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS balance_difference
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
""")

debit_total, credit_total, difference = cursor.fetchone()
print(f"  Total Debits:  ${float(debit_total):>12,.2f}")
print(f"  Total Credits: ${float(credit_total):>12,.2f}")
print(f"  Difference:    ${float(difference):>12,.2f}")

if abs(float(difference)) < 0.01:
    print(f"\n  ✓ GL IS BALANCED!")
else:
    print(f"\n  ⚠ GL OUT OF BALANCE by ${abs(float(difference)):,.2f}")
    print(f"     This is likely GST/ITC mismatch or QB import issue")

conn.commit()
print()

# Step 5: Charter Revenue Reconciliation
print("STEP 5: CHARTER REVENUE RECONCILIATION (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  'GL Charter Revenue' AS line,
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
  'Charter Payments (from charters)',
  ROUND(SUM(cp.amount)::numeric, 2)
FROM charter_payments cp
JOIN charters c ON c.reserve_number = cp.charter_id
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
""")

gl_revenue = None
il_revenue = None
cp_revenue = None

for line, amount in cursor.fetchall():
    print(f"  {line:<40}: ${float(amount):>12,.2f}")
    if 'GL Charter' in line:
        gl_revenue = float(amount)
    elif 'Income Ledger' in line:
        il_revenue = float(amount)
    elif 'Charter Payments' in line:
        cp_revenue = float(amount)

if gl_revenue and il_revenue:
    variance = gl_revenue - il_revenue
    print(f"\n  Variance (GL vs IL): ${variance:,.2f}")
    if abs(variance) < 1.00:
        print(f"  ✓ Within tolerance")
    else:
        print(f"  ⚠ Review required")

conn.commit()
print()

# Step 6: Top Accounts
print("STEP 6: TOP ACCOUNTS BY BALANCE (2012 GL)")
print("-" * 80)
print(f"{'Account':<40} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
print("-" * 80)

cursor.execute("""
SELECT 
  COALESCE(account_name, account)::text,
  ROUND(SUM(debit)::numeric, 2),
  ROUND(SUM(credit)::numeric, 2),
  ROUND((SUM(debit) - SUM(credit))::numeric, 2)
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
GROUP BY account_name, account
ORDER BY ABS(SUM(debit) - SUM(credit)) DESC
LIMIT 12
""")

for acct, deb, cred, bal in cursor.fetchall():
    acct_name = str(acct)[:39] if acct else "Unknown"
    print(f"{acct_name:<40} ${float(deb):>11,.2f} ${float(cred):>11,.2f} ${float(bal):>11,.2f}")

conn.commit()
print()

# Step 7: GST Analysis
print("STEP 7: GST/ITC ANALYSIS (2012)")
print("-" * 80)

cursor.execute("""
SELECT 
  account_name,
  ROUND(SUM(debit)::numeric, 2) AS debit_amt,
  ROUND(SUM(credit)::numeric, 2) AS credit_amt,
  ROUND((SUM(debit) - SUM(credit))::numeric, 2) AS net_amt
FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012
  AND (account_name ILIKE '%GST%' OR account_name ILIKE '%HST%' OR account_name ILIKE '%ITC%')
GROUP BY account_name
ORDER BY account_name
""")

gst_accounts = cursor.fetchall()
total_gst = 0

if gst_accounts:
    for acct, deb, cred, net in gst_accounts:
        print(f"  {str(acct):<45}: D=${float(deb):>11,.2f} C=${float(cred):>11,.2f} Net=${float(net):>11,.2f}")
        total_gst += float(net)
    print(f"\n  Net GST Position: ${total_gst:,.2f}")
else:
    print(f"  No GST/HST/ITC accounts found in 2012 GL")

conn.commit()
print()

# Step 8: Summary
print("STEP 8: REBUILD COMPLETE - SUMMARY")
print("=" * 80)
print(f"✓ 2012 General Ledger Rebuilt from QB Journal Entries")
print(f"✓ {new_count:,} entries loaded")
print(f"✓ Status: {'BALANCED' if abs(float(difference)) < 0.01 else 'OUT OF BALANCE'}")
print(f"✓ Backup saved: backup_general_ledger_2012_pre_rebuild_20260410")
print()
print("NEXT STEPS:")
print("  1. Verify Charter Revenue tie-in ($vs Income Ledger)")
print("  2. Check GST/ITC account balances")
print("  3. Verify Banking Reconciliation")
print("  4. Post final T2 export")
print()

conn.close()
