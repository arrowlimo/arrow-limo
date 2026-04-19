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

# Load all receipts linked to dup rows
cur.execute(
    "SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date, "
    "       r.payment_method, r.banking_transaction_id, r.receipt_source "
    "FROM receipts r "
    "WHERE r.banking_transaction_id = ANY(%s) "
    "ORDER BY r.banking_transaction_id",
    (dup_ids,)
)
receipt_rows = cur.fetchall()
print(f"Receipts linked to dup withdrawal rows: {len(receipt_rows)}")

# Load the dup BT rows themselves
cur.execute(
    "SELECT transaction_id, transaction_date, debit_amount, description "
    "FROM banking_transactions "
    "WHERE transaction_id = ANY(%s) "
    "ORDER BY transaction_id",
    (dup_ids,)
)
bt_rows = {r[0]: r for r in cur.fetchall()}

# Group receipts by bt_id
by_bt = defaultdict(list)
for r in receipt_rows:
    by_bt[r[5]].append(r)

print()
no_twin = []
remap_plan = []  # (receipt_id, old_bt_id, new_bt_id)

for bt_id, rcpts in sorted(by_bt.items()):
    bt = bt_rows.get(bt_id)
    if not bt:
        print(f"  DUP BT={bt_id} NOT IN DB (already deleted?)")
        continue
    bid, bt_date, bt_amt, bt_desc = bt

    # Find the detail twin on same date+amount
    cur2.execute(
        "SELECT transaction_id, description, source_file "
        "FROM banking_transactions "
        "WHERE transaction_date = %s AND debit_amount = %s "
        "  AND transaction_id != %s "
        "  AND description NOT IN ('BANK WITHDRAWAL', 'MONEY MART WITHDRAWAL') "
        "  AND (description ILIKE '%%withdrawal%%' OR description ILIKE '%%atm%%' "
        "       OR description ILIKE '%%abm%%' OR description ILIKE '%%branch%%')",
        (bt_date, bt_amt, bt_id)
    )
    twins = cur2.fetchall()

    print(f"  DUP  BT={bt_id} {bt_date} ${float(bt_amt):.2f} [{bt_desc}]")
    for r in rcpts:
        print(f"       receipt {r[0]} {str(r[1])[:30]:<30} ${float(r[2]):.2f} src={r[6]}")

    if twins:
        twin_id = twins[0][0]
        print(f"       TWIN BT={twin_id} [{twins[0][1][:55]}]")
        for r in rcpts:
            remap_plan.append((r[0], bt_id, twin_id))
    else:
        print(f"       ** NO TWIN FOUND **")
        no_twin.append((bt_id, rcpts))

print()
print(f"Receipts that can be re-linked to twin:  {len(remap_plan)}")
print(f"Receipts with no twin (need manual fix): {sum(len(r) for _, r in no_twin)}")

conn.close()
