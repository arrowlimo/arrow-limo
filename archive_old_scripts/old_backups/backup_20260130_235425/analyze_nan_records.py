"""
Analyze records with name='nan' to understand their nature and find patterns
"""
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 140)
print("ANALYZING RECORDS WITH name='nan'")
print("=" * 140)

# Total count
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE name = 'nan'
""")
total_nan = cur.fetchone()[0]
print(f"\nTotal records with name='nan': {total_nan:,}")

# By year
print("\nBreakdown by year:")
cur.execute("""
    SELECT EXTRACT(YEAR FROM date) as year, COUNT(*) as count
    FROM general_ledger 
    WHERE name = 'nan'
    GROUP BY year
    ORDER BY year DESC
""")
for year, count in cur.fetchall():
    print(f"  {int(year) if year else 'NULL'}: {count:,}")

# By account
print("\nTop 20 accounts with name='nan':")
cur.execute("""
    SELECT account, COUNT(*) as count
    FROM general_ledger 
    WHERE name = 'nan'
    GROUP BY account
    ORDER BY count DESC
    LIMIT 20
""")
for account, count in cur.fetchall():
    print(f"  {account}: {count:,}")

# By transaction_type
print("\nBy transaction type:")
cur.execute("""
    SELECT transaction_type, COUNT(*) as count
    FROM general_ledger 
    WHERE name = 'nan'
    GROUP BY transaction_type
    ORDER BY count DESC
""")
for trans_type, count in cur.fetchall():
    type_label = trans_type if trans_type else 'NULL'
    print(f"  {type_label}: {count:,}")

# Check memo_description for patterns
print("\n" + "=" * 140)
print("Sample records with memo_description patterns:")
print("=" * 140)
cur.execute("""
    SELECT id, date, account, memo_description, debit, credit, transaction_type, num
    FROM general_ledger 
    WHERE name = 'nan'
    AND memo_description IS NOT NULL
    AND memo_description != ''
    ORDER BY date DESC
    LIMIT 30
""")

for row in cur.fetchall():
    gl_id, date, account, memo, debit, credit, trans_type, num = row
    amount = debit if debit else credit
    memo_short = memo[:80] if memo else ''
    print(f"ID {gl_id}: {date} | {account:40s} | ${amount:10} | Type: {trans_type:15s} | {memo_short}")

# Check if there are matching transactions on same date with different accounts (transfers)
print("\n" + "=" * 140)
print("Analyzing potential transfer patterns (same date, same amount, opposite accounts):")
print("=" * 140)
cur.execute("""
    WITH nan_records AS (
        SELECT id, date, account, debit, credit, memo_description
        FROM general_ledger
        WHERE name = 'nan'
        AND EXTRACT(YEAR FROM date) = 2025
        LIMIT 100
    )
    SELECT 
        nr.id,
        nr.date,
        nr.account as from_account,
        gl2.account as to_account,
        nr.debit,
        nr.credit,
        gl2.debit as match_debit,
        gl2.credit as match_credit,
        nr.memo_description
    FROM nan_records nr
    JOIN general_ledger gl2 ON gl2.date = nr.date
        AND gl2.id != nr.id
        AND (
            (nr.debit IS NOT NULL AND gl2.credit = nr.debit)
            OR (nr.credit IS NOT NULL AND gl2.debit = nr.credit)
        )
    WHERE gl2.name != 'nan'
    LIMIT 20
""")

transfer_pairs = cur.fetchall()
if transfer_pairs:
    print("Found potential transfer pairs:")
    for row in transfer_pairs:
        gl_id, date, from_acct, to_acct, debit, credit, match_debit, match_credit, memo = row
        amount = debit if debit else credit
        memo_short = memo[:60] if memo else ''
        print(f"ID {gl_id}: {date} | {from_acct:35s} ↔ {to_acct:35s} | ${amount:10} | {memo_short}")
else:
    print("No clear transfer pairs found in sample")

# Check for Square-specific patterns
print("\n" + "=" * 140)
print("Square-related transactions:")
print("=" * 140)
cur.execute("""
    SELECT id, date, account, debit, credit, memo_description, transaction_type
    FROM general_ledger 
    WHERE name = 'nan'
    AND (account LIKE '%Square%' OR memo_description LIKE '%Square%')
    ORDER BY date DESC
    LIMIT 15
""")

for row in cur.fetchall():
    gl_id, date, account, debit, credit, memo, trans_type = row
    amount = debit if debit else credit
    memo_short = memo[:70] if memo else ''
    print(f"ID {gl_id}: {date} | {account:40s} | ${amount:10} | {trans_type:10s} | {memo_short}")

conn.close()
print("\n" + "=" * 140)
print("Analysis complete!")
