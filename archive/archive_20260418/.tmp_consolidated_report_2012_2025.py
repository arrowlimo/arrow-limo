#!/usr/bin/env python3
"""
Generate consolidated reconciliation report for 2012-2025
Combines results from 2012-2017 repair and 2018-2025 LMS sync
"""
import psycopg2
import pandas as pd
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

print("\n" + "="*80)
print("CONSOLIDATED RECONCILIATION REPORT: 2012-2025")
print("="*80)

# Get full 2012-2025 audit
q_full = """
SELECT 
    c.reserve_number,
    c.charter_date,
    c.total_amount_due,
    c.balance,
    SUM(CASE WHEN p.payment_date IS NOT NULL THEN ABS(p.amount) ELSE 0 END) AS payments_sum,
    COUNT(p.payment_id) AS payment_count,
    EXTRACT(YEAR FROM c.charter_date)::int AS year
FROM charters c
LEFT JOIN payments p ON c.reserve_number = p.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) BETWEEN 2012 AND 2025
GROUP BY c.reserve_number, c.charter_date, c.total_amount_due, c.balance, year
ORDER BY year, c.reserve_number
"""

df_full = pd.read_sql_query(q_full, conn)

# Reconciliation logic
df_full['expected_balance'] = df_full['total_amount_due'] - df_full['payments_sum']
df_full['variance'] = df_full['balance'] - df_full['expected_balance']
df_full['match_status'] = df_full['variance'].apply(
    lambda x: 'EXACT' if abs(x) < 0.01 else ('OVERPAID' if x > 0 else 'UNDERPAID')
)

# Summary stats
exact_count = (df_full['match_status'] == 'EXACT').sum()
overpaid_count = (df_full['match_status'] == 'OVERPAID').sum()
underpaid_count = (df_full['match_status'] == 'UNDERPAID').sum()
total_charters = len(df_full)

print(f"\nOVERALL RECONCILIATION METRICS (2012-2025):")
print("-" * 80)
print(f"Total charters:         {total_charters:,}")
print(f"Exact matches:          {exact_count:,} ({100*exact_count/total_charters:.1f}%)")
print(f"Overpaid:               {overpaid_count:,} ({100*overpaid_count/total_charters:.2f}%)")
print(f"Underpaid:              {underpaid_count:,} ({100*underpaid_count/total_charters:.2f}%)")

print(f"\nRESULTS BY YEAR:")
print("-" * 80)
year_summary = df_full.groupby('year').agg({
    'reserve_number': 'count',
    'match_status': lambda x: (x == 'EXACT').sum(),
    'variance': lambda x: (x > 0).sum()  # overpaid
}).rename(columns={'reserve_number': 'Total', 'match_status': 'Exact', 'variance': 'Overpaid'})
year_summary['Exact %'] = (100 * year_summary['Exact'] / year_summary['Total']).round(1)
print(year_summary)

print(f"\nPHASE BREAKDOWN:")
print("-" * 80)
df_2012_2017 = df_full[df_full['year'] <= 2017]
df_2018_2025 = df_full[df_full['year'] >= 2018]

print(f"2012-2017 (Manual cleanup phase):  {len(df_2012_2017):,} charters")
print(f"  - Exact: {(df_2012_2017['match_status'] == 'EXACT').sum():,} ({100*(df_2012_2017['match_status'] == 'EXACT').sum()/len(df_2012_2017):.1f}%)")
print(f"  - Overpaid: {(df_2012_2017['match_status'] == 'OVERPAID').sum():,}")

print(f"\n2018-2025 (LMS sync phase):  {len(df_2018_2025):,} charters")
print(f"  - Exact: {(df_2018_2025['match_status'] == 'EXACT').sum():,} ({100*(df_2018_2025['match_status'] == 'EXACT').sum()/len(df_2018_2025):.1f}%)")
print(f"  - Overpaid: {(df_2018_2025['match_status'] == 'OVERPAID').sum():,}")

# Remaining issues
if overpaid_count > 0:
    print(f"\nREMAINING OVERPAID RESERVES (Top 30):")
    print("-" * 80)
    overpaid = df_full[df_full['match_status'] == 'OVERPAID'].sort_values('variance', ascending=False)
    print(overpaid[['reserve_number', 'year', 'total_amount_due', 'payments_sum', 'balance', 'variance']].head(30).to_string(index=False))
    print(f"\nTotal overpaid amount: ${df_full[df_full['match_status'] == 'OVERPAID']['variance'].sum():,.2f}")

if underpaid_count > 0:
    print(f"\nREMAINING UNDERPAID RESERVES (Top 30):")
    print("-" * 80)
    underpaid = df_full[df_full['match_status'] == 'UNDERPAID'].sort_values('variance')
    print(underpaid[['reserve_number', 'year', 'total_amount_due', 'payments_sum', 'balance', 'variance']].head(30).to_string(index=False))
    print(f"\nTotal underpaid amount: ${-df_full[df_full['match_status'] == 'UNDERPAID']['variance'].sum():,.2f}")

# Save detailed report
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
report_file = f"l:\\limo\\reports\\consolidated_reconciliation_2012_2025_{timestamp}.csv"
df_full.to_csv(report_file, index=False)
print(f"\n✓ Detailed report saved: {report_file}")

# Save summary to JSON
import json
summary_data = {
    'timestamp': datetime.now().isoformat(),
    'date_range': '2012-2025',
    'total_charters': int(total_charters),
    'exact_matches': int(exact_count),
    'exact_percentage': round(100*exact_count/total_charters, 2),
    'overpaid_count': int(overpaid_count),
    'overpaid_percentage': round(100*overpaid_count/total_charters, 4),
    'underpaid_count': int(underpaid_count),
    'underpaid_percentage': round(100*underpaid_count/total_charters, 4),
    'total_overpaid_amount': round(float(df_full[df_full['match_status'] == 'OVERPAID']['variance'].sum()), 2),
    'total_underpaid_amount': round(float(-df_full[df_full['match_status'] == 'UNDERPAID']['variance'].sum()), 2),
    'phases': {
        '2012-2017_manual_cleanup': {
            'charters': int(len(df_2012_2017)),
            'exact': int((df_2012_2017['match_status'] == 'EXACT').sum()),
            'overpaid': int((df_2012_2017['match_status'] == 'OVERPAID').sum())
        },
        '2018-2025_lms_sync': {
            'charters': int(len(df_2018_2025)),
            'exact': int((df_2018_2025['match_status'] == 'EXACT').sum()),
            'overpaid': int((df_2018_2025['match_status'] == 'OVERPAID').sum())
        }
    }
}

summary_json_file = f"l:\\limo\\reports\\consolidated_reconciliation_summary_{timestamp}.json"
with open(summary_json_file, 'w') as f:
    json.dump(summary_data, f, indent=2)
print(f"✓ Summary JSON saved: {summary_json_file}")

conn.close()
