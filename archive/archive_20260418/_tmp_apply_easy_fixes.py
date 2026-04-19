import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import psycopg2

nsf_csv = Path(r'l:\limo\data\audit\nsf_correction_high_conf_candidates_20260407_190606.csv')
lease_gst_csv = Path(r'l:\limo\data\audit\lease_2012_2014_gst_backfill_candidates_20260407_190606.csv')
dup_reco_csv = Path(r'l:\limo\data\audit\duplicate_high_conf_keep_drop_recommendations_20260407_190745.csv')

if not nsf_csv.exists() or not lease_gst_csv.exists() or not dup_reco_csv.exists():
    raise SystemExit('Required CSV input missing')

nsf_ids = []
with nsf_csv.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        if row.get('suggest_set_is_nsf','').lower() == 'true' and 'keyword_nsf' in (row.get('reason') or ''):
            nsf_ids.append(int(row['receipt_id']))

lease_rows = []
with lease_gst_csv.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        lease_rows.append((int(row['receipt_id']), Decimal(str(row['expected_gst']))))

# unique review_drop ids only
review_drop_ids = set()
with dup_reco_csv.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        review_drop_ids.add(int(row['receipt_id_review_drop']))

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

try:
    # Backup tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backup_easyfix_receipts_20260407 AS
        SELECT * FROM receipts WHERE 1=0
    """)

    all_target_ids = sorted(set(nsf_ids) | {rid for rid, _ in lease_rows} | review_drop_ids)
    if all_target_ids:
        cur.execute("INSERT INTO backup_easyfix_receipts_20260407 SELECT * FROM receipts WHERE receipt_id = ANY(%s)", (all_target_ids,))

    # 1) NSF easy fixes
    cur.execute(
        """
        UPDATE receipts
        SET is_nsf = TRUE,
            exclude_from_reports = TRUE,
            updated_at = NOW()
        WHERE receipt_id = ANY(%s)
          AND (COALESCE(is_nsf,false)=FALSE OR COALESCE(exclude_from_reports,false)=FALSE)
        """,
        (nsf_ids,)
    )
    nsf_updated = cur.rowcount

    # 2) Lease GST backfill easy fixes
    lease_updated = 0
    for rid, expected_gst in lease_rows:
        cur.execute(
            """
            UPDATE receipts
            SET gst_amount = %s,
                updated_at = NOW()
            WHERE receipt_id = %s
              AND COALESCE(gst_exempt,false)=FALSE
              AND COALESCE(gst_amount,0)=0
            """,
            (expected_gst.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), rid)
        )
        lease_updated += cur.rowcount

    # 3) Mark high-confidence duplicate review-drop candidates (no deletion)
    cur.execute(
        """
        UPDATE receipts
        SET potential_duplicate = TRUE,
            receipt_review_status = COALESCE(NULLIF(receipt_review_status,''), 'DUP_SAME_BANKING'),
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'') = '' THEN '' ELSE E'\\n' END ||
                'Auto-flagged (easy-fix pass): same banking transaction duplicate candidate',
            updated_at = NOW()
        WHERE receipt_id = ANY(%s)
        """,
        (sorted(review_drop_ids),)
    )
    dup_marked = cur.rowcount

    conn.commit()
    print('EASY_FIX_APPLIED')
    print('nsf_target_ids', len(nsf_ids), 'nsf_rows_updated', nsf_updated)
    print('lease_gst_target_ids', len(lease_rows), 'lease_gst_rows_updated', lease_updated)
    print('dup_review_drop_ids', len(review_drop_ids), 'dup_rows_marked', dup_marked)

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
