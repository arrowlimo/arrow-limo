#!/usr/bin/env python3
"""
Create missing customer records from charter reserves.

Extracts customers from lms_staging_reserve that don't exist in clients table
and creates client records for them.

Usage:
    python scripts/create_missing_customers_from_reserves.py --dry-run
    python scripts/create_missing_customers_from_reserves.py --write
"""

import os
import sys
import psycopg2
from datetime import datetime
import argparse

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def find_missing_customers(cur):
    """Find customers in reserves that don't exist in clients table."""
    print("\n" + "="*80)
    print("ANALYZING MISSING CUSTOMERS")
    print("="*80)
    
    # Find unique account numbers with customer names and charter counts
    cur.execute("""
        SELECT DISTINCT
            lsr.raw_data->>'Account_No' as account_number,
            lsr.raw_data->>'Name' as client_name,
            COUNT(*) OVER (PARTITION BY lsr.raw_data->>'Account_No') as charter_count,
            MIN((lsr.raw_data->>'PU_Date')::DATE) OVER (PARTITION BY lsr.raw_data->>'Account_No') as first_charter,
            MAX((lsr.raw_data->>'PU_Date')::DATE) OVER (PARTITION BY lsr.raw_data->>'Account_No') as last_charter,
            SUM((lsr.raw_data->>'Rate')::NUMERIC) OVER (PARTITION BY lsr.raw_data->>'Account_No') as total_revenue
        FROM lms_staging_reserve lsr
        WHERE lsr.raw_data->>'Account_No' IS NOT NULL 
        AND lsr.raw_data->>'Account_No' != ''
        AND NOT EXISTS (
            SELECT 1 FROM clients c
            WHERE c.account_number = lsr.raw_data->>'Account_No'
        )
        ORDER BY charter_count DESC, account_number
    """)
    
    missing = cur.fetchall()
    
    if not missing:
        print("\n[OK] No missing customers found - all accounts in reserves exist in clients table")
        return []
    
    print(f"\n📊 Found {len(missing)} missing customers:")
    print(f"\n{'Account':<10} {'Customer Name':<35} {'Charters':<10} {'First':<12} {'Last':<12} {'Revenue':<12}")
    print("-"*95)
    
    total_charters = 0
    total_revenue = 0
    
    for row in missing:
        account, name, count, first_date, last_date, revenue = row
        name_display = (name[:32] + '...') if name and len(name) > 35 else (name or 'UNKNOWN')
        first_display = first_date.strftime('%Y-%m-%d') if first_date else 'N/A'
        last_display = last_date.strftime('%Y-%m-%d') if last_date else 'N/A'
        revenue_display = f"${revenue:,.2f}" if revenue else "$0.00"
        
        print(f"{account:<10} {name_display:<35} {count:<10} {first_display:<12} {last_display:<12} {revenue_display:<12}")
        
        total_charters += count
        total_revenue += revenue if revenue else 0
    
    print("-"*95)
    print(f"{'TOTALS':<10} {'':<35} {total_charters:<10} {'':<12} {'':<12} ${total_revenue:,.2f}")
    
    return missing

def analyze_recent_customers(cur):
    """Highlight recent customers (2024-2025) that are missing."""
    print("\n" + "="*80)
    print("URGENT: RECENT CUSTOMERS (2024-2025)")
    print("="*80)
    
    cur.execute("""
        SELECT DISTINCT
            lsr.raw_data->>'Account_No' as account_number,
            lsr.raw_data->>'Name' as client_name,
            lsr.raw_data->>'Phone' as phone,
            MAX((lsr.raw_data->>'PU_Date')::DATE) as last_charter,
            SUM((lsr.raw_data->>'Rate')::NUMERIC) as total_revenue,
            COUNT(*) as charter_count
        FROM lms_staging_reserve lsr
        WHERE lsr.raw_data->>'Account_No' IS NOT NULL 
        AND lsr.raw_data->>'Account_No' != ''
        AND (lsr.raw_data->>'PU_Date')::DATE >= '2024-01-01'
        AND NOT EXISTS (
            SELECT 1 FROM clients c
            WHERE c.account_number = lsr.raw_data->>'Account_No'
        )
        GROUP BY 
            lsr.raw_data->>'Account_No',
            lsr.raw_data->>'Name',
            lsr.raw_data->>'Phone'
        ORDER BY MAX((lsr.raw_data->>'PU_Date')::DATE) DESC
    """)
    
    recent = cur.fetchall()
    
    if not recent:
        print("\n[OK] No recent missing customers (all 2024-2025 customers exist)")
        return []
    
    print(f"\n🔥 Found {len(recent)} customers from 2024-2025 that are MISSING:")
    print(f"\n{'Account':<10} {'Customer Name':<30} {'Last Charter':<15} {'Charters':<10} {'Revenue':<12}")
    print("-"*85)
    
    for row in recent:
        account, name, phone, last_date, revenue, count = row
        name_display = (name[:27] + '...') if name and len(name) > 30 else (name or 'UNKNOWN')
        last_display = last_date.strftime('%Y-%m-%d') if last_date else 'N/A'
        revenue_display = f"${revenue:,.2f}" if revenue else "$0.00"
        
        print(f"{account:<10} {name_display:<30} {last_display:<15} {count:<10} {revenue_display:<12}")
    
    return recent

