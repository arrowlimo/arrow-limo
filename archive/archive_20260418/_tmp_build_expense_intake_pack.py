#!/usr/bin/env python3
"""
Build actionable intake files for:
1) Missing receipt intake from unlinked banking debits
2) Invoice-link gaps on receipts
3) ITC candidate receipts
"""

from pathlib import Path
import psycopg2
import csv

OUT_DIR = Path(r"L:\limo\data\intake")
OUT_DIR.mkdir(parents=True, exist_ok=True)

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

# 1) Missing receipt intake pool
cur.execute(
    """
    SELECT
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        category,
        vendor_extracted
    FROM banking_transactions
    WHERE debit_amount > 0
      AND receipt_id IS NULL
    ORDER BY debit_amount DESC, transaction_date
    """
)
rows = cur.fetchall()
missing_receipts_csv = OUT_DIR / "missing_receipt_intake_queue.csv"
with missing_receipts_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["transaction_id", "transaction_date", "description", "debit_amount", "category", "vendor_extracted"])
    w.writerows(rows)

# 2) Receipts missing vendor invoice links
cur.execute(
    """
    SELECT
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.canonical_vendor,
        r.gross_amount,
        r.description,
        r.gl_account_code,
        r.payment_method,
        r.receipt_source
    FROM receipts r
    WHERE NOT EXISTS (
        SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id = r.receipt_id
    )
    ORDER BY r.gross_amount DESC, r.receipt_date
    """
)
rows = cur.fetchall()
invoice_gap_csv = OUT_DIR / "receipts_missing_invoice_link.csv"
with invoice_gap_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow([
        "receipt_id", "receipt_date", "vendor_name", "canonical_vendor", "gross_amount",
        "description", "gl_account_code", "payment_method", "receipt_source"
    ])
    w.writerows(rows)

# 3) ITC candidates (simple conservative rule)
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_name='receipts'
ORDER BY column_name
""")
cols = {r[0] for r in cur.fetchall()}

where_parts = ["COALESCE(r.gst_amount,0) > 0"]
if 'is_personal_purchase' in cols:
    where_parts.append("COALESCE(r.is_personal_purchase,false)=false")
if 'owner_personal_amount' in cols:
    where_parts.append("COALESCE(r.owner_personal_amount,0)=0")
if 'exclude_from_reports' in cols:
    where_parts.append("COALESCE(r.exclude_from_reports,false)=false")

where_sql = " AND ".join(where_parts)
cur.execute(
    f"""
    SELECT
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.canonical_vendor,
        r.gross_amount,
        r.gst_amount,
        r.gl_account_code,
        r.description,
        r.payment_method,
        r.receipt_source
    FROM receipts r
    WHERE {where_sql}
    ORDER BY r.gst_amount DESC, r.receipt_date
    """
)
rows = cur.fetchall()
itc_csv = OUT_DIR / "itc_candidate_receipts.csv"
with itc_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow([
        "receipt_id", "receipt_date", "vendor_name", "canonical_vendor", "gross_amount",
        "gst_amount", "gl_account_code", "description", "payment_method", "receipt_source"
    ])
    w.writerows(rows)

# Summary
cur.execute("SELECT COUNT(*), COALESCE(SUM(gross_amount),0) FROM income_ledger WHERE source_system='charter_payments'")
ledger_count, ledger_total = cur.fetchone()
cur.execute("SELECT COUNT(*), COALESCE(SUM(gross_amount),0), COALESCE(SUM(gst_amount),0) FROM receipts")
r_count, r_total, r_gst = cur.fetchone()
cur.execute("SELECT COUNT(*), COALESCE(SUM(debit_amount),0) FROM banking_transactions WHERE debit_amount > 0 AND receipt_id IS NULL")
unlinked_count, unlinked_total = cur.fetchone()

print(f"ledger_rows={ledger_count} ledger_total={ledger_total}")
print(f"receipts_rows={r_count} receipts_total={r_total} receipts_gst_total={r_gst}")
print(f"unlinked_debits={unlinked_count} unlinked_debit_total={unlinked_total}")
print(f"missing_receipt_file={missing_receipts_csv}")
print(f"invoice_gap_file={invoice_gap_csv}")
print(f"itc_file={itc_csv}")

cur.close()
conn.close()
