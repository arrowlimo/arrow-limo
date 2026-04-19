import csv
from pathlib import Path

import psycopg2

QUEUE_CSV = Path(r"l:\limo\data\intake\unlinked_debits_manual_review_queue.csv")
TARGET_GROUP = "TRANSFER_ETRANSFER"

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
conn.autocommit = False
cur = conn.cursor()

if not QUEUE_CSV.exists():
    raise FileNotFoundError(f"Missing queue: {QUEUE_CSV}")

ids = []
with QUEUE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if (row.get("group") or "").strip().upper() != TARGET_GROUP:
            continue
        tid = (row.get("transaction_id") or "").strip()
        if tid.isdigit():
            ids.append(int(tid))

ids = sorted(set(ids))
print(f"TARGET_IDS={len(ids)}")
if not ids:
    print("NO_TARGET_IDS")
    cur.close()
    conn.close()
    raise SystemExit(0)

cur.execute(
    """
    SELECT
        COUNT(1),
        COALESCE(SUM(debit_amount), 0),
        COUNT(1) FILTER (WHERE is_transfer IS TRUE)
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    """,
    (ids,),
)
before_count, before_amount, before_transfer_true = cur.fetchone()
print(f"BEFORE|rows={before_count}|amount={before_amount}|already_transfer={before_transfer_true}")

cur.execute("CREATE TEMP TABLE _q_transfer_ids (transaction_id integer PRIMARY KEY) ON COMMIT DROP")
cur.executemany(
    "INSERT INTO _q_transfer_ids (transaction_id) VALUES (%s) ON CONFLICT DO NOTHING",
    [(x,) for x in ids],
)

cur.execute(
    """
    UPDATE banking_transactions bt
    SET
        is_transfer = TRUE,
        category = CASE
            WHEN bt.category IS NULL OR btrim(bt.category) = '' OR bt.category IN ('Expense - Other', 'Correction')
                THEN 'Bank Transfer'
            ELSE bt.category
        END,
        reconciliation_status = CASE
            WHEN bt.reconciliation_status = 'CASH_BOX_REVIEW' THEN bt.reconciliation_status
            ELSE 'TRANSFER_REVIEW'
        END,
        reconciliation_notes = CASE
            WHEN bt.reconciliation_notes ILIKE '%transfer_etransfer_batch1%'
                THEN bt.reconciliation_notes
            WHEN bt.reconciliation_notes IS NULL OR btrim(bt.reconciliation_notes) = ''
                THEN '[AUTO] transfer_etransfer_batch1: classified as transfer movement'
            ELSE bt.reconciliation_notes || E'\n[AUTO] transfer_etransfer_batch1: classified as transfer movement'
        END
    FROM _q_transfer_ids q
    WHERE bt.transaction_id = q.transaction_id
      AND bt.receipt_id IS NULL
      AND bt.debit_amount > 0
      AND bt.reconciled_receipt_id IS NULL
      AND bt.reconciled_payment_id IS NULL
      AND bt.reconciled_charter_id IS NULL
      AND bt.reconciliation_status IS DISTINCT FROM 'CASH_BOX_REVIEW'
      AND bt.is_transfer IS DISTINCT FROM TRUE
    """
)
updated = cur.rowcount

cur.execute(
    """
    SELECT
        COUNT(1),
        COALESCE(SUM(debit_amount), 0),
        COUNT(1) FILTER (WHERE is_transfer IS TRUE),
        COUNT(1) FILTER (WHERE reconciliation_status = 'TRANSFER_REVIEW')
    FROM banking_transactions
    WHERE transaction_id = ANY(%s)
    """,
    (ids,),
)
after_count, after_amount, after_transfer_true, after_transfer_review = cur.fetchone()

conn.commit()
cur.close()
conn.close()

print(f"UPDATED_ROWS={updated}")
print(
    f"AFTER|rows={after_count}|amount={after_amount}|transfer_true={after_transfer_true}|transfer_review={after_transfer_review}"
)
print("TRANSFER_ETRANSFER_BATCH1_DONE")
