import pandas as pd
import psycopg2
from pathlib import Path

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
OVERPAY_CSV = r"L:\limo\reports\overpaid_analysis_2012_2017_20260417_214440.csv"
BLOCKED_CSV = r"L:\limo\reports\synthetic_cleanup_blocked_reserves_20260417_214421.csv"
REPORT = Path(r"L:\limo\reports\final_residual_overpay_buckets_20260417_214440.csv")

special_cases = {
    '006341': 'user-confirmed bounced-check special case; keep',
    '006311': 'legacy credit-card residual; review manually',
    '007504': 'credit adjustment special case; keep/review',
    '006504': 'already fixed special-case refund',
}

blocked = set()
blocked_path = Path(BLOCKED_CSV)
if blocked_path.exists():
    blocked = set(pd.read_csv(blocked_path, dtype={'reserve_number': str})['reserve_number'].tolist())

over = pd.read_csv(OVERPAY_CSV, dtype={'reserve_number': str})
conn = psycopg2.connect(**PG)
pay = pd.read_sql_query(
    """
    SELECT reserve_number, COALESCE(notes,'') AS notes, COUNT(*) AS rows, SUM(amount) AS amount
    FROM payments
    WHERE reserve_number = ANY(%s)
    GROUP BY reserve_number, COALESCE(notes,'')
    ORDER BY reserve_number, amount DESC
    """,
    conn,
    params=(over['reserve_number'].dropna().tolist(),),
)
conn.close()

bucket_rows = []
for _, row in over.iterrows():
    reserve = row['reserve_number']
    notes = pay[pay['reserve_number'] == reserve]
    note_set = set(notes['notes'].tolist())
    category = 'manual_review'
    detail = ''

    if reserve in special_cases:
        category = 'special_case_keep_or_manual'
        detail = special_cases[reserve]
    elif reserve in blocked:
        category = 'fk_blocked_synthetic_duplicate'
        detail = 'synthetic duplicate rows remain but payment rows are externally referenced'
    elif row.get('cancelled') is True or str(row.get('status', '')).lower() == 'cancelled':
        category = 'cancelled_non_nrr_overpay'
        detail = 'cancelled reserve with retained payment'
    elif 'LMS screenshot reconcile 2026-02-25 (missing payment line)' in note_set:
        category = 'screenshot_reconcile_duplicate'
        detail = 'screenshot reconcile row appears alongside LMS sync/import rows'
    elif 'Inserted from LMS2026d payment sync' in note_set and 'Backfilled from charter_payments' in note_set:
        category = 'backfill_plus_sync_overlap'
        detail = 'old backfill rows overlap with authoritative LMS sync rows'
    elif 'Inserted from LMS2026d payment sync' in note_set and 'LMS-verified balancing payment - 2012 import gap' in note_set:
        category = 'gapfill_plus_sync_overlap'
        detail = 'old 2012 gapfill row overlaps with authoritative LMS sync rows'
    elif 'Backfilled from charter_payments' in note_set and 'LMS-verified balancing payment - 2012 import gap' in note_set:
        category = 'two_synthetic_sources_overlap'
        detail = 'two synthetic local sources remain without LMS sync note'
    elif '' in note_set and len(note_set) == 1:
        category = 'blank_note_legacy_rows'
        detail = 'only blank-note legacy payment rows remain'
    elif '' in note_set:
        category = 'blank_note_plus_other_overlap'
        detail = 'legacy blank-note rows overlap with named synthetic/import rows'

    bucket_rows.append({
        'reserve_number': reserve,
        'variance': row['variance'],
        'payment_sum': row['payment_sum'],
        'total_amount_due': row['total_amount_due'],
        'status': row['status'],
        'cancelled': row['cancelled'],
        'payment_methods': row['payment_methods'],
        'category': category,
        'detail': detail,
        'notes_present': ' | '.join(notes['notes'].tolist()),
    })

out = pd.DataFrame(bucket_rows).sort_values(['category', 'variance'], ascending=[True, False])
out.to_csv(REPORT, index=False)
print(out.groupby('category').agg(reserve_count=('reserve_number','size'), variance_sum=('variance','sum')).reset_index().to_string(index=False))
print(f'written={REPORT}')
