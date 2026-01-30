#!/usr/bin/env python3
"""Quick beverage matching status check."""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('=' * 80)
print('BEVERAGE MATCHING STATUS CHECK')
print('=' * 80)

# Charter charges with beverage keywords
cur.execute("""
    SELECT COUNT(*) as charge_count,
           COUNT(DISTINCT charter_id) as charter_count,
           SUM(amount) as total_revenue
    FROM charter_charges 
    WHERE LOWER(description) LIKE '%beverage%' 
       OR LOWER(description) LIKE '%alcohol%'
       OR LOWER(description) LIKE '%wine%'
       OR LOWER(description) LIKE '%beer%'
       OR LOWER(charge_type) LIKE '%beverage%'
""")
charges = cur.fetchone()
print(f'\n📊 BEVERAGE CHARGES IN CHARTER_CHARGES TABLE:')
print(f'   Total beverage charges: {charges[0]:,}')
print(f'   Charters with beverages: {charges[1]:,}')
print(f'   Total beverage revenue: ${charges[2] or 0:,.2f}')

# Receipts with liquor/alcohol purchases
cur.execute("""
    SELECT COUNT(*) as receipt_count,
           SUM(gross_amount) as total_cost,
           COUNT(DISTINCT vendor_name) as vendor_count
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%liquor%'
       OR LOWER(vendor_name) LIKE '%wine%'
       OR LOWER(vendor_name) LIKE '%beer%'
       OR LOWER(vendor_name) LIKE '%alcohol%'
       OR LOWER(description) LIKE '%alcohol%'
       OR LOWER(description) LIKE '%beverage%'
       OR LOWER(category) LIKE '%alcohol%'
""")
receipts = cur.fetchone()
print(f'\n🛒 ALCOHOL PURCHASES IN RECEIPTS TABLE:')
print(f'   Total alcohol receipts: {receipts[0]:,}')
print(f'   Total purchase cost: ${receipts[1] or 0:,.2f}')
print(f'   Unique vendors: {receipts[2]:,}')

# Year-by-year breakdown
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM c.charter_date) as year,
        COUNT(cc.charge_id) as charges,
        SUM(cc.amount) as revenue
    FROM charter_charges cc
    INNER JOIN charters c ON cc.charter_id = c.charter_id
    WHERE LOWER(cc.description) LIKE '%beverage%' 
       OR LOWER(cc.description) LIKE '%alcohol%'
       OR LOWER(cc.description) LIKE '%wine%'
       OR LOWER(cc.description) LIKE '%beer%'
    GROUP BY year
    ORDER BY year
""")
years = cur.fetchall()
print(f'\n📅 BEVERAGE CHARGES BY YEAR:')
for year, count, revenue in years:
    print(f'   {int(year)}: {count:,} charges, ${revenue:,.2f} revenue')

# Sample recent beverage charges
cur.execute("""
    SELECT c.reserve_number, c.charter_date, cc.description, cc.amount
    FROM charter_charges cc
    INNER JOIN charters c ON cc.charter_id = c.charter_id
    WHERE LOWER(cc.description) LIKE '%beverage%' 
       OR LOWER(cc.description) LIKE '%alcohol%'
    ORDER BY c.charter_date DESC
    LIMIT 10
""")
samples = cur.fetchall()
print(f'\n🍾 SAMPLE RECENT BEVERAGE CHARGES:')
for reserve, date, desc, amount in samples:
    print(f'   {reserve} | {date} | {desc[:40]:<40} | ${amount:,.2f}')

print('\n' + '=' * 80)
print('MATCHING STATUS SUMMARY')
print('=' * 80)
print(f'[OK] Beverage charges ARE linked to charters via charter_charges table')
print(f'[OK] Alcohol purchases ARE tracked in receipts table')
print(f'[WARN]  Matching purchases→charters requires date/amount correlation')
print(f'📊 {charges[0]:,} beverage charges across {charges[1]:,} charters')
print(f'🛒 {receipts[0]:,} alcohol purchase receipts from {receipts[2]:,} vendors')
print('=' * 80)

conn.close()
