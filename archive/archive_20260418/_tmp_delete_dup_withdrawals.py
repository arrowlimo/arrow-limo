import psycopg2
from collections import defaultdict

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Re-derive the 71 IDs
cur.execute(
    "SELECT transaction_id, transaction_date, debit_amount, description, "
    "       category, source_file "
    "FROM banking_transactions "
    "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
    "  AND debit_amount IS NOT NULL AND debit_amount > 0 "
    "  AND (description ILIKE '%withdrawal%' OR description ILIKE '%money mart%') "
    "ORDER BY transaction_date, debit_amount DESC, transaction_id"
)
all_rows = cur.fetchall()

by_key = defaultdict(list)
for r in all_rows:
    by_key[(r[1], r[2])].append(r)

def is_summary(desc):
    return (desc or "").upper() in ("BANK WITHDRAWAL", "MONEY MART WITHDRAWAL")

dup_ids = []
for key, group in by_key.items():
    if len(group) > 1:
        has_detail = any(not is_summary(r[3]) for r in group)
        if has_detail:
            for r in group:
                if is_summary(r[3]):
                    dup_ids.append(r[0])

dup_ids_tuple = tuple(dup_ids)
print(f"IDs to delete ({len(dup_ids)}): {sorted(dup_ids)}")

# Check FK references in charter_payments
cur.execute(
    "SELECT COUNT(*) FROM charter_payments "
    "WHERE banking_transaction_id = ANY(%s)",
    (list(dup_ids),)
)
cp_refs = cur.fetchone()[0]

# Check FK references in receipts
cur.execute(
    "SELECT COUNT(*) FROM receipts "
    "WHERE banking_transaction_id = ANY(%s)",
    (list(dup_ids),)
)
rcpt_refs = cur.fetchone()[0]

print(f"charter_payments references: {cp_refs}")
print(f"receipts references: {rcpt_refs}")

if cp_refs == 0 and rcpt_refs == 0:
    print("\nNo FK references — safe to delete.")
    
    # Execute the delete
    cur.execute(
        "DELETE FROM banking_transactions "
        "WHERE transaction_id = ANY(%s) "
        "RETURNING transaction_id",
        (list(dup_ids),)
    )
    deleted = cur.fetchall()
    conn.commit()
    print(f"\nDELETED {len(deleted)} rows successfully.")
    
    # Verify the balance impact
    cur.execute(
        "SELECT COUNT(*), SUM(debit_amount) "
        "FROM banking_transactions "
        "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
        "  AND debit_amount IS NOT NULL "
        "  AND (description ILIKE '%withdrawal%' OR description ILIKE '%money mart%')"
    )
    r = cur.fetchone()
    print(f"\nRemaining 2013-2014 withdrawal rows: {r[0]}, total ${float(r[1] or 0):,.2f}")
else:
    print(f"\nWARNING: FK references found — NOT deleting. Manual review needed.")

conn.close()
