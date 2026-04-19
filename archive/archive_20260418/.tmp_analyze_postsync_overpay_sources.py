import pandas as pd
import psycopg2

PG = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
OVERPAY_CSV = r"L:\limo\reports\overpaid_analysis_2012_2017_20260417_213945.csv"

conn = psycopg2.connect(**PG)
over = pd.read_csv(OVERPAY_CSV, dtype={'reserve_number': str})
reserves = over['reserve_number'].dropna().tolist()

pay = pd.read_sql_query(
    """
    SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method, status, COALESCE(notes,'') AS notes
    FROM payments
    WHERE reserve_number = ANY(%s)
    ORDER BY reserve_number, payment_date, payment_id
    """,
    conn,
    params=(reserves,),
)
conn.close()

note_summary = (
    pay.groupby('notes', dropna=False)
    .agg(
        reserve_count=('reserve_number', 'nunique'),
        payment_rows=('payment_id', 'size'),
        total_amount=('amount', 'sum'),
    )
    .reset_index()
    .sort_values(['reserve_count', 'total_amount'], ascending=[False, False])
)
print('NOTE SUMMARY')
print(note_summary.head(20).to_string(index=False))

synthetic_notes = {
    'LMS-verified balancing payment - 2012 import gap',
    'Backfilled from charter_payments',
}
synthetic = pay[pay['notes'].isin(synthetic_notes)].copy()
if synthetic.empty:
    print('\nNo synthetic-note rows found.')
else:
    syn_by_reserve = (
        synthetic.groupby(['reserve_number', 'notes'], dropna=False)
        .agg(synthetic_amount=('amount', 'sum'), synthetic_rows=('payment_id', 'size'))
        .reset_index()
    )
    print('\nSYNTHETIC NOTE BREAKDOWN')
    print(syn_by_reserve.head(50).to_string(index=False))

    syn_total = (
        synthetic.groupby('reserve_number', dropna=False)
        .agg(synthetic_total=('amount', 'sum'))
        .reset_index()
    )
    merged = over.merge(syn_total, on='reserve_number', how='left').fillna({'synthetic_total': 0})
    merged['variance'] = pd.to_numeric(merged['variance'], errors='coerce').fillna(0).round(2)
    merged['synthetic_total'] = pd.to_numeric(merged['synthetic_total'], errors='coerce').fillna(0).round(2)
    merged['variance_minus_synthetic'] = (merged['variance'] - merged['synthetic_total']).round(2)
    exact_if_removed = merged[merged['variance_minus_synthetic'].abs() <= 0.01].copy()
    print('\nEXACT IF SYNTHETIC REMOVED')
    print('count', len(exact_if_removed), 'variance_sum', round(exact_if_removed['variance'].sum(), 2), 'synthetic_sum', round(exact_if_removed['synthetic_total'].sum(), 2))
    print(exact_if_removed[['reserve_number','variance','synthetic_total','variance_minus_synthetic']].head(100).to_string(index=False))

    remaining = merged[merged['variance_minus_synthetic'].abs() > 0.01].copy()
    print('\nTOP REMAINING AFTER SYNTHETIC REMOVAL')
    print(remaining.sort_values('variance_minus_synthetic', ascending=False).head(50)[['reserve_number','variance','synthetic_total','variance_minus_synthetic']].to_string(index=False))
