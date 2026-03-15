"""
Analyze LMS staging tables for duplicate detection.

Three tables imported from legacy LMS Access database:
- lms_staging_customer (6,258 rows)
- lms_staging_payment (24,534 rows)  
- lms_staging_reserve (18,542 rows)

Compare against production tables to determine promotion status.
"""

import os
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("LMS STAGING TABLES ANALYSIS")
print("=" * 80)
print(f"Analysis date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================================
# 1. LMS_STAGING_CUSTOMER vs CLIENTS
# ============================================================================
print("1. LMS_STAGING_CUSTOMER ANALYSIS")
print("-" * 80)

# Get staging customer structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'lms_staging_customer'
    ORDER BY ordinal_position
""")

customer_cols = cur.fetchall()
print(f"Staging customer columns ({len(customer_cols)}):")
for col, dtype in customer_cols:
    print(f"  {col:<30} {dtype}")

# Count staging customers
cur.execute("SELECT COUNT(*) FROM lms_staging_customer")
staging_cust_count = cur.fetchone()[0]
print(f"\nStaging customers: {staging_cust_count:,}")

# Count production clients
cur.execute("SELECT COUNT(*) FROM clients")
prod_clients_count = cur.fetchone()[0]
print(f"Production clients: {prod_clients_count:,}")

# Check for duplicates by matching on name
cur.execute("""
    SELECT 
        COUNT(*) as total_staging,
        COUNT(DISTINCT lsc.account_no) as unique_accounts,
        SUM(CASE WHEN c.client_id IS NOT NULL THEN 1 ELSE 0 END) as matched_to_clients
    FROM lms_staging_customer lsc
    LEFT JOIN clients c ON LOWER(TRIM(lsc.name)) = LOWER(TRIM(c.client_name))
""")

total_staging, unique_accounts, matched = cur.fetchone()
match_pct = (matched / total_staging * 100) if total_staging > 0 else 0
print(f"\nDuplicate analysis:")
print(f"  Staging records: {total_staging:,}")
print(f"  Unique accounts: {unique_accounts:,}")
print(f"  Matched to clients: {matched:,} ({match_pct:.1f}%)")
print(f"  Unmatched: {total_staging - matched:,} ({100-match_pct:.1f}%)")

# Sample unmatched customers
if total_staging - matched > 0:
    cur.execute("""
        SELECT lsc.account_no, lsc.name, lsc.email
        FROM lms_staging_customer lsc
        LEFT JOIN clients c ON LOWER(TRIM(lsc.name)) = LOWER(TRIM(c.client_name))
        WHERE c.client_id IS NULL
        LIMIT 20
    """)
    
    print(f"\nSample unmatched customers (not in production):")
    for acct, name, email in cur.fetchall():
        print(f"  {acct:<15} {name:<40} {email or '(no email)'}")

# ============================================================================
# 2. LMS_STAGING_PAYMENT vs PAYMENTS
# ============================================================================
print("\n" + "=" * 80)
print("2. LMS_STAGING_PAYMENT ANALYSIS")
print("-" * 80)

# Get staging payment structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'lms_staging_payment'
    ORDER BY ordinal_position
""")

payment_cols = cur.fetchall()
print(f"Staging payment columns ({len(payment_cols)}):")
for col, dtype in payment_cols:
    print(f"  {col:<30} {dtype}")

# Count staging payments
cur.execute("SELECT COUNT(*), SUM(amount) FROM lms_staging_payment")
staging_pmt_count, staging_pmt_total = cur.fetchone()
print(f"\nStaging payments: {staging_pmt_count:,} | Total: ${staging_pmt_total or 0:,.2f}")

# Count production payments
cur.execute("SELECT COUNT(*), SUM(amount) FROM payments")
prod_pmt_count, prod_pmt_total = cur.fetchone()
print(f"Production payments: {prod_pmt_count:,} | Total: ${prod_pmt_total or 0:,.2f}")

# Check for duplicates by matching on reserve_number + amount
cur.execute("""
    SELECT 
        COUNT(*) as total_staging,
        SUM(CASE WHEN p.payment_id IS NOT NULL THEN 1 ELSE 0 END) as matched_to_payments
    FROM lms_staging_payment lsp
    LEFT JOIN payments p ON lsp.reserve_no = p.reserve_number 
                        AND ABS(lsp.amount - p.amount) < 0.01
""")

total_staging_pmt, matched_pmt = cur.fetchone()
match_pct_pmt = (matched_pmt / total_staging_pmt * 100) if total_staging_pmt > 0 else 0
print(f"\nDuplicate analysis:")
print(f"  Staging records: {total_staging_pmt:,}")
print(f"  Matched to payments: {matched_pmt:,} ({match_pct_pmt:.1f}%)")
print(f"  Unmatched: {total_staging_pmt - matched_pmt:,} ({100-match_pct_pmt:.1f}%)")

# Date range comparison
cur.execute("""
    SELECT MIN(payment_date)::date, MAX(payment_date)::date
    FROM lms_staging_payment
    WHERE payment_date IS NOT NULL
""")

staging_pmt_earliest, staging_pmt_latest = cur.fetchone()
print(f"  Staging date range: {staging_pmt_earliest} to {staging_pmt_latest}")

cur.execute("""
    SELECT MIN(payment_date)::date, MAX(payment_date)::date
    FROM payments
    WHERE payment_date IS NOT NULL
""")

prod_pmt_earliest, prod_pmt_latest = cur.fetchone()
print(f"  Production date range: {prod_pmt_earliest} to {prod_pmt_latest}")

