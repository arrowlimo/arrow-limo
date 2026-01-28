#!/usr/bin/env python3
"""
Compare staging tables to main tables to identify duplicates and new records.

This script analyzes all staging tables and compares them to their corresponding
main tables to determine:
1. How many records are already in the main table (duplicates)
2. How many records are new and ready to promote
3. Data quality issues that need fixing before promotion

Usage:
    python scripts/compare_staging_to_main.py
"""

import os
import sys
import psycopg2
from datetime import datetime

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_qb_accounts_staging(cur):
    """Compare qb_accounts_staging to existing account tables."""
    print("\n" + "="*80)
    print("1. QB ACCOUNTS STAGING → Chart of Accounts")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM qb_accounts_staging")
    staging_count = cur.fetchone()[0]
    print(f"📊 Staging records: {staging_count:,}")
    
    # Check if there's an accounts table
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'accounts'
        )
    """)
    accounts_exists = cur.fetchone()[0]
    
    if accounts_exists:
        cur.execute("SELECT COUNT(*) FROM accounts")
        main_count = cur.fetchone()[0]
        print(f"📊 Main accounts table: {main_count:,} records")
        
        # Check for matching account numbers/names
        cur.execute("""
            SELECT COUNT(DISTINCT qa.account_number)
            FROM qb_accounts_staging qa
            INNER JOIN accounts a ON qa.account_number = a.account_number
        """)
        duplicates = cur.fetchone()[0]
        print(f"🔄 Duplicates (matching account_number): {duplicates:,}")
        print(f"[OK] New records ready to promote: {staging_count - duplicates:,}")
    else:
        print("[WARN]  No 'accounts' table found - all records are new")
        print(f"[OK] Ready to create accounts table with {staging_count:,} records")
    
    # Show sample accounts
    cur.execute("""
        SELECT qb_account_number, qb_name, qb_account_type, qb_current_balance
        FROM qb_accounts_staging
        ORDER BY qb_account_number
        LIMIT 5
    """)
    print("\n📋 Sample accounts in staging:")
    for row in cur.fetchall():
        balance = row[3] if row[3] is not None else 0
        print(f"   {row[0]}: {row[1]} ({row[2]}) - Balance: ${balance:,.2f}")

def analyze_lms_customers_staging(cur):
    """Compare lms_staging_customer to clients table."""
    print("\n" + "="*80)
    print("2. LMS STAGING CUSTOMER → clients table")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM lms_staging_customer")
    staging_count = cur.fetchone()[0]
    print(f"📊 Staging records: {staging_count:,}")
    
    cur.execute("SELECT COUNT(*) FROM clients")
    main_count = cur.fetchone()[0]
    print(f"📊 Main clients table: {main_count:,} records")
    
    # Check for duplicates by client_id
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_customer lsc
        INNER JOIN clients c ON (lsc.raw_data->>'Client_ID')::INTEGER = c.client_id
    """)
    duplicates_by_id = cur.fetchone()[0]
    print(f"🔄 Duplicates (matching client_id): {duplicates_by_id:,}")
    
    # Check for duplicates by name (fuzzy)
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_customer lsc
        INNER JOIN clients c ON LOWER(TRIM(lsc.raw_data->>'Name')) = LOWER(TRIM(c.client_name))
        WHERE NOT EXISTS (
            SELECT 1 FROM clients c2 
            WHERE (lsc.raw_data->>'Client_ID')::INTEGER = c2.client_id
        )
    """)
    duplicates_by_name = cur.fetchone()[0]
    print(f"🔄 Additional duplicates (matching name but different ID): {duplicates_by_name:,}")
    
    total_duplicates = duplicates_by_id + duplicates_by_name
    new_records = staging_count - total_duplicates
    print(f"[OK] New unique customers ready to promote: {new_records:,}")
    
    # Check for data quality issues
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN raw_data->>'Name' IS NULL OR raw_data->>'Name' = '' THEN 1 END) as missing_name,
            COUNT(CASE WHEN raw_data->>'Phone' IS NOT NULL AND raw_data->>'Phone' != '' THEN 1 END) as has_phone,
            COUNT(CASE WHEN raw_data->>'Email' IS NOT NULL AND raw_data->>'Email' != '' THEN 1 END) as has_email
        FROM lms_staging_customer
    """)
    qc = cur.fetchone()
    print(f"\n🔍 Data Quality:")
    print(f"   Missing names: {qc[1]:,} ({qc[1]/qc[0]*100:.1f}%)")
    print(f"   With phone: {qc[2]:,} ({qc[2]/qc[0]*100:.1f}%)")
    print(f"   With email: {qc[3]:,} ({qc[3]/qc[0]*100:.1f}%)")
    
    # Show sample new customers
    cur.execute("""
        SELECT 
            lsc.raw_data->>'Client_ID' as client_id,
            lsc.raw_data->>'Name' as name,
            lsc.raw_data->>'Phone' as phone,
            lsc.raw_data->>'Email' as email
        FROM lms_staging_customer lsc
        WHERE NOT EXISTS (
            SELECT 1 FROM clients c 
            WHERE (lsc.raw_data->>'Client_ID')::INTEGER = c.client_id
        )
        ORDER BY (lsc.raw_data->>'Client_ID')::INTEGER
        LIMIT 5
    """)
    print("\n📋 Sample NEW customers (not in main table):")
    for row in cur.fetchall():
        print(f"   ID {row[0]}: {row[1]} | {row[2]} | {row[3]}")

