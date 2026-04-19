"""
Step 1: Re-link 65 receipts from dup BANK WITHDRAWAL BT rows to their detail twins.
Step 2: Delete the 71 confirmed-duplicate BANK WITHDRAWAL banking_transaction rows.
Step 3: Verify.
"""
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur  = conn.cursor()
cur2 = conn.cursor()

dup_ids = [62577, 62786, 88233, 88254, 88285, 88308, 88311, 88319, 88321, 88324,
           88329, 88332, 88338, 88352, 88364, 88373, 88375, 88383, 88387, 88407,
           88420, 88426, 88435, 88437, 88442, 88446, 88454, 88468, 88470, 88471,
           88484, 88486, 88487, 88493, 88505, 88517, 88521, 88525, 88526, 88529,
           88530, 88534, 88543, 88547, 88550, 88553, 88565, 88575, 88576, 88579,
           88585, 88586, 88593, 88602, 88618, 88630, 88633, 88636, 88642, 88644,
           88649, 88653, 88658, 88670, 88673, 88677, 88682, 88684, 88690, 88696, 88699]

# ── Build remap: receipt_id -> new_bt_id ──────────────────────────────────────
cur.execute(
    "SELECT r.receipt_id, r.banking_transaction_id "
    "FROM receipts r "
    "WHERE r.banking_transaction_id = ANY(%s)",
    (dup_ids,)
)
receipt_links = cur.fetchall()

cur.execute(
    "SELECT transaction_id, transaction_date, debit_amount "
    "FROM banking_transactions WHERE transaction_id = ANY(%s)",
    (dup_ids,)
)
bt_rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

by_bt = defaultdict(list)
for receipt_id, bt_id in receipt_links:
    by_bt[bt_id].append(receipt_id)

remap = []  # (receipt_id, old_bt_id, new_bt_id)
for bt_id, receipt_ids in by_bt.items():
    bt_date, bt_amt = bt_rows[bt_id]
    cur2.execute(
        "SELECT transaction_id FROM banking_transactions "
        "WHERE transaction_date = %s AND debit_amount = %s "
        "  AND transaction_id != %s "
        "  AND description NOT IN ('BANK WITHDRAWAL', 'MONEY MART WITHDRAWAL') "
        "  AND (description ILIKE '%%withdrawal%%' OR description ILIKE '%%atm%%' "
        "       OR description ILIKE '%%abm%%' OR description ILIKE '%%branch%%') "
        "ORDER BY transaction_id LIMIT 1",
        (bt_date, bt_amt, bt_id)
    )
    twin = cur2.fetchone()
    if twin:
        for rid in receipt_ids:
            remap.append((rid, bt_id, twin[0]))
    else:
        print(f"  WARNING: No twin for BT={bt_id} {bt_date} ${float(bt_amt):.2f} — skipping its receipts")

print(f"Receipts to re-link: {len(remap)}")
if not remap:
    print("Nothing to do.")
    conn.close()
    exit()

# ── Step 1: Update receipts ───────────────────────────────────────────────────
print("\nStep 1: Re-linking receipts...")
for receipt_id, old_bt, new_bt in remap:
    cur.execute(
        "UPDATE receipts SET banking_transaction_id = %s WHERE receipt_id = %s",
        (new_bt, receipt_id)
    )
conn.commit()
print(f"  Updated {len(remap)} receipts.")

# ── Verify no receipts still point at dup rows ────────────────────────────────
cur.execute(
    "SELECT COUNT(*) FROM receipts WHERE banking_transaction_id = ANY(%s)",
    (dup_ids,)
)
remaining = cur.fetchone()[0]
print(f"  Receipts still linked to dup rows after update: {remaining}")
if remaining > 0:
    print("  ERROR — some receipts not re-linked. Aborting delete.")
    conn.close()
    exit(1)

# ── Step 2: Delete the 71 dup rows ───────────────────────────────────────────
print("\nStep 2: Deleting 71 confirmed-duplicate BANK WITHDRAWAL rows...")
cur.execute(
    "DELETE FROM banking_transactions WHERE transaction_id = ANY(%s) RETURNING transaction_id",
    (dup_ids,)
)
deleted = [r[0] for r in cur.fetchall()]
conn.commit()
print(f"  Deleted {len(deleted)} rows: {sorted(deleted)[:10]} ...")

# ── Step 3: Verify clean state ────────────────────────────────────────────────
cur.execute(
    "SELECT COUNT(*), COALESCE(SUM(debit_amount),0) "
    "FROM banking_transactions "
    "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
    "  AND debit_amount IS NOT NULL "
    "  AND (description ILIKE '%%withdrawal%%' OR description ILIKE '%%money mart%%')"
)
r = cur.fetchone()
print(f"\nRemaining 2013-2014 withdrawal rows: {r[0]}  total: ${float(r[1]):,.2f}")

cur.execute(
    "SELECT COUNT(*) FROM receipts WHERE banking_transaction_id = ANY(%s)",
    (dup_ids,)
)
print(f"Receipts still linked to deleted rows: {cur.fetchone()[0]}  (should be 0)")

print("\nDone.")
conn.close()
