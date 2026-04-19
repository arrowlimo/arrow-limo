#!/usr/bin/env python3
"""
Baseline audit for 2018-2025 charters — same logic as 2012-2017
Compares charter balances (invoiced + adjustments) vs payments (pooled receipts)
"""
import psycopg2
import pandas as pd
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

# Get all 2018-2025 charters with balance detail
q_charters = """
SELECT 
    c.reserve_number,
    c.charter_date,
    c.total_amount_due,
    c.balance,
    SUM(CASE WHEN p.payment_date IS NOT NULL THEN ABS(p.amount) ELSE 0 END) AS payments_sum,
    COUNT(p.payment_id) AS payment_count,
    STRING_AGG(DISTINCT p.payment_method, ', ') AS payment_methods
FROM charters c
LEFT JOIN payments p ON c.reserve_number = p.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) BETWEEN 2018 AND 2025
GROUP BY c.reserve_number, c.charter_date, c.total_amount_due, c.balance
ORDER BY c.reserve_number
"""

df_charters = pd.read_sql_query(q_charters, conn)

# Reconciliation logic: balance should equal total_amount_due - payments_sum
df_charters['expected_balance'] = df_charters['total_amount_due'] - df_charters['payments_sum']
df_charters['variance'] = df_charters['balance'] - df_charters['expected_balance']
df_charters['match_status'] = df_charters['variance'].apply(
    lambda x: 'EXACT' if abs(x) < 0.01 else ('OVERPAID' if x > 0 else 'UNDERPAID')
)

# Summary stats
exact_count = (df_charters['match_status'] == 'EXACT').sum()
overpaid_count = (df_charters['match_status'] == 'OVERPAID').sum()
underpaid_count = (df_charters['match_status'] == 'UNDERPAID').sum()
total_charters = len(df_charters)

print("\n" + "="*80)
print("BASELINE AUDIT: 2018-2025 CHARTERS")
print("="*80)
print(f"\nTotal charters:    {total_charters:,}")
print(f"Exact matches:     {exact_count:,} ({100*exact_count/total_charters:.1f}%)")
print(f"Overpaid:          {overpaid_count:,}")
print(f"Underpaid:         {underpaid_count:,}")

# Show overpaid and underpaid charters
if overpaid_count > 0:
    overpaid = df_charters[df_charters['match_status'] == 'OVERPAID'].sort_values('variance', ascending=False)
    print(f"\nTop 20 OVERPAID reserves:")
    print(overpaid[['reserve_number', 'charter_date', 'total_amount_due', 'payments_sum', 'balance', 'variance']].head(20).to_string(index=False))

if underpaid_count > 0:
    underpaid = df_charters[df_charters['match_status'] == 'UNDERPAID'].sort_values('variance')
    print(f"\nTop 20 UNDERPAID reserves:")
    print(underpaid[['reserve_number', 'charter_date', 'total_amount_due', 'payments_sum', 'balance', 'variance']].head(20).to_string(index=False))

# Save detailed report
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
report_file = f"l:\\limo\\reports\\baseline_audit_2018_2025_{timestamp}.csv"
df_charters.to_csv(report_file, index=False)
print(f"\n✓ Detailed report saved: {report_file}")

# Variance summary by year
print("\n" + "-"*80)
print("Variance by Year:")
print("-"*80)
df_charters['year'] = pd.to_datetime(df_charters['charter_date']).dt.year
year_summary = df_charters.groupby('year').agg({
    'reserve_number': 'count',
    'match_status': lambda x: (x == 'EXACT').sum(),
    'variance': lambda x: (x > 0).sum()  # overpaid count
}).rename(columns={'reserve_number': 'total', 'match_status': 'exact', 'variance': 'overpaid'})
print(year_summary)

conn.close()


