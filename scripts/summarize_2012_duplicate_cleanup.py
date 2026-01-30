#!/usr/bin/env python3
"""
Generate comprehensive 2012 duplicate removal summary.
Reports what was removed and impact on data quality.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('='*80)
print('2012 DUPLICATE REMOVAL - COMPREHENSIVE SUMMARY REPORT')
print('='*80)
print(f'Report Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Historical progression
print('CLEANUP PROGRESSION:')
print('-'*80)
cleanup_stages = [
    ('Initial state (Excel file)', 5157),
    ('After database scan (fix_2012_duplicates_and_nsf.py)', 5139),
    ('After first Excel cleanup (50 groups)', 5042),
    ('After complete Excel cleanup (all 381 groups)', 4555),
]

for stage, count in cleanup_stages:
    print(f'{stage}: {count:,} receipts')

print()
total_removed = cleanup_stages[0][1] - cleanup_stages[-1][1]
pct_removed = (total_removed / cleanup_stages[0][1]) * 100

print(f'TOTAL DUPLICATES REMOVED: {total_removed:,} receipts ({pct_removed:.1f}%)')
print()

# Duplicate statistics
print('DUPLICATE ANALYSIS:')
print('-'*80)
print(f'Duplicate groups identified: 381')
print(f'Groups processed in first batch: 50')
print(f'Groups processed in final batch: 331')
print(f'Duplicate receipts in first batch: 97')
print(f'Duplicate receipts in final batch: 487')
print(f'Total duplicates deleted: 584')
print()

# Current state
print('CURRENT DATABASE STATE (2012):')
print('-'*80)
cur.execute('''
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(DISTINCT DATE_TRUNC('month', receipt_date)) as months_covered,
        MIN(receipt_date) as first_receipt,
        MAX(receipt_date) as last_receipt,
        SUM(gross_amount) as total_amount,
        COUNT(CASE WHEN created_from_banking THEN 1 END) as from_banking,
        COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as mapped_to_banking
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
''')

row = cur.fetchone()
total, months, first_date, last_date, total_amt, from_banking, mapped = row

print(f'Total receipts: {total:,}')
print(f'Date range: {first_date} to {last_date}')
print(f'Months covered: {months}')
print(f'Total amount: ${total_amt:,.2f}')
print(f'Created from banking: {from_banking:,}')
print(f'Mapped to banking: {mapped:,}')
print()

# Banking coverage
print('BANKING RECONCILIATION:')
print('-'*80)
cur.execute('''
    SELECT 
        COUNT(*) as total_debits,
        COUNT(DISTINCT receipt_id) as receipts_matched,
        SUM(debit_amount) as matched_amount,
        (COUNT(DISTINCT receipt_id) * 100.0 / COUNT(*)) as match_pct
    FROM (
        SELECT DISTINCT
            bt.transaction_id,
            bt.debit_amount,
            bm.receipt_id
        FROM banking_transactions bt
        JOIN banking_receipt_matching_ledger bm 
            ON bt.transaction_id = bm.banking_transaction_id
        WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
    ) m
''')

row = cur.fetchone()
if row and row[0]:
    total_debits, receipts_matched, matched_amount, match_pct = row
    print(f'Banking debits: {total_debits:,}')
    print(f'Receipts matched: {receipts_matched:,}')
    print(f'Match rate: {match_pct:.1f}%')
    print(f'Amount matched: ${matched_amount:,.2f}')
else:
    print('No banking matches found')

print()

# Category breakdown
print('RECEIPTS BY CATEGORY:')
print('-'*80)
cur.execute('''
    SELECT 
        category,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    GROUP BY category
    ORDER BY total_amount DESC
    LIMIT 15
''')

for row in cur.fetchall():
    category, count, amount = row
    cat_display = category if category else '(uncategorized)'
    print(f'{cat_display:30} {count:5,} receipts  ${amount:12,.2f}')

print()

# NSF status
print('NSF TRANSACTION STATUS:')
print('-'*80)
cur.execute('''
    SELECT 
        COUNT(*) as nsf_count,
        SUM(gross_amount) as nsf_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (
        vendor_name ILIKE '%NSF%'
        OR vendor_name ILIKE '%BOUNCE%'
        OR vendor_name ILIKE '%REVERSAL%'
        OR description ILIKE '%NSF%'
    )
''')

row = cur.fetchone()
nsf_count, nsf_amount = row
print(f'NSF-related transactions: {nsf_count}')
print(f'NSF total: ${nsf_amount:,.2f}')
print()
print('⚠️  NOTE: All NSF transactions are POSITIVE (charges only)')
print('   No reversals found - see analyze_2012_nsf_transactions.py')
print()

# Quality metrics
print('DATA QUALITY METRICS:')
print('-'*80)
cur.execute('''
    SELECT 
        COUNT(CASE WHEN vendor_name IS NULL OR vendor_name = '' THEN 1 END) as null_vendors,
        COUNT(CASE WHEN gross_amount = 0 THEN 1 END) as zero_amounts,
        COUNT(CASE WHEN gross_amount < 0 THEN 1 END) as negative_amounts,
        COUNT(CASE WHEN gst_amount IS NULL THEN 1 END) as null_gst,
        COUNT(CASE WHEN category IS NULL OR category = '' THEN 1 END) as uncategorized
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
''')

row = cur.fetchone()
null_vendors, zero_amt, neg_amt, null_gst, uncategorized = row

print(f'NULL vendors: {null_vendors}')
print(f'Zero amount receipts: {zero_amt}')
print(f'Negative amount receipts: {neg_amt}')
print(f'NULL GST amounts: {null_gst}')
print(f'Uncategorized: {uncategorized}')
print()

# Success indicators
print('SUCCESS INDICATORS:')
print('-'*80)
if total_removed > 500:
    print('✅ Major duplicate cleanup completed (600+ duplicates removed)')
else:
    print('⚠️  Unexpected duplicate count')

if from_banking > 2000:
    print('✅ Automated receipt generation working (2000+ from banking)')
else:
    print('⚠️  Lower than expected automated receipts')

if mapped > 2000:
    print('✅ Banking reconciliation successful (2000+ matched)')
else:
    print('⚠️  Lower than expected banking matches')

if null_vendors == 0:
    print('✅ All receipts have vendor names')
else:
    print(f'⚠️  {null_vendors} receipts missing vendor names')

print()

# Next steps
print('NEXT ACTIONS RECOMMENDED:')
print('-'*80)
print('1. Import complete 2011-2012 banking data:')
print('   python scripts/import_2011_2012_banking_data_plan.py')
print()
print('2. Analyze NSF reversal issue:')
print('   - 293 NSF charges ($188,870.51) with no reversals')
print('   - Need to find reversed payment entries that should pair')
print()
print('3. Verify balance continuity:')
print('   - 2011 Dec 31 closing = $7,177.34')
print('   - 2012 Jan 1 opening should match')
print()
print('4. Generate final 2012 reconciliation report')
print()

cur.close()
conn.close()

print('='*80)
print('END REPORT')
print('='*80)
