import csv
from pathlib import Path
from datetime import datetime

import psycopg2

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
SHORTLIST = Path(r"l:\limo\data\audit\shortlist_8362_1615_conflicts_20260407_192218.csv")

if not SHORTLIST.exists():
    raise SystemExit(f"Missing shortlist file: {SHORTLIST}")

safe_pairs = []
manual_pairs = []

with SHORTLIST.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        reasons = row.get("reasons", "")
        is_safe = ("same_day" in reasons) and ("both_auto_generated" in reasons)
        rec = {
            "r1": int(row["receipt_id_1"]),
            "r2": int(row["receipt_id_2"]),
            "a1": str(row.get("account_1") or ""),
            "a2": str(row.get("account_2") or ""),
            "reasons": reasons,
            "score": int(float(row.get("score") or 0)),
            "amount": row.get("amount"),
            "day_gap": int(float(row.get("day_gap") or 0)),
        }
        if is_safe:
            safe_pairs.append(rec)
        else:
            manual_pairs.append(rec)

# For safe pairs, mark 8362-side as duplicate-candidate against 1615-side
safe_target_ids = []
safe_notes = []
for p in safe_pairs:
    if "8362" in p["a1"] and "1615" in p["a2"]:
        dup_id, keep_id = p["r1"], p["r2"]
    elif "1615" in p["a1"] and "8362" in p["a2"]:
        dup_id, keep_id = p["r2"], p["r1"]
    else:
        # Fallback: do not auto-assign if account strings are unexpected
        continue
    safe_target_ids.append(dup_id)
    safe_notes.append((dup_id, keep_id, p["score"], p["reasons"], p["amount"]))

manual_ids = sorted({x["r1"] for x in manual_pairs}.union({x["r2"] for x in manual_pairs}))
all_touch_ids = sorted(set(safe_target_ids).union(manual_ids))

conn = psycopg2.connect(**DB)
cur = conn.cursor()

try:
    # Backup
    cur.execute("CREATE TABLE IF NOT EXISTS backup_easyfix_xacc_refine_20260407 AS SELECT * FROM receipts WHERE 1=0")
    if all_touch_ids:
        cur.execute("INSERT INTO backup_easyfix_xacc_refine_20260407 SELECT * FROM receipts WHERE receipt_id = ANY(%s)", (all_touch_ids,))

    # 1) Safe subset tagging on 8362-side only (no deletions)
    safe_updated = 0
    for dup_id, keep_id, score, reasons, amount in safe_notes:
        cur.execute(
            """
            UPDATE receipts
            SET potential_duplicate = TRUE,
                receipt_review_status = CASE
                    WHEN COALESCE(receipt_review_status,'') = '' THEN 'XACC_DUP_AUTO'
                    ELSE receipt_review_status
                END,
                receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                    CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                    %s,
                updated_at = NOW()
            WHERE receipt_id = %s
            """,
            (
                f"Auto-refine 2026-04-07: cross-account 8362<->1615 safe duplicate candidate. Keep receipt {keep_id}; this row tagged duplicate candidate (score={score}, amount={amount}, reasons={reasons}).",
                dup_id,
            ),
        )
        safe_updated += cur.rowcount

    # 2) Manual review tagging for non-safe shortlist rows
    if manual_ids:
        cur.execute(
            """
            UPDATE receipts
            SET receipt_review_status = CASE
                    WHEN COALESCE(receipt_review_status,'') = '' THEN 'XACC_REVIEW'
                    ELSE receipt_review_status
                END,
                receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                    CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                    'Auto-refine 2026-04-07: in 8362<->1615 shortlist, requires manual cross-account duplicate review.',
                updated_at = NOW()
            WHERE receipt_id = ANY(%s)
            """,
            (manual_ids,),
        )
        manual_updated = cur.rowcount
    else:
        manual_updated = 0

    conn.commit()

    print("XACC_SAFE_SUBSET_APPLIED")
    print("safe_pairs_total", len(safe_pairs))
    print("safe_target_ids", len(set(safe_target_ids)))
    print("safe_rows_updated", safe_updated)
    print("manual_pairs_total", len(manual_pairs))
    print("manual_ids", len(manual_ids))
    print("manual_rows_updated", manual_updated)

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