# Sample unmatched payments
if total_staging_pmt - matched_pmt > 0:
    cur.execute("""
        SELECT lsp.reserve_no, lsp.account_no, lsp.amount, lsp.payment_date
        FROM lms_staging_payment lsp
        LEFT JOIN payments p ON lsp.reserve_no = p.reserve_number 
                            AND ABS(lsp.amount - p.amount) < 0.01
        WHERE p.payment_id IS NULL
        ORDER BY lsp.amount DESC
        LIMIT 20
    """)
    
    print(f"\nSample unmatched payments (not in production):")
    for reserve, acct, amt, pmt_date in cur.fetchall():
        print(f"  Reserve {reserve:<10} Acct {acct:<15} ${amt:>10,.2f}  {pmt_date}")

# ============================================================================
# 3. LMS_STAGING_RESERVE vs CHARTERS
# ============================================================================
print("\n" + "=" * 80)
print("3. LMS_STAGING_RESERVE ANALYSIS")
print("-" * 80)

# Get staging reserve structure
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'lms_staging_reserve'
    ORDER BY ordinal_position
""")

reserve_cols = cur.fetchall()
print(f"Staging reserve columns ({len(reserve_cols)}):")
for col, dtype in reserve_cols:
    print(f"  {col:<30} {dtype}")

# Count staging reserves
cur.execute("SELECT COUNT(*) FROM lms_staging_reserve")
staging_res_count = cur.fetchone()[0]
print(f"\nStaging reserves: {staging_res_count:,}")

# Count production charters
cur.execute("SELECT COUNT(*) FROM charters")
prod_charters_count = cur.fetchone()[0]
print(f"Production charters: {prod_charters_count:,}")

# Check for duplicates by matching on reserve_no
cur.execute("""
    SELECT 
        COUNT(*) as total_staging,
        SUM(CASE WHEN c.charter_id IS NOT NULL THEN 1 ELSE 0 END) as matched_to_charters
    FROM lms_staging_reserve lsr
    LEFT JOIN charters c ON lsr.reserve_no = c.reserve_number
""")

total_staging_res, matched_res = cur.fetchone()
match_pct_res = (matched_res / total_staging_res * 100) if total_staging_res > 0 else 0
print(f"\nDuplicate analysis:")
print(f"  Staging records: {total_staging_res:,}")
print(f"  Matched to charters: {matched_res:,} ({match_pct_res:.1f}%)")
print(f"  Unmatched: {total_staging_res - matched_res:,} ({100-match_pct_res:.1f}%)")

# Date range comparison
cur.execute("""
    SELECT MIN(pu_date)::date, MAX(pu_date)::date
    FROM lms_staging_reserve
    WHERE pu_date IS NOT NULL
""")

staging_res_earliest, staging_res_latest = cur.fetchone()
print(f"  Staging date range: {staging_res_earliest} to {staging_res_latest}")

cur.execute("""
    SELECT MIN(charter_date)::date, MAX(charter_date)::date
    FROM charters
    WHERE charter_date IS NOT NULL
""")

prod_res_earliest, prod_res_latest = cur.fetchone()
print(f"  Production date range: {prod_res_earliest} to {prod_res_latest}")

# Sample unmatched reserves
if total_staging_res - matched_res > 0:
    cur.execute("""
        SELECT lsr.reserve_no, lsr.account_no, lsr.pu_date
        FROM lms_staging_reserve lsr
        LEFT JOIN charters c ON lsr.reserve_no = c.reserve_number
        WHERE c.charter_id IS NULL
        ORDER BY lsr.reserve_no DESC
        LIMIT 20
    """)
    
    print(f"\nSample unmatched reserves (not in production):")
    for reserve, acct, pu_date in cur.fetchall():
        print(f"  Reserve {reserve:<10} Acct {acct:<15} PU Date: {pu_date}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("ANALYSIS SUMMARY")
print("=" * 80)

total_staging_records = staging_cust_count + staging_pmt_count + staging_res_count
total_matched = matched + matched_pmt + matched_res
total_unmatched = total_staging_records - total_matched

print(f"\nOVERALL STATISTICS:")
print(f"  Total staging records: {total_staging_records:,}")
print(f"  Total matched: {total_matched:,} ({total_matched/total_staging_records*100:.1f}%)")
print(f"  Total unmatched: {total_unmatched:,} ({total_unmatched/total_staging_records*100:.1f}%)")

print(f"\nBY TABLE:")
print(f"  Customers: {matched:,}/{staging_cust_count:,} matched ({match_pct:.1f}%)")
print(f"  Payments: {matched_pmt:,}/{staging_pmt_count:,} matched ({match_pct_pmt:.1f}%)")
print(f"  Reserves: {matched_res:,}/{staging_res_count:,} matched ({match_pct_res:.1f}%)")

print(f"\nRECOMMENDATION:")
if total_unmatched < total_staging_records * 0.05:  # Less than 5% unmatched
    print("  ✓ ARCHIVE - Over 95% already in production")
    print("  ✓ Review unmatched records for manual promotion")
elif total_unmatched > total_staging_records * 0.50:  # More than 50% unmatched
    print("  ⚠ PROMOTE - Significant new data available")
    print("  ⚠ Review matching logic - may need fuzzy matching")
else:
    print("  ⚡ SELECTIVE PROMOTION - Review unmatched records")
    print("  ⚡ May represent recent additions not yet synced")

cur.close()
conn.close()
