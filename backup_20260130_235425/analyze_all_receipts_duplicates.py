#!/usr/bin/env python3
"""
Comprehensive analysis of ALL receipts database-wide for duplicates and NSF pairing issues.
Identifies patterns across all years, not just 2012.
"""

import psycopg2
from collections import defaultdict
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('='*80)
print('COMPREHENSIVE RECEIPT ANALYSIS - ALL YEARS')
print('='*80)
print(f'Analysis Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Step 1: Overall statistics
print('STEP 1: Overall Database Statistics')
print('-'*80)

cur.execute('''
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(DISTINCT EXTRACT(YEAR FROM receipt_date)) as years_covered,
        MIN(EXTRACT(YEAR FROM receipt_date)) as first_year,
        MAX(EXTRACT(YEAR FROM receipt_date)) as last_year,
        SUM(gross_amount) as total_amount,
        COUNT(CASE WHEN created_from_banking THEN 1 END) as from_banking,
        COUNT(CASE WHEN mapped_bank_account_id IS NOT NULL THEN 1 END) as mapped_to_banking
    FROM receipts
''')

row = cur.fetchone()
total_receipts, years_covered, first_year, last_year, total_amount, from_banking, mapped = row

print(f'Total receipts: {total_receipts:,}')
print(f'Years covered: {int(years_covered)} years ({int(first_year)}-{int(last_year)})')
print(f'Total amount: ${total_amount:,.2f}')
print(f'From banking: {from_banking:,} ({100*from_banking/total_receipts:.1f}%)')
print(f'Mapped to banking: {mapped:,}')
print()

# Step 2: Duplicate analysis by year
print('STEP 2: Potential Duplicates by Year')
print('-'*80)

cur.execute('''
    WITH date_amount_groups AS (
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            DATE(receipt_date) as receipt_date,
            gross_amount,
            COUNT(*) as count
        FROM receipts
        GROUP BY EXTRACT(YEAR FROM receipt_date), DATE(receipt_date), gross_amount
        HAVING COUNT(*) > 1
    )
    SELECT 
        year,
        COUNT(*) as duplicate_groups,
        SUM(count) as total_duplicate_rows,
        SUM(count) - COUNT(*) as excess_duplicates,
        SUM(gross_amount * (count - 1)) as duplicate_amount
    FROM date_amount_groups
    GROUP BY year
    ORDER BY year DESC
''')

total_dup_groups = 0
total_dup_rows = 0
total_dup_amount = 0.0

for row in cur.fetchall():
    year, groups, rows, excess, amount = row
    print(f'{int(year)}: {groups} duplicate groups | {int(rows)} rows | {int(excess)} excess | ${float(amount if amount else 0):,.2f}')
    total_dup_groups += groups
    total_dup_rows += rows
    total_dup_amount += float(amount if amount else 0)

print()
print(f'TOTAL: {total_dup_groups} duplicate groups | {total_dup_rows} rows | ${total_dup_amount:,.2f}')
print()

# Step 3: NSF transaction analysis by year
print('STEP 3: NSF Transactions by Year')
print('-'*80)

cur.execute('''
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as nsf_count,
        SUM(gross_amount) as nsf_amount,
        COUNT(CASE WHEN gross_amount > 0 THEN 1 END) as positive_charges,
        COUNT(CASE WHEN gross_amount < 0 THEN 1 END) as negative_reversals
    FROM receipts
    WHERE (
        vendor_name ILIKE '%NSF%'
        OR vendor_name ILIKE '%BOUNCE%'
        OR vendor_name ILIKE '%CHARGE BACK%'
        OR description ILIKE '%NSF%'
        OR description ILIKE '%BOUNCE%'
        OR description ILIKE '%CHARGE BACK%'
    )
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year DESC
''')

total_nsf = 0
total_nsf_amt = 0.0

for row in cur.fetchall():
    year, count, amount, pos, neg = row
    print(f'{int(year)}: {count} NSF entries | ${float(amount if amount else 0):,.2f} | {pos} charges | {neg} reversals')
    total_nsf += count
    total_nsf_amt += float(amount if amount else 0)

print()
print(f'TOTAL: {total_nsf} NSF entries | ${total_nsf_amt:,.2f}')
print()

# Step 4: NSF-Payment pairs analysis (same date, same amount)
print('STEP 4: NSF-Payment Pair Analysis (Customer Payment + NSF Event)')
print('-'*80)

cur.execute('''
    WITH pairs AS (
        SELECT 
            DATE(receipt_date) as receipt_date,
            gross_amount,
            COUNT(*) as count,
            COUNT(DISTINCT CASE WHEN vendor_name LIKE '%Customer Payment%' OR description LIKE '%Customer Payment%' THEN 1 END) as has_customer_payment,
            COUNT(DISTINCT CASE WHEN vendor_name LIKE '%NSF Event%' OR description LIKE '%NSF Event%' THEN 1 END) as has_nsf_event
        FROM receipts
        WHERE (
            vendor_name LIKE '%Customer Payment%' OR vendor_name LIKE '%NSF Event%'
            OR description LIKE '%Customer Payment%' OR description LIKE '%NSF Event%'
        )
        GROUP BY DATE(receipt_date), gross_amount
        HAVING COUNT(*) >= 2
    )
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as pair_groups,
        SUM(count) as total_rows_in_pairs,
        SUM(gross_amount * (count - 1)) as duplicate_amount
    FROM pairs
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year DESC
''')

total_pair_groups = 0
total_pair_rows = 0
total_pair_amount = 0.0

for row in cur.fetchall():
    year, groups, rows, amount = row
    print(f'{int(year)}: {groups} pair groups | {int(rows)} rows | ${float(amount if amount else 0):,.2f} duplicated')
    total_pair_groups += groups
    total_pair_rows += rows
    total_pair_amount += float(amount if amount else 0)

print()
print(f'TOTAL: {total_pair_groups} pair groups | {int(total_pair_rows)} rows | ${total_pair_amount:,.2f}')
print()

# Step 5: NULL vendor analysis
print('STEP 5: Data Quality - NULL/Missing Vendors')
print('-'*80)

cur.execute('''
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as null_vendor_count,
        SUM(gross_amount) as amount
    FROM receipts
    WHERE vendor_name IS NULL OR vendor_name = ''
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year DESC
''')

for row in cur.fetchall():
    year, count, amount = row
    if count > 0:
        print(f'{int(year)}: {count} receipts with NULL vendor | ${amount:,.2f}')

print()

# Step 6: Summary and recommendations
print('='*80)
print('SUMMARY AND RECOMMENDATIONS')
print('='*80)
print()

print(f'Total Duplicates Found: {total_dup_groups:,} groups ({total_dup_rows:,} rows) = ${total_dup_amount:,.2f}')
print(f'Total NSF Transactions: {total_nsf:,} entries = ${total_nsf_amt:,.2f}')
print(f'Total NSF-Payment Pairs: {total_pair_groups:,} groups ({int(total_pair_rows):,} rows) = ${total_pair_amount:,.2f}')
print()

if total_dup_groups > 100:
    print('⚠️  HIGH: Significant number of duplicates across database')
    print('   Recommendation: Run database-wide duplicate cleanup')
else:
    print('✅ Duplicates within normal range')

if total_pair_amount > 50000:
    print('⚠️  HIGH: Significant NSF-Payment pairs found')
    print('   Recommendation: Investigate if these should be consolidated')
else:
    print('✅ NSF pairs within normal range')

print()
print('NEXT STEPS:')
print('-'*80)
print('1. Run: python scripts/find_all_duplicates_database_wide.py')
print('   (Generate list of all duplicate groups across all years)')
print()
print('2. Run: python scripts/cleanup_all_duplicates.py')
print('   (Remove all duplicates with NSF protection)')
print()
print('3. Run: python scripts/analyze_nsf_pairs_all_years.py')
print('   (Verify NSF-Payment pairing consolidated correctly)')
print()

cur.close()
conn.close()

print('='*80)
