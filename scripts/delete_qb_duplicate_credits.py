"""
Delete QB duplicate CREDIT cheque transactions that match DEBIT cheques.
These are accounting journal entries duplicating actual bank transactions.
"""
import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("DELETE QB DUPLICATE CREDIT CHEQUE TRANSACTIONS")
print("=" * 120)

# 1. Get all CREDIT cheque transactions
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        credit_amount,
        description,
        EXTRACT(YEAR FROM transaction_date) as year
    FROM banking_transactions
    WHERE (description ILIKE '%CHQ%' OR description ILIKE '%CHEQUE%')
      AND credit_amount IS NOT NULL
    ORDER BY transaction_date
""")

credit_txs = cur.fetchall()
print(f"\nFound {len(credit_txs)} CREDIT cheque transactions")

# 2. Get all DEBIT cheque transactions to build matching index
cur.execute("""
    SELECT 
        transaction_date,
        debit_amount
    FROM banking_transactions
    WHERE (description ILIKE '%CHQ%' OR description ILIKE '%CHEQUE%')
      AND debit_amount IS NOT NULL
""")

# Build index of debit transactions by date+amount
debit_index = set()
for date, amount in cur.fetchall():
    key = (date, amount)
    debit_index.add(key)

print(f"Built index of {len(debit_index)} unique date+amount DEBIT combinations")

# 3. Find credits that match debits
duplicates = []
for tx_id, date, amount, desc, year in credit_txs:
    key = (date, amount)
    if key in debit_index:
        duplicates.append((tx_id, date, amount, desc, year))

print(f"\nFound {len(duplicates)} CREDIT transactions matching DEBIT date+amount")

# 4. Separate by year (locked vs unlocked)
locked_years = [2012, 2013, 2014]
locked_duplicates = [d for d in duplicates if d[4] in locked_years]
unlocked_duplicates = [d for d in duplicates if d[4] not in locked_years]

print(f"  - Locked years (2012-2014): {len(locked_duplicates)}")
print(f"  - Unlocked years: {len(unlocked_duplicates)}")

# 5. Delete unlocked duplicates
if unlocked_duplicates:
    print(f"\n\nDELETING {len(unlocked_duplicates)} UNLOCKED QB DUPLICATES:")
    deleted_count = 0
    for tx_id, date, amount, desc, year in unlocked_duplicates[:10]:  # Show first 10
        print(f"  TX {tx_id:6d} | {date} | ${amount:>10,.2f} | {desc[:60]}")
    if len(unlocked_duplicates) > 10:
        print(f"  ... and {len(unlocked_duplicates) - 10} more")
    
    # Delete them
    unlocked_ids = [d[0] for d in unlocked_duplicates]
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE transaction_id = ANY(%s)
    """, (unlocked_ids,))
    deleted_count = cur.rowcount
    print(f"\n✅ Deleted {deleted_count} unlocked transactions")

# 6. Mark locked duplicates
if locked_duplicates:
    print(f"\n\nMARKING {len(locked_duplicates)} LOCKED QB DUPLICATES (2012-2014):")
    for tx_id, date, amount, desc, year in locked_duplicates[:10]:  # Show first 10
        print(f"  TX {tx_id:6d} | {date} | ${amount:>10,.2f} | {desc[:60]}")
    if len(locked_duplicates) > 10:
        print(f"  ... and {len(locked_duplicates) - 10} more")
    
    # Mark them as duplicates
    locked_ids = [d[0] for d in locked_duplicates]
    cur.execute("""
        UPDATE banking_transactions
        SET reconciliation_status = 'QB_DUPLICATE',
            reconciliation_notes = 'QB journal entry duplicate of actual bank DEBIT cheque (same date+amount)',
            reconciled_at = NOW(),
            reconciled_by = 'System - QB duplicate cleanup'
        WHERE transaction_id = ANY(%s)
    """, (locked_ids,))
    marked_count = cur.rowcount
    print(f"\n✅ Marked {marked_count} locked transactions as QB_DUPLICATE")

# Commit all changes
conn.commit()
print("\n" + "=" * 120)
print("✅ ALL CHANGES COMMITTED")
print("=" * 120)

# 7. Verify final state
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE reconciliation_status = 'QB_DUPLICATE') as qb_duplicates,
        COUNT(*) FILTER (WHERE reconciliation_status IS NULL OR reconciliation_status != 'QB_DUPLICATE') as active
    FROM banking_transactions
    WHERE (description ILIKE '%CHQ%' OR description ILIKE '%CHEQUE%')
      AND credit_amount IS NOT NULL
""")

qb_dup, active = cur.fetchone()
print(f"\nFinal CREDIT cheque transaction counts:")
print(f"  - Marked as QB_DUPLICATE: {qb_dup}")
print(f"  - Active (not duplicates): {active}")
print(f"  - Previously deleted (unlocked): {deleted_count if unlocked_duplicates else 0}")
print(f"\n✅ Cleanup complete - {len(duplicates)} QB duplicates removed from active data")

cur.close()
conn.close()
