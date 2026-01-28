"""
Fix CIBC 8362 2014-2017 deposit/withdrawal column mismatches
Swap debit_amount and credit_amount where description doesn't match actual transaction direction
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

print("=" * 100)
print("FIX CIBC 8362 (2014-2017) DEPOSIT/WITHDRAWAL COLUMN MISMATCHES")
print("=" * 100)

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Fix 1: SQUARE DEPOSIT showing as debit (WRONG - should be credit)
print("\n🔧 FIX 1: SQUARE DEPOSIT in debit column → swap to credit")
print("-" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%SQUARE DEPOSIT%'
    AND debit_amount IS NOT NULL
    AND debit_amount > 0
    ORDER BY transaction_date
""")

square_fixes = cur.fetchall()
print(f"Found {len(square_fixes)} SQUARE DEPOSIT transactions to fix:")
for tid, date, desc, debit, credit in square_fixes:
    print(f"  {date} - ID {tid}: ${debit:.2f} debit → credit")

# Fix 2: BANK DEPOSIT showing as debit (WRONG - should be credit)
print("\n🔧 FIX 2: BANK DEPOSIT in debit column → swap to credit")
print("-" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%BANK DEPOSIT%'
    AND UPPER(description) NOT LIKE '%STOP%'
    AND debit_amount IS NOT NULL
    AND debit_amount > 0
    ORDER BY transaction_date
""")

bank_deposit_fixes = cur.fetchall()
print(f"Found {len(bank_deposit_fixes)} BANK DEPOSIT transactions to fix:")
for tid, date, desc, debit, credit in bank_deposit_fixes:
    print(f"  {date} - ID {tid}: ${debit:.2f} debit → credit")

# Fix 3: BANK WITHDRAWAL showing as credit (WRONG - should be debit)
print("\n🔧 FIX 3: BANK WITHDRAWAL in credit column → swap to debit")
print("-" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%BANK WITHDRAWAL%'
    AND UPPER(description) NOT LIKE '%STOP%'
    AND credit_amount IS NOT NULL
    AND credit_amount > 0
    ORDER BY transaction_date
""")

bank_withdrawal_fixes = cur.fetchall()
print(f"Found {len(bank_withdrawal_fixes)} BANK WITHDRAWAL transactions to fix:")
for tid, date, desc, debit, credit in bank_withdrawal_fixes:
    print(f"  {date} - ID {tid}: ${credit:.2f} credit → debit")

# Check STOP transactions (don't auto-fix, just report)
print("\n🔍 STOP transactions (review only - not auto-fixed):")
print("-" * 100)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(description) LIKE '%STOP%'
    ORDER BY transaction_date
""")

stop_txns = cur.fetchall()
if stop_txns:
    for tid, date, desc, debit, credit in stop_txns:
        debit_str = f"${debit:.2f}" if debit else "None"
        credit_str = f"${credit:.2f}" if credit else "None"
        print(f"  {date} - ID {tid}: {desc[:50]} - Debit: {debit_str}, Credit: {credit_str}")
else:
    print("  No STOP transactions found")

# Confirmation
total_fixes = len(square_fixes) + len(bank_deposit_fixes) + len(bank_withdrawal_fixes)
print("\n" + "=" * 100)
print(f"TOTAL FIXES TO APPLY: {total_fixes}")
print("=" * 100)

if total_fixes == 0:
    print("✅ No fixes needed")
    cur.close()
    conn.close()
    exit(0)

response = input(f"\nApply {total_fixes} fixes? (YES to proceed): ")

if response != "YES":
    print("❌ Cancelled - no changes made")
    cur.close()
    conn.close()
    exit(0)

# Apply fixes
print("\n🚀 Applying fixes...")

# Fix SQUARE DEPOSIT (swap debit → credit)
if square_fixes:
    for tid, date, desc, debit, credit in square_fixes:
        cur.execute("""
            UPDATE banking_transactions
            SET debit_amount = NULL,
                credit_amount = %s,
                updated_at = NOW()
            WHERE transaction_id = %s
        """, (debit, tid))
    print(f"✅ Fixed {len(square_fixes)} SQUARE DEPOSIT transactions")

# Fix BANK DEPOSIT (swap debit → credit)
if bank_deposit_fixes:
    for tid, date, desc, debit, credit in bank_deposit_fixes:
        cur.execute("""
            UPDATE banking_transactions
            SET debit_amount = NULL,
                credit_amount = %s,
                updated_at = NOW()
            WHERE transaction_id = %s
        """, (debit, tid))
    print(f"✅ Fixed {len(bank_deposit_fixes)} BANK DEPOSIT transactions")

# Fix BANK WITHDRAWAL (swap credit → debit)
if bank_withdrawal_fixes:
    for tid, date, desc, debit, credit in bank_withdrawal_fixes:
        cur.execute("""
            UPDATE banking_transactions
            SET credit_amount = NULL,
                debit_amount = %s,
                updated_at = NOW()
            WHERE transaction_id = %s
        """, (credit, tid))
    print(f"✅ Fixed {len(bank_withdrawal_fixes)} BANK WITHDRAWAL transactions")

# COMMIT
conn.commit()
print(f"\n✅ COMMITTED {total_fixes} fixes to database")

# Verify
print("\n" + "=" * 100)
print("VERIFICATION - Re-checking for mismatches...")
print("=" * 100)

cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE bank_id = 1
    AND transaction_date BETWEEN '2014-01-01' AND '2017-12-31'
    AND source_file = '2014-2017 CIBC 8362.xlsx'
    AND (
        (UPPER(description) LIKE '%SQUARE DEPOSIT%' AND debit_amount IS NOT NULL)
        OR (UPPER(description) LIKE '%BANK DEPOSIT%' AND UPPER(description) NOT LIKE '%STOP%' AND debit_amount IS NOT NULL)
        OR (UPPER(description) LIKE '%BANK WITHDRAWAL%' AND UPPER(description) NOT LIKE '%STOP%' AND credit_amount IS NOT NULL)
    )
""")

remaining = cur.fetchone()[0]

if remaining == 0:
    print("✅ All mismatches fixed!")
else:
    print(f"⚠️ Warning: {remaining} mismatches still remain")

cur.close()
conn.close()

print("\n✅ Fix complete")