def analyze_lms_vehicles_staging(cur):
    """Compare lms_staging_vehicles to vehicles table."""
    print("\n" + "="*80)
    print("3. LMS STAGING VEHICLES → vehicles table")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM lms_staging_vehicles")
    staging_count = cur.fetchone()[0]
    print(f"📊 Staging records: {staging_count:,}")
    
    cur.execute("SELECT COUNT(*) FROM vehicles")
    main_count = cur.fetchone()[0]
    print(f"📊 Main vehicles table: {main_count:,} records")
    
    # Check for duplicates by VIN
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_vehicles lsv
        INNER JOIN vehicles v ON 
            LOWER(TRIM(lsv.vin)) = LOWER(TRIM(v.vin_number))
        WHERE lsv.vin IS NOT NULL 
        AND lsv.vin != ''
    """)
    duplicates_by_vin = cur.fetchone()[0]
    print(f"🔄 Duplicates (matching VIN): {duplicates_by_vin:,}")
    
    total_duplicates = duplicates_by_vin
    new_records = staging_count - total_duplicates
    print(f"[OK] New vehicles ready to promote: {new_records:,}")
    
    # Check for data quality
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN vin IS NULL OR vin = '' THEN 1 END) as missing_vin,
            COUNT(CASE WHEN vehicle_code IS NULL OR vehicle_code = '' THEN 1 END) as missing_code,
            COUNT(CASE WHEN raw_data->>'Type' IS NULL OR raw_data->>'Type' = '' THEN 1 END) as missing_type
        FROM lms_staging_vehicles
    """)
    qc = cur.fetchone()
    print(f"\n🔍 Data Quality:")
    print(f"   Missing VIN: {qc[1]:,} ({qc[1]/qc[0]*100:.1f}%)")
    print(f"   Missing vehicle_code: {qc[2]:,} ({qc[2]/qc[0]*100:.1f}%)")
    print(f"   Missing type: {qc[3]:,} ({qc[3]/qc[0]*100:.1f}%)")
    
    # Show sample vehicles
    cur.execute("""
        SELECT 
            lsv.vehicle_code as unit,
            lsv.vin as vin,
            lsv.raw_data->>'Type' as type,
            lsv.raw_data->>'Make' as make,
            lsv.raw_data->>'Model' as model
        FROM lms_staging_vehicles lsv
        WHERE NOT EXISTS (
            SELECT 1 FROM vehicles v 
            WHERE LOWER(TRIM(lsv.vin)) = LOWER(TRIM(v.vin_number))
        )
        LIMIT 5
    """)
    print("\n📋 Sample NEW vehicles (not in main table):")
    for row in cur.fetchall():
        print(f"   Unit {row[0]}: {row[3]} {row[4]} | VIN: {row[1]} | Type: {row[2]}")

