import csv
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB_PASSWORD = os.environ.get("DB_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("Set DB_PASSWORD before running")

BASE = Path(r"l:\limo\reports\audit_exceptions_2012")
IN_CSV = BASE / "priority_manual_first_2012.csv"
OUT_CSV = BASE / "top20_action_plan_2012.csv"
OUT_SQL = BASE / "top20_action_plan_2012.sql"

# User-confirmed classifications for formerly ambiguous rows.
# This makes action planning deterministic and audit-traceable.
OVERRIDES = {
    69148: {
        "action": "KEEP_AS_IS",
        "reason": "user_classified_vendor_refund_credit_against_prior_purchase",
    },
    102149: {
        "action": "SAFE_RELINK",
        "reason": "user_classified_related_party_reimbursement",
        "keep_receipt_id": 215796,
        "unlink_receipt_ids": [216351],
    },
    69560: {
        "action": "KEEP_AS_IS",
        "reason": "user_classified_internal_transfer_credit",
    },
    69489: {
        "action": "KEEP_AS_IS",
        "reason": "user_classified_internal_transfer_credit",
    },
    69781: {
        "action": "KEEP_AS_IS",
        "reason": "user_classified_internal_transfer_credit",
    },
    99922: {
        "action": "SAFE_RELINK",
        "reason": "user_classified_vehicle_repair",
        "keep_receipt_id": 173546,
        "unlink_receipt_ids": [218686],
    },
    100033: {
        "action": "KEEP_AS_IS",
        "reason": "user_classified_internal_transfer_cheque_nsf_tracking",
    },
}

rows = []
with IN_CSV.open("r", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

# Keep first 20 transaction ids in listed priority order
seen = set()
tx_ids = []
for row in rows:
    tx = row.get("banking_transaction_id")
    if not tx:
        continue
    try:
        txid = int(tx)
    except Exception:
        continue
    if txid in seen:
        continue
    seen.add(txid)
    tx_ids.append(txid)
    if len(tx_ids) >= 20:
        break

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password=DB_PASSWORD,
)
cur = conn.cursor(cursor_factory=RealDictCursor)

plan = []
sql_lines = [
    "-- top20_action_plan_2012.sql",
    "-- Generated from local almsdata; REVIEW BEFORE APPLYING",
    "BEGIN;",
]

for txid in tx_ids:
    cur.execute(
        """
        SELECT transaction_id, account_number, transaction_date, COALESCE(description,'') AS description,
               COALESCE(debit_amount,0)::float AS debit_amount, receipt_id
        FROM banking_transactions
        WHERE transaction_id = %s
        """,
        (txid,),
    )
    tx = cur.fetchone()
    if not tx:
        plan.append(
            {
                "transaction_id": txid,
                "action": "MANUAL_REVIEW",
                "reason": "transaction_missing",
            }
        )
        continue

    cur.execute(
        """
        SELECT receipt_id, receipt_date, COALESCE(vendor_name,'') AS vendor_name,
               COALESCE(description,'') AS description,
               COALESCE(gross_amount,0)::float AS gross_amount,
               COALESCE(receipt_source,'') AS receipt_source,
               banking_transaction_id,
               COALESCE(gl_account_code, COALESCE(gl_code,'')) AS gl_code
        FROM receipts
        WHERE banking_transaction_id = %s
        ORDER BY receipt_id
        """,
        (txid,),
    )
    linked = cur.fetchall()

    debit = float(tx["debit_amount"] or 0.0)
    total = sum(float(r["gross_amount"] or 0.0) for r in linked)
    delta = round(total - debit, 2)

    action = "MANUAL_REVIEW"
    reason = "needs_context"
    keep_receipt_id = None
    unlink_receipt_ids = []

    if txid in OVERRIDES:
        ov = OVERRIDES[txid]
        action = ov["action"]
        reason = ov["reason"]
        keep_receipt_id = ov.get("keep_receipt_id")
        unlink_receipt_ids = ov.get("unlink_receipt_ids", [])
        if action == "SAFE_RELINK" and keep_receipt_id:
            linked_ids = {r["receipt_id"] for r in linked}
            if keep_receipt_id in linked_ids and linked_ids.issubset({keep_receipt_id}):
                action = "KEEP_AS_IS"
                reason = f"{reason}_already_applied"
                unlink_receipt_ids = []
    else:
        if not linked:
            action = "MANUAL_REVIEW"
            reason = "no_linked_receipts"
        elif len(linked) == 1 and abs(delta) < 0.01:
            action = "KEEP_AS_IS"
            reason = "single_receipt_exact"
            keep_receipt_id = linked[0]["receipt_id"]
        else:
            exact = [r for r in linked if abs(float(r["gross_amount"]) - debit) < 0.01]
            non_auto_exact = [
                r
                for r in exact
                if not (r["receipt_source"] or "").lower().startswith("auto_")
            ]
            auto_rows = [
                r for r in linked if (r["receipt_source"] or "").lower().startswith("auto_")
            ]

            if len(non_auto_exact) == 1:
                keep_receipt_id = non_auto_exact[0]["receipt_id"]
                unlink_receipt_ids = [
                    r["receipt_id"] for r in linked if r["receipt_id"] != keep_receipt_id
                ]
                action = "SAFE_RELINK"
                reason = "prefer_non_auto_exact"
            elif len(exact) == 1:
                keep_receipt_id = exact[0]["receipt_id"]
                unlink_receipt_ids = [
                    r["receipt_id"] for r in linked if r["receipt_id"] != keep_receipt_id
                ]
                action = "SAFE_RELINK"
                reason = "single_exact_receipt"
            elif len(linked) >= 2 and len(auto_rows) >= 1 and abs(delta) >= 0.01:
                action = "MANUAL_REVIEW"
                reason = "multi_receipt_non_exact"
            else:
                action = "MANUAL_REVIEW"
                reason = "ambiguous_multi_receipt"

    plan.append(
        {
            "transaction_id": txid,
            "account_number": tx["account_number"],
            "transaction_date": str(tx["transaction_date"]),
            "description": tx["description"],
            "debit_amount": f"{debit:.2f}",
            "linked_receipts": len(linked),
            "linked_sum": f"{total:.2f}",
            "delta": f"{delta:.2f}",
            "action": action,
            "reason": reason,
            "keep_receipt_id": keep_receipt_id or "",
            "unlink_receipt_ids": ",".join(str(x) for x in unlink_receipt_ids),
        }
    )

    if action == "SAFE_RELINK" and keep_receipt_id:
        sql_lines.append(f"-- tx {txid}: {tx['description']}")
        sql_lines.append(
            f"UPDATE receipts SET banking_transaction_id = {txid} WHERE receipt_id = {keep_receipt_id};"
        )
        if unlink_receipt_ids:
            sql_lines.append(
                f"UPDATE receipts SET banking_transaction_id = NULL WHERE receipt_id IN ({','.join(str(x) for x in unlink_receipt_ids)});"
            )
        sql_lines.append(
            f"UPDATE banking_transactions SET receipt_id = {keep_receipt_id} WHERE transaction_id = {txid};"
        )

sql_lines.append("-- COMMIT;  -- uncomment after review")
sql_lines.append("ROLLBACK;")

with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
    fieldnames = [
        "transaction_id",
        "account_number",
        "transaction_date",
        "description",
        "debit_amount",
        "linked_receipts",
        "linked_sum",
        "delta",
        "action",
        "reason",
        "keep_receipt_id",
        "unlink_receipt_ids",
    ]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for row in plan:
        w.writerow(row)

OUT_SQL.write_text("\n".join(sql_lines) + "\n", encoding="utf-8")

print("WROTE", OUT_CSV)
print("WROTE", OUT_SQL)
print("TOTAL", len(plan))
print("SAFE_RELINK", sum(1 for r in plan if r["action"] == "SAFE_RELINK"))
print("KEEP_AS_IS", sum(1 for r in plan if r["action"] == "KEEP_AS_IS"))
print("MANUAL_REVIEW", sum(1 for r in plan if r["action"] == "MANUAL_REVIEW"))

cur.close()
conn.close()
