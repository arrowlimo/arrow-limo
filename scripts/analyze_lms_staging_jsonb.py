"""
Analyze LMS staging tables with JSONB raw_data fields.

These tables store raw data from LMS Access database as JSON.
Need to extract and compare against production tables.
"""

import os
import psycopg2
import json
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 80)
print("LMS STAGING TABLES ANALYSIS (JSONB Format)")
print("=" * 80)
print(f"Analysis date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================================
# 1. LMS_STAGING_CUSTOMER
# ============================================================================
print("1. LMS_STAGING_CUSTOMER ANALYSIS")
print("-" * 80)

cur.execute("SELECT COUNT(*) FROM lms_staging_customer")
staging_cust_count = cur.fetchone()[0]
print(f"Staging customers: {staging_cust_count:,}")

cur.execute("SELECT COUNT(*) FROM clients")
prod_clients_count = cur.fetchone()[0]
print(f"Production clients: {prod_clients_count:,}")

# Sample JSON structure
cur.execute("""
    SELECT raw_data 
    FROM lms_staging_customer 
    WHERE raw_data IS NOT NULL
    LIMIT 1
""")

sample = cur.fetchone()
if sample:
    print(f"\nSample JSON structure:")
    sample_data = sample[0]
    if isinstance(sample_data, dict):
        for key in sorted(sample_data.keys()):
            print(f"  {key}: {sample_data[key]}")

# Check for matches by customer_id
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN c.client_id IS NOT NULL THEN 1 ELSE 0 END) as matched
    FROM lms_staging_customer lsc
    LEFT JOIN clients c ON lsc.customer_id = c.client_id
""")

total_cust, matched_cust = cur.fetchone()
match_pct_cust = (matched_cust / total_cust * 100) if total_cust > 0 else 0
print(f"\nDuplicate check (by customer_id):")
print(f"  Total staging: {total_cust:,}")
print(f"  Matched: {matched_cust:,} ({match_pct_cust:.1f}%)")
print(f"  Unmatched: {total_cust - matched_cust:,} ({100-match_pct_cust:.1f}%)")

# Date range
cur.execute("""
    SELECT 
        MIN(last_updated)::date as earliest,
        MAX(last_updated)::date as latest
    FROM lms_staging_customer
    WHERE last_updated IS NOT NULL
""")

earliest_cust, latest_cust = cur.fetchone()
print(f"  Last updated range: {earliest_cust} to {latest_cust}")

# ============================================================================
# 2. LMS_STAGING_PAYMENT
# ============================================================================
print("\n" + "=" * 80)
print("2. LMS_STAGING_PAYMENT ANALYSIS")
print("-" * 80)

cur.execute("SELECT COUNT(*) FROM lms_staging_payment")
staging_pmt_count = cur.fetchone()[0]
print(f"Staging payments: {staging_pmt_count:,}")

cur.execute("SELECT COUNT(*) FROM payments")
prod_pmt_count = cur.fetchone()[0]
print(f"Production payments: {prod_pmt_count:,}")

# Sample JSON structure
cur.execute("""
    SELECT raw_data 
    FROM lms_staging_payment 
    WHERE raw_data IS NOT NULL
    LIMIT 1
""")

sample_pmt = cur.fetchone()
if sample_pmt:
    print(f"\nSample JSON structure:")
    sample_data = sample_pmt[0]
    if isinstance(sample_data, dict):
        for key in sorted(sample_data.keys()):
            print(f"  {key}: {sample_data[key]}")

# Check for matches by reserve_no
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN p.payment_id IS NOT NULL THEN 1 ELSE 0 END) as matched
    FROM lms_staging_payment lsp
    LEFT JOIN payments p ON lsp.reserve_no = p.reserve_number
""")

total_pmt, matched_pmt = cur.fetchone()
match_pct_pmt = (matched_pmt / total_pmt * 100) if total_pmt > 0 else 0
print(f"\nDuplicate check (by reserve_no):")
print(f"  Total staging: {total_pmt:,}")
print(f"  Matched: {matched_pmt:,} ({match_pct_pmt:.1f}%)")
print(f"  Unmatched: {total_pmt - matched_pmt:,} ({100-match_pct_pmt:.1f}%)")

# Date range
cur.execute("""
    SELECT 
        MIN(last_updated)::date as earliest,
        MAX(last_updated)::date as latest
    FROM lms_staging_payment
    WHERE last_updated IS NOT NULL
""")

earliest_pmt, latest_pmt = cur.fetchone()
print(f"  Last updated range: {earliest_pmt} to {latest_pmt}")