def analyze_lms_payments_staging(cur):
    """Compare lms_staging_payment to payments table."""
    print("\n" + "="*80)
    print("4. LMS STAGING PAYMENT → payments table")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM lms_staging_payment")
    staging_count = cur.fetchone()[0]
    print(f"📊 Staging records: {staging_count:,}")
    
    cur.execute("SELECT COUNT(*) FROM payments")
    main_count = cur.fetchone()[0]
    print(f"📊 Main payments table: {main_count:,} records")
    
    # Check for duplicates by payment_id
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_payment lsp
        INNER JOIN payments p ON lsp.payment_id = p.payment_id
    """)
    duplicates_by_id = cur.fetchone()[0]
    print(f"🔄 Duplicates (matching payment_id): {duplicates_by_id:,}")
    
    # Check for duplicates by (account, reserve, amount, date)
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_payment lsp
        INNER JOIN payments p ON 
            lsp.raw_data->>'Account_No' = p.account_number
            AND lsp.reserve_no = p.reserve_number
            AND (lsp.raw_data->>'Amount')::NUMERIC = p.amount
            AND lsp.last_updated::DATE = p.payment_date
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p2 
            WHERE lsp.payment_id = p2.payment_id
        )
    """)
    duplicates_by_data = cur.fetchone()[0]
    print(f"🔄 Additional duplicates (matching data but different ID): {duplicates_by_data:,}")
    
    total_duplicates = duplicates_by_id + duplicates_by_data
    new_records = staging_count - total_duplicates
    print(f"[OK] New payments ready to promote: {new_records:,}")
    
    # Calculate financial impact
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM((raw_data->>'Amount')::NUMERIC) as total_amount
        FROM lms_staging_payment lsp
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE lsp.payment_id = p.payment_id
        )
    """)
    new_stats = cur.fetchone()
    if new_stats[0] > 0:
        print(f"\n💰 New Payments Financial Impact:")
        print(f"   Count: {new_stats[0]:,} payments")
        print(f"   Total Amount: ${new_stats[1]:,.2f}")
    
    # Check data quality
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN raw_data->>'Amount' IS NULL OR (raw_data->>'Amount')::NUMERIC <= 0 THEN 1 END) as invalid_amount,
            COUNT(CASE WHEN raw_data->>'Reserve_No' IS NULL OR raw_data->>'Reserve_No' = '' THEN 1 END) as missing_reserve,
            COUNT(CASE WHEN raw_data->>'LastUpdated' IS NULL THEN 1 END) as missing_date
        FROM lms_staging_payment
    """)
    qc = cur.fetchone()
    print(f"\n🔍 Data Quality:")
    print(f"   Invalid amounts: {qc[1]:,} ({qc[1]/qc[0]*100:.1f}%)")
    print(f"   Missing reserve #: {qc[2]:,} ({qc[2]/qc[0]*100:.1f}%)")
    print(f"   Missing date: {qc[3]:,} ({qc[3]/qc[0]*100:.1f}%)")