def create_missing_customers(cur, conn, dry_run=True):
    """Create customer records for missing accounts."""
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN MODE - No customers will be created")
        print("="*80)
        return
    
    print("\n" + "="*80)
    print("CREATING MISSING CUSTOMERS")
    print("="*80)
    
    # Get next available client_id
    cur.execute("SELECT COALESCE(MAX(client_id), 0) + 1 FROM clients")
    next_client_id = cur.fetchone()[0]
    
    print(f"\n📋 Next available client_id: {next_client_id}")
    
    # Insert missing customers
    insert_query = """
        INSERT INTO clients (
            client_id,
            account_number,
            client_name,
            primary_phone,
            status,
            created_at,
            updated_at,
            is_inactive
        )
        SELECT DISTINCT ON (lsr.raw_data->>'Account_No')
            ROW_NUMBER() OVER (ORDER BY lsr.raw_data->>'Account_No') + %s - 1 as client_id,
            lsr.raw_data->>'Account_No' as account_number,
            lsr.raw_data->>'Name' as client_name,
            lsr.raw_data->>'Phone' as primary_phone,
            'active' as status,
            CURRENT_TIMESTAMP as created_at,
            CURRENT_TIMESTAMP as updated_at,
            false as is_inactive
        FROM lms_staging_reserve lsr
        WHERE lsr.raw_data->>'Account_No' IS NOT NULL 
        AND lsr.raw_data->>'Account_No' != ''
        AND NOT EXISTS (
            SELECT 1 FROM clients c
            WHERE c.account_number = lsr.raw_data->>'Account_No'
        )
        ORDER BY lsr.raw_data->>'Account_No'
    """
    
    try:
        cur.execute(insert_query, (next_client_id,))
        created_count = cur.rowcount
        
        print(f"[OK] Created {created_count} new customer records")
        
        # Show what was created
        cur.execute("""
            SELECT 
                c.client_id,
                c.account_number,
                c.client_name,
                c.primary_phone
            FROM clients c
            WHERE c.client_id >= %s
            ORDER BY c.client_id
        """, (next_client_id,))
        
        print(f"\n{'ID':<8} {'Account':<10} {'Customer Name':<40} {'Phone':<15}")
        print("-"*80)
        
        for row in cur.fetchall():
            client_id, account, name, phone = row
            name_display = (name[:37] + '...') if name and len(name) > 40 else (name or 'UNKNOWN')
            phone_display = phone if phone else 'N/A'
            print(f"{client_id:<8} {account:<10} {name_display:<40} {phone_display:<15}")
        
        conn.commit()
        print("\n[OK] Changes committed to database")
        
        return created_count
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error creating customers: {e}")
        raise

def verify_charters_can_be_added(cur):
    """Check if any charters are now ready to be added after customers created."""
    print("\n" + "="*80)
    print("CHARTER READINESS CHECK")
    print("="*80)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_reserve lsr
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c 
            WHERE lsr.reserve_no = c.reserve_number
        )
    """)
    
    total_new_charters = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*)
        FROM lms_staging_reserve lsr
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c 
            WHERE lsr.reserve_no = c.reserve_number
        )
        AND EXISTS (
            SELECT 1 FROM clients cl
            WHERE cl.account_number = lsr.raw_data->>'Account_No'
        )
    """)
    
    ready_charters = cur.fetchone()[0]
    
    print(f"\n📊 Total new charters in staging: {total_new_charters}")
    print(f"[OK] Charters with valid customers: {ready_charters}")
    print(f"[WARN]  Charters still missing customers: {total_new_charters - ready_charters}")
    
    if ready_charters > 0:
        print(f"\n💡 {ready_charters} charters are now ready to be promoted!")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Create missing customer records from charter reserves'
    )
    parser.add_argument('--write', action='store_true',
                       help='Create customers in database (default is dry-run)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Analyze only, do not create customers (default)')
    
    args = parser.parse_args()
    
    # Default to dry-run unless --write is specified
    dry_run = not args.write
    
    print("="*80)
    print("CREATE MISSING CUSTOMERS FROM CHARTER RESERVES")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'WRITE (creating customers)'}")
    print("="*80)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Find all missing customers
        missing = find_missing_customers(cur)
        
        if not missing:
            print("\n[OK] No missing customers - all accounts have client records")
            cur.close()
            conn.close()
            return
        
        # Highlight recent customers
        recent = analyze_recent_customers(cur)
        
        # Create customers if not dry-run
        if not dry_run:
            print("\n" + "="*80)
            response = input(f"Proceed with creating {len(missing)} customers? (yes/no): ")
            if response.lower() != 'yes':
                print("[FAIL] Customer creation cancelled")
                cur.close()
                conn.close()
                return
            
            created = create_missing_customers(cur, conn, dry_run=False)
            
            if created:
                # Check charter readiness
                verify_charters_can_be_added(cur)
        else:
            print("\n" + "="*80)
            print("💡 To create these customers, run:")
            print("   python scripts/create_missing_customers_from_reserves.py --write")
        
        cur.close()
        conn.close()
        
        print("\n[OK] Script completed successfully")
        
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
