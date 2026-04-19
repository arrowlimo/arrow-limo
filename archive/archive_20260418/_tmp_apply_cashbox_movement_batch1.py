import csv
from pathlib import Path

import psycopg2

DECISION_CSV = Path(r"l:\limo\data\intake\cash_box_queue_decision_sheet.csv")

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
conn.autocommit = False
cur = conn.cursor()

if not DECISION_CSV.exists():
    raise FileNotFoundError(f"Missing decision sheet: {DECISION_CSV}")

ids = []
with DECISION_CSV.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if (row.get("recommended_action") or "").strip().upper() != "CASH_BOX_MOVEMENT":
            continue
        raw_id = (row.get("transaction_id") or "").strip()
        if raw_id.isdigit():
            ids.append(int(raw_id))

ids = sorted(set(ids))
print(f"DECISION_IDS={len(ids)}")
if not ids:
    print("NO_IDS_TO_APPLY")
    cur.close()
    conn.close()
    raise SystemExit(0)

cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
      AND (is_transfer IS DISTINCT FROM TRUE)
    """,
    (ids,),
)
before_count, before_amount = cur.fetchone()
print(f"ELIGIBLE_BEFORE={before_count}|{before_amount}")

values = [(x,) for x in ids]
cur.execute("CREATE TEMP TABLE _cashbox_ids (transaction_id integer PRIMARY KEY) ON COMMIT DROP")
cur.executemany(
    "INSERT INTO _cashbox_ids (transaction_id) VALUES (%s) ON CONFLICT DO NOTHING",
    values,
)

cur.execute(
    """
    UPDATE banking_transactions bt
    SET
        is_transfer = TRUE,
        category = CASE
            WHEN bt.category IS NULL OR btrim(bt.category) = '' THEN 'Cash Withdrawal'
            ELSE bt.category
        END,
        reconciliation_notes = CASE
            WHEN bt.reconciliation_notes ILIKE '%cash_box_decision:CASH_BOX_MOVEMENT%'
                THEN bt.reconciliation_notes
            WHEN bt.reconciliation_notes IS NULL OR btrim(bt.reconciliation_notes) = ''
                THEN '[AUTO] cash_box_decision:CASH_BOX_MOVEMENT transfer-classified'
            ELSE bt.reconciliation_notes || E'\n[AUTO] cash_box_decision:CASH_BOX_MOVEMENT transfer-classified'
        END
    FROM _cashbox_ids x
    WHERE bt.transaction_id = x.transaction_id
      AND (bt.is_transfer IS DISTINCT FROM TRUE)
    """
)
updated = cur.rowcount

cur.execute(
    """
    SELECT COUNT(1), COALESCE(SUM(debit_amount), 0)
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
      AND is_transfer IS TRUE
    """,
    (ids,),
)
after_count, after_amount = cur.fetchone()

conn.commit()
cur.close()
conn.close()

print(f"UPDATED_ROWS={updated}")
print(f"TRANSFER_AFTER={after_count}|{after_amount}")
print("CASHBOX_MOVEMENT_BATCH1_DONE")