def analyze_lms_reserves_staging(cur):
    """Compare lms_staging_reserve to charters table."""
    print("\n" + "="*80)
    print("5. LMS STAGING RESERVE → charters table")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM lms_staging_reserve")
    staging_count = cur.fetchone()[0]
    print(f"📊 Staging records: {staging_count:,}")
    
    cur.execute("SELECT COUNT(*) FROM charters")
    main_count = cur.fetchone()[0]
    print(f"📊 Main charters table: {main_count:,} records")
    
    # Check for duplicates by reserve_number
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_reserve lsr
        INNER JOIN charters c ON lsr.reserve_no = c.reserve_number
    """)
    duplicates_by_reserve = cur.fetchone()[0]
    print(f"🔄 Duplicates (matching reserve_number): {duplicates_by_reserve:,}")
    
    new_records = staging_count - duplicates_by_reserve
    print(f"[OK] New charters ready to promote: {new_records:,}")
    
    # Calculate financial impact
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM((raw_data->>'Rate')::NUMERIC) as total_rate,
            SUM((raw_data->>'Balance')::NUMERIC) as total_balance
        FROM lms_staging_reserve lsr
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c 
            WHERE lsr.reserve_no = c.reserve_number
        )
    """)
    new_stats = cur.fetchone()
    if new_stats[0] > 0:
        print(f"\n💰 New Charters Financial Impact:")
        print(f"   Count: {new_stats[0]:,} charters")
        print(f"   Total Rate: ${new_stats[1]:,.2f}")
        print(f"   Total Balance: ${new_stats[2]:,.2f}")
    
    # Check data quality
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN raw_data->>'Reserve_No' IS NULL OR raw_data->>'Reserve_No' = '' THEN 1 END) as missing_reserve,
            COUNT(CASE WHEN raw_data->>'PU_Date' IS NULL THEN 1 END) as missing_date,
            COUNT(CASE WHEN raw_data->>'Account_No' IS NULL OR raw_data->>'Account_No' = '' THEN 1 END) as missing_account,
            COUNT(CASE WHEN raw_data->>'Rate' IS NULL OR (raw_data->>'Rate')::NUMERIC <= 0 THEN 1 END) as invalid_rate
        FROM lms_staging_reserve
    """)
    qc = cur.fetchone()
    print(f"\n🔍 Data Quality:")
    print(f"   Missing reserve #: {qc[1]:,} ({qc[1]/qc[0]*100:.1f}%)")
    print(f"   Missing date: {qc[2]:,} ({qc[2]/qc[0]*100:.1f}%)")
    print(f"   Missing account: {qc[3]:,} ({qc[3]/qc[0]*100:.1f}%)")
    print(f"   Invalid rate: {qc[4]:,} ({qc[4]/qc[0]*100:.1f}%)")

def analyze_staging_employee_reference(cur):
    """Compare staging_employee_reference_data to employees table."""
    print("\n" + "="*80)
    print("6. STAGING EMPLOYEE REFERENCE → employees table")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM staging_employee_reference_data")
    staging_count = cur.fetchone()[0]
    print(f"📊 Staging records: {staging_count:,}")
    
    cur.execute("SELECT COUNT(*) FROM employees")
    main_count = cur.fetchone()[0]
    print(f"📊 Main employees table: {main_count:,} records")
    
    # Check for duplicates by SIN
    cur.execute("""
        SELECT COUNT(*)
        FROM staging_employee_reference_data serd
        INNER JOIN employees e ON serd.sin = e.t4_sin
        WHERE serd.sin IS NOT NULL AND serd.sin != ''
    """)
    duplicates_by_sin = cur.fetchone()[0]
    print(f"🔄 Duplicates (matching SIN): {duplicates_by_sin:,}")
    
    # Check for duplicates by name
    cur.execute("""
        SELECT COUNT(*)
        FROM staging_employee_reference_data serd
        INNER JOIN employees e ON 
            LOWER(TRIM(serd.employee_name)) = LOWER(TRIM(e.full_name))
        WHERE NOT EXISTS (
            SELECT 1 FROM employees e2 
            WHERE serd.sin = e2.t4_sin
        )
    """)
    duplicates_by_name = cur.fetchone()[0]
    print(f"🔄 Additional duplicates (matching name): {duplicates_by_name:,}")
    
    total_duplicates = duplicates_by_sin + duplicates_by_name
    new_records = staging_count - total_duplicates
    print(f"[OK] New employees ready to promote: {new_records:,}")
    
    # Show sample data
    cur.execute("""
        SELECT 
            serd.employee_name,
            serd.sin,
            COALESCE(serd.street1, '') || ' ' || COALESCE(serd.city, '') as address,
            serd.hire_date
        FROM staging_employee_reference_data serd
        WHERE NOT EXISTS (
            SELECT 1 FROM employees e 
            WHERE serd.sin = e.t4_sin
        )
        ORDER BY serd.hire_date
        LIMIT 5
    """)
    print("\n📋 Sample NEW employees (not in main table):")
    for row in cur.fetchall():
        print(f"   {row[0]} | SIN: {row[1]} | Hired: {row[3]} | {row[2]}")

def main():
    """Main execution function."""
    print("="*80)
    print("STAGING vs MAIN TABLES - DUPLICATE ANALYSIS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print("\nComparing staging tables to main tables to identify:")
    print("  1. Duplicate records already in main tables")
    print("  2. New records ready for promotion")
    print("  3. Data quality issues requiring attention")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Analyze each staging table
        analyze_qb_accounts_staging(cur)
        analyze_lms_customers_staging(cur)
        analyze_lms_vehicles_staging(cur)
        analyze_lms_payments_staging(cur)
        analyze_lms_reserves_staging(cur)
        analyze_staging_employee_reference(cur)
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY & RECOMMENDATIONS")
        print("="*80)
        print("\n[OK] SAFE TO PROMOTE (Low Duplicate Risk):")
        print("   1. QB Accounts (reference data)")
        print("   2. Employee Reference Data (small dataset)")
        print("\n[WARN]  MEDIUM RISK (Need Deduplication Logic):")
        print("   3. LMS Customers (check client_id + name matching)")
        print("   4. LMS Vehicles (check VIN + unit matching)")
        print("\n🚨 HIGH RISK (Complex Deduplication Required):")
        print("   5. LMS Payments (check payment_id + data hash)")
        print("   6. LMS Reserves (check reserve_number + date range)")
        print("\n📋 NEXT STEPS:")
        print("   1. Create promotion scripts with duplicate detection")
        print("   2. Run in --dry-run mode first")
        print("   3. Backup database before promotion")
        print("   4. Promote in order: accounts → customers → vehicles → payments → reserves")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
