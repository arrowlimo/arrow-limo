import csv
from pathlib import Path
from datetime import datetime

AUDIT_DIR = Path(r"l:\limo\data\audit")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

nsf_csv = Path(r"l:\limo\data\audit\nsf_correction_high_conf_candidates_20260407_190606.csv")
dup_csv = Path(r"l:\limo\data\audit\duplicate_pairs_priority_queue_20260407_190606.csv")

if not nsf_csv.exists() or not dup_csv.exists():
    raise SystemExit("Expected input CSVs not found")

# 1) Build SQL preview (DO NOT EXECUTE)
sql_preview = AUDIT_DIR / f"review_only_nsf_correction_flag_updates_{STAMP}.sql"

nsf_rows = []
with nsf_csv.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        nsf_rows.append(row)

# High-confidence subset: explicit NSF keyword suggestions only
high_conf_ids = [
    int(r["receipt_id"])
    for r in nsf_rows
    if r.get("suggest_set_is_nsf", "").lower() == "true"
       and "keyword_nsf" in (r.get("reason") or "")
]

with sql_preview.open("w", encoding="utf-8") as f:
    f.write("-- REVIEW ONLY: NSF/CORRECTION FLAG UPDATE PREVIEW\n")
    f.write("-- Generated automatically; do NOT execute blindly.\n")
    f.write("-- Validate sample rows first.\n\n")
    f.write(f"-- Candidate rows (high-confidence NSF): {len(high_conf_ids)}\n\n")

    if high_conf_ids:
        ids = ",".join(str(x) for x in sorted(high_conf_ids))
        f.write("-- PREVIEW TARGET ROWS\n")
        f.write("SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, is_nsf, exclude_from_reports\n")
        f.write(f"FROM receipts WHERE receipt_id IN ({ids}) ORDER BY receipt_date, receipt_id;\n\n")

        f.write("-- PROPOSED UPDATE\n")
        f.write("-- UPDATE receipts\n")
        f.write("-- SET is_nsf = TRUE,\n")
        f.write("--     exclude_from_reports = TRUE,\n")
        f.write("--     updated_at = NOW()\n")
        f.write(f"-- WHERE receipt_id IN ({ids});\n\n")

        f.write("-- POST-UPDATE CHECK\n")
        f.write("SELECT COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt\n")
        f.write("FROM receipts\n")
        f.write(f"WHERE receipt_id IN ({ids})\n")
        f.write("  AND is_nsf = TRUE AND exclude_from_reports = TRUE;\n")

# 2) Build recommendation CSV for high-confidence duplicates
reco_csv = AUDIT_DIR / f"duplicate_high_conf_keep_drop_recommendations_{STAMP}.csv"

rows = []
with dup_csv.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

high_rows = [
    r for r in rows
    if r.get("priority") == "HIGH"
       and "same_banking_transaction" in (r.get("reasons") or "")
]

with reco_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow([
        "receipt_id_keep", "receipt_id_review_drop", "reason", "vendor_norm", "amount",
        "date_keep", "date_drop", "banking_txn", "account_keep", "account_drop",
        "description_keep", "description_drop"
    ])

    for r in high_rows:
        rid1 = int(r["receipt_id_1"])
        rid2 = int(r["receipt_id_2"])

        # Keep older (lower id) by default for deterministic review; user can override.
        keep = min(rid1, rid2)
        drop = max(rid1, rid2)

        if keep == rid1:
            date_keep, date_drop = r["date_1"], r["date_2"]
            acc_keep, acc_drop = r["account_1"], r["account_2"]
            d_keep, d_drop = r["description_1"], r["description_2"]
            bt = r["banking_txn_1"]
        else:
            date_keep, date_drop = r["date_2"], r["date_1"]
            acc_keep, acc_drop = r["account_2"], r["account_1"]
            d_keep, d_drop = r["description_2"], r["description_1"]
            bt = r["banking_txn_2"]

        w.writerow([
            keep,
            drop,
            "same_banking_transaction_high_confidence",
            r["vendor_norm"],
            r["amount"],
            date_keep,
            date_drop,
            bt,
            acc_keep,
            acc_drop,
            d_keep,
            d_drop,
        ])

summary = AUDIT_DIR / f"review_artifacts_summary_{STAMP}.txt"
summary.write_text(
    "\n".join([
        "REVIEW ARTIFACTS SUMMARY",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"SQL preview file: {sql_preview}",
        f"High-confidence NSF candidate count in SQL preview: {len(high_conf_ids)}",
        "",
        f"Duplicate keep/drop recommendation CSV: {reco_csv}",
        f"High-confidence same-banking pairs: {len(high_rows)}",
        "",
        "No updates/deletes executed.",
    ]),
    encoding="utf-8",
)

print(f"SQL_PREVIEW: {sql_preview}")
print(f"RECO_CSV: {reco_csv}")
print(f"SUMMARY: {summary}")
print(f"NSF_HIGH_CONF: {len(high_conf_ids)}")
print(f"DUP_HIGH_SAME_BANKING: {len(high_rows)}")
