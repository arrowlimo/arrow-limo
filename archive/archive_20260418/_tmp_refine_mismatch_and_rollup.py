import csv
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
AUDIT_DIR = Path(r"l:\limo\data\audit")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

MISMATCH_CSV = Path(r"l:\limo\data\audit\strict_mismatch_review_queue_20260407_191913.csv")
DUP_CSV = Path(r"l:\limo\data\audit\duplicate_pairs_priority_queue_20260407_190606.csv")

if not MISMATCH_CSV.exists():
    raise SystemExit(f"Missing mismatch csv: {MISMATCH_CSV}")
if not DUP_CSV.exists():
    raise SystemExit(f"Missing duplicate csv: {DUP_CSV}")

# 1) Build high-confidence subset from strict mismatch queue
hi_ids = set()
lo_ids = set()
mismatch_rows = []
with MISMATCH_CSV.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        mismatch_rows.append(row)
        rid = int(row["receipt_id"])
        score = int(float(row["score"] or 0))
        reasons = row.get("reasons", "")
        if score >= 95 and "corr_signal_mismatch" in reasons:
            hi_ids.add(rid)
        else:
            lo_ids.add(rid)

# Keep only those currently tagged REVIEW_MISMATCH to avoid touching unrelated rows
conn = psycopg2.connect(**DB)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT receipt_id
    FROM receipts
    WHERE receipt_review_status = 'REVIEW_MISMATCH'
""")
current_mismatch_ids = {r["receipt_id"] for r in cur.fetchall()}

hi_ids = sorted(hi_ids.intersection(current_mismatch_ids))
lo_ids = sorted(lo_ids.intersection(current_mismatch_ids))
all_touch = sorted(set(hi_ids).union(lo_ids))

# Backup before refinement
cur.execute("CREATE TABLE IF NOT EXISTS backup_easyfix_mismatch_refine_20260407 AS SELECT * FROM receipts WHERE 1=0")
if all_touch:
    cur.execute("INSERT INTO backup_easyfix_mismatch_refine_20260407 SELECT * FROM receipts WHERE receipt_id = ANY(%s)", (all_touch,))

# Refine tags
hi_updated = 0
lo_updated = 0
if hi_ids:
    cur.execute(
        """
        UPDATE receipts
        SET receipt_review_status = 'REVIEW_MISM_HI',
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                'Refined 2026-04-07: high-confidence mismatch (score>=95 with correction-signal mismatch).',
            updated_at = NOW()
        WHERE receipt_id = ANY(%s)
        """,
        (hi_ids,),
    )
    hi_updated = cur.rowcount

if lo_ids:
    cur.execute(
        """
        UPDATE receipts
        SET receipt_review_status = 'REVIEW_MISM_LO',
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\n' END ||
                'Refined 2026-04-07: lower-confidence mismatch (keep for manual review queue).',
            updated_at = NOW()
        WHERE receipt_id = ANY(%s)
        """,
        (lo_ids,),
    )
    lo_updated = cur.rowcount

# 2) Create focused 8362<->1615 shortlist from duplicate queue
shortlist = []
with DUP_CSV.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        reasons = row.get("reasons", "")
        priority = row.get("priority", "")
        if "cross_account_8362_1615" in reasons and priority in {"HIGH", "MEDIUM"}:
            shortlist.append(row)

shortlist_path = AUDIT_DIR / f"shortlist_8362_1615_conflicts_{STAMP}.csv"
with shortlist_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow([
        "priority", "score", "reasons",
        "receipt_id_1", "date_1", "account_1", "banking_txn_1", "vendor_1", "description_1",
        "receipt_id_2", "date_2", "account_2", "banking_txn_2", "vendor_2", "description_2",
        "vendor_norm", "amount", "day_gap"
    ])
    for row in shortlist:
        w.writerow([
            row.get("priority"), row.get("score"), row.get("reasons"),
            row.get("receipt_id_1"), row.get("date_1"), row.get("account_1"), row.get("banking_txn_1"), row.get("vendor_1"), row.get("description_1"),
            row.get("receipt_id_2"), row.get("date_2"), row.get("account_2"), row.get("banking_txn_2"), row.get("vendor_2"), row.get("description_2"),
            row.get("vendor_norm"), row.get("amount"), row.get("day_gap")
        ])

# 3) Rollup summary
cur.execute("SELECT COUNT(*) AS c FROM backup_easyfix_mismatch_refine_20260407")
backup_rows = cur.fetchone()["c"]

cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status = 'REVIEW_MISM_HI'")
status_hi_total = cur.fetchone()["c"]
cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status = 'REVIEW_MISM_LO'")
status_lo_total = cur.fetchone()["c"]
cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status = 'DUP_SAME_BANKING'")
dup_same_banking_total = cur.fetchone()["c"]
cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE receipt_review_status = 'NON_EXPENSE_REV'")
non_expense_rev_total = cur.fetchone()["c"]

conn.commit()
cur.close()
conn.close()

summary_path = AUDIT_DIR / f"refine_mismatch_rollup_summary_{STAMP}.txt"
summary_path.write_text(
    "\n".join([
        "REFINEMENT ROLLUP SUMMARY",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Mismatch refinement:",
        f"- REVIEW_MISM_HI updated in this pass: {hi_updated}",
        f"- REVIEW_MISM_LO updated in this pass: {lo_updated}",
        f"- Backup rows captured: {backup_rows}",
        "",
        "Current review status totals:",
        f"- REVIEW_MISM_HI: {status_hi_total}",
        f"- REVIEW_MISM_LO: {status_lo_total}",
        f"- DUP_SAME_BANKING: {dup_same_banking_total}",
        f"- NON_EXPENSE_REV: {non_expense_rev_total}",
        "",
        "Conflict shortlist:",
        f"- 8362<->1615 HIGH/MEDIUM rows: {len(shortlist)}",
        f"- File: {shortlist_path}",
        "",
        "No deletions were performed.",
    ]),
    encoding="utf-8",
)

print(f"HI_UPDATED: {hi_updated}")
print(f"LO_UPDATED: {lo_updated}")
print(f"SHORTLIST_COUNT: {len(shortlist)}")
print(f"SHORTLIST_FILE: {shortlist_path}")
print(f"SUMMARY_FILE: {summary_path}")
