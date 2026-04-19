"""
Complete cleanup of 71 duplicate BANK WITHDRAWAL rows:
1. Build twin map (dup_bt_id -> twin_bt_id)
2. Update receipt_banking_links to point at twins (delete if twin already linked)
3. Check all other FK tables — should be zero
4. Delete the 71 rows
5. Verify
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

# ── Build twin map ────────────────────────────────────────────────────────────
cur.execute(
    "SELECT transaction_id, transaction_date, debit_amount "
    "FROM banking_transactions WHERE transaction_id = ANY(%s)",
    (dup_ids,)
)
bt_rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

twin_map = {}  # dup_bt_id -> twin_bt_id
for bt_id, (bt_date, bt_amt) in bt_rows.items():
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
        twin_map[bt_id] = twin[0]
    else:
        print(f"  WARNING: No twin for BT={bt_id} {bt_date} ${float(bt_amt):.2f}")

print(f"Twin map built: {len(twin_map)} dup rows mapped to twins")

# ── Step 1: Handle receipt_banking_links ──────────────────────────────────────
cur.execute(
    "SELECT link_id, receipt_id, transaction_id "
    "FROM receipt_banking_links WHERE transaction_id = ANY(%s)",
    (dup_ids,)
)
rbl_rows = cur.fetchall()
print(f"receipt_banking_links rows to handle: {len(rbl_rows)}")

updated_rbl = 0
deleted_rbl = 0
for link_id, receipt_id, dup_bt_id in rbl_rows:
    twin_id = twin_map.get(dup_bt_id)
    if twin_id is None:
        print(f"  No twin for BT={dup_bt_id}, deleting link {link_id}")
        cur.execute("DELETE FROM receipt_banking_links WHERE link_id = %s", (link_id,))
        deleted_rbl += 1
        continue
    
    # Check if twin already has a link for this receipt
    cur2.execute(
        "SELECT link_id FROM receipt_banking_links "
        "WHERE receipt_id = %s AND transaction_id = %s",
        (receipt_id, twin_id)
    )
    existing = cur2.fetchone()
    if existing:
        # Twin already linked — delete the dup link
        cur.execute("DELETE FROM receipt_banking_links WHERE link_id = %s", (link_id,))
        deleted_rbl += 1
    else:
        # Re-point to twin
        cur.execute(
            "UPDATE receipt_banking_links SET transaction_id = %s WHERE link_id = %s",
            (twin_id, link_id)
        )
        updated_rbl += 1

conn.commit()
print(f"  receipt_banking_links: updated={updated_rbl}, deleted={deleted_rbl}")

# ── Step 2: Check all other FK tables ────────────────────────────────────────
other_fk_tables = [
    "chauffeur_float_tracking",
    "cibc_card_transactions",
    "etransfer_banking_reconciliation",
    "square_etransfer_reconciliation",
    "owner_expense_transactions",
    "square_capital_loans",
    "vehicle_loan_payments",
    "cheque_register",
    "etransfer_transactions",
    "cash_box_transactions",
    "deposit_slip_items",
]
print("\nChecking other FK tables:")
any_refs = False
for tbl in other_fk_tables:
    try:
        cur.execute(
            f"SELECT COUNT(*) FROM {tbl} WHERE banking_transaction_id = ANY(%s)",
            (dup_ids,)
        )
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print(f"  ** {tbl}: {cnt} references — NEED TO HANDLE")
            any_refs = True
        else:
            print(f"  {tbl}: 0  OK")
    except Exception as e:
        # etransfer_banking_reconciliation has transaction_id not banking_transaction_id
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM {tbl} WHERE transaction_id = ANY(%s)",
                (dup_ids,)
            )
            cnt = cur.fetchone()[0]
            mark = " ** NEED TO HANDLE" if cnt > 0 else "  OK"
            print(f"  {tbl}: {cnt}{mark}")
            if cnt > 0:
                any_refs = True
        except Exception as e2:
            print(f"  {tbl}: error={e2}")
            conn.rollback()

if any_refs:
    print("\nWARNING: Other FK references exist — NOT deleting yet.")
    conn.close()
    exit(1)

# ── Step 3: Verify receipts.banking_transaction_id is clean ──────────────────
cur.execute(
    "SELECT COUNT(*) FROM receipts WHERE banking_transaction_id = ANY(%s)",
    (dup_ids,)
)
rcpt_refs = cur.fetchone()[0]
cur.execute(
    "SELECT COUNT(*) FROM receipt_banking_links WHERE transaction_id = ANY(%s)",
    (dup_ids,)
)
rbl_refs = cur.fetchone()[0]
print(f"\nPre-delete FK check:")
print(f"  receipts.banking_transaction_id refs: {rcpt_refs}")
print(f"  receipt_banking_links refs:           {rbl_refs}")

if rcpt_refs > 0 or rbl_refs > 0:
    print("ERROR: FK refs remain — fix before deleting.")
    conn.close()
    exit(1)

# ── Step 4: DELETE ────────────────────────────────────────────────────────────
print("\nStep 4: Deleting 71 confirmed-duplicate rows...")
cur.execute(
    "DELETE FROM banking_transactions WHERE transaction_id = ANY(%s) RETURNING transaction_id",
    (dup_ids,)
)
deleted = sorted([r[0] for r in cur.fetchall()])
conn.commit()
print(f"  Deleted {len(deleted)} rows.")

# ── Step 5: Final verification ────────────────────────────────────────────────
cur.execute(
    "SELECT COUNT(*), COALESCE(SUM(debit_amount),0) "
    "FROM banking_transactions "
    "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
    "  AND debit_amount IS NOT NULL "
    "  AND (description ILIKE '%%withdrawal%%' OR description ILIKE '%%money mart%%')"
)
r = cur.fetchone()
print(f"\nRemaining 2013-2014 withdrawal rows: {r[0]}  total: ${float(r[1]):,.2f}")
print("(Was 413 rows / $412,681.70 before dedup; now should reflect ~241 rows / ~$180K)")
print("\nCleanup complete.")
conn.close()