# ============================================================================
# 3. LMS_STAGING_RESERVE
# ============================================================================
print("\n" + "=" * 80)
print("3. LMS_STAGING_RESERVE ANALYSIS")
print("-" * 80)

cur.execute("SELECT COUNT(*) FROM lms_staging_reserve")
staging_res_count = cur.fetchone()[0]
print(f"Staging reserves: {staging_res_count:,}")

cur.execute("SELECT COUNT(*) FROM charters")
prod_charters_count = cur.fetchone()[0]
print(f"Production charters: {prod_charters_count:,}")

# Sample JSON structure
cur.execute("""
    SELECT raw_data 
    FROM lms_staging_reserve 
    WHERE raw_data IS NOT NULL
    LIMIT 1
""")

sample_res = cur.fetchone()
if sample_res:
    print(f"\nSample JSON structure:")
    sample_data = sample_res[0]
    if isinstance(sample_data, dict):
        for key in sorted(sample_data.keys()):
            value = sample_data[key]
            # Truncate long values
            if isinstance(value, str) and len(str(value)) > 60:
                value = str(value)[:60] + "..."
            print(f"  {key}: {value}")

# Check for matches by reserve_no
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN c.charter_id IS NOT NULL THEN 1 ELSE 0 END) as matched
    FROM lms_staging_reserve lsr
    LEFT JOIN charters c ON lsr.reserve_no = c.reserve_number
""")

total_res, matched_res = cur.fetchone()
match_pct_res = (matched_res / total_res * 100) if total_res > 0 else 0
print(f"\nDuplicate check (by reserve_no):")
print(f"  Total staging: {total_res:,}")
print(f"  Matched: {matched_res:,} ({match_pct_res:.1f}%)")
print(f"  Unmatched: {total_res - matched_res:,} ({100-match_pct_res:.1f}%)")

# Date range
cur.execute("""
    SELECT 
        MIN(last_updated)::date as earliest,
        MAX(last_updated)::date as latest
    FROM lms_staging_reserve
    WHERE last_updated IS NOT NULL
""")

earliest_res, latest_res = cur.fetchone()
print(f"  Last updated range: {earliest_res} to {latest_res}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("ANALYSIS SUMMARY")
print("=" * 80)

total_staging = staging_cust_count + staging_pmt_count + staging_res_count
total_matched = matched_cust + matched_pmt + matched_res
total_unmatched = total_staging - total_matched

print(f"\nOVERALL STATISTICS:")
print(f"  Total staging records: {total_staging:,}")
print(f"  Total matched: {total_matched:,} ({total_matched/total_staging*100:.1f}%)")
print(f"  Total unmatched: {total_unmatched:,} ({total_unmatched/total_staging*100:.1f}%)")

print(f"\nBY TABLE:")
print(f"  Customers: {matched_cust:,}/{staging_cust_count:,} ({match_pct_cust:.1f}%) | Prod: {prod_clients_count:,}")
print(f"  Payments: {matched_pmt:,}/{staging_pmt_count:,} ({match_pct_pmt:.1f}%) | Prod: {prod_pmt_count:,}")
print(f"  Reserves: {matched_res:,}/{staging_res_count:,} ({match_pct_res:.1f}%) | Prod: {prod_charters_count:,}")

print(f"\nPRODUCTION vs STAGING:")
cust_diff = prod_clients_count - staging_cust_count
pmt_diff = prod_pmt_count - staging_pmt_count
res_diff = prod_charters_count - staging_res_count

print(f"  Customers: {prod_clients_count:,} prod - {staging_cust_count:,} staging = {cust_diff:+,}")
print(f"  Payments: {prod_pmt_count:,} prod - {staging_pmt_count:,} staging = {pmt_diff:+,}")
print(f"  Reserves: {prod_charters_count:,} prod - {staging_res_count:,} staging = {res_diff:+,}")

print(f"\nRECOMMENDATION:")
if total_unmatched < total_staging * 0.02:  # Less than 2% unmatched
    print("  ✓ ARCHIVE - Over 98% already in production")
    print("  ✓ Staging tables are redundant backups")
elif prod_clients_count < staging_cust_count or prod_pmt_count < staging_pmt_count or prod_charters_count < staging_res_count:
    print("  ⚠ INVESTIGATE - Staging has MORE data than production!")
    print("  ⚠ Possible data loss during migration")
else:
    print("  ✓ ARCHIVE - Production is superset of staging")
    print("  ✓ Keep for 30 days then drop")

cur.close()
conn.close()
