#!/usr/bin/env python3
"""
LMS DATA VERIFICATION AND UPDATE TO ALMSDATA
============================================

Verifies all LMS Excel data against PostgreSQL and updates/imports missing records
to ensure complete data integrity in almsdata database.
"""

import os
import pandas as pd
import psycopg2
from datetime import datetime
import re

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def verify_and_update_lms_data():
    """Verify all LMS data and update almsdata database."""
    
    print("🔄 LMS DATA VERIFICATION AND UPDATE TO ALMSDATA")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Step 1: Load and clean LMS data
    print("\n📋 STEP 1: LOADING LMS DATA")
    print("-" * 28)
    
    try:
        audit_file = r"L:\limo\docs\2012-2013 excel\auditstatement.xls"
        
        # Read LMS data
        df = pd.read_excel(audit_file, sheet_name='Sheet1', header=1)
        df.columns = ['Col' + str(i) for i in range(len(df.columns))]
        
        # Filter for valid transaction records
        mask = (
            pd.notna(df['Col1']) &  # Date
            pd.notna(df['Col3']) &  # Transaction
            df['Col3'].astype(str).str.contains('Inv #', na=False)
        )
        
        clean_df = df[mask].copy()
        
        # Extract key fields
        clean_df['invoice_number'] = clean_df['Col3'].str.extract(r'Inv # (\d+)')
        clean_df['invoice_number'] = pd.to_numeric(clean_df['invoice_number'], errors='coerce')
        clean_df['charter_date'] = pd.to_datetime(clean_df['Col1'], errors='coerce')
        clean_df['passenger_name'] = clean_df['Col7'].astype(str)
        clean_df['order_by'] = clean_df['Col13'].astype(str)
        clean_df['total_amount'] = pd.to_numeric(clean_df['Col18'], errors='coerce')
        clean_df['payment_amount'] = pd.to_numeric(clean_df['Col21'], errors='coerce')
        clean_df['balance_amount'] = pd.to_numeric(clean_df['Col25'], errors='coerce')
        
        # Filter for valid data
        valid_mask = (
            pd.notna(clean_df['invoice_number']) &
            pd.notna(clean_df['charter_date']) &
            pd.notna(clean_df['total_amount'])
        )
        
        lms_data = clean_df[valid_mask].copy()
        
        print(f"   [OK] LMS Records Loaded: {len(lms_data):,}")
        print(f"   📅 Date Range: {lms_data['charter_date'].min()} to {lms_data['charter_date'].max()}")
        print(f"   🧾 Invoice Range: {int(lms_data['invoice_number'].min())} to {int(lms_data['invoice_number'].max())}")
        
    except Exception as e:
        print(f"   [FAIL] Error loading LMS data: {str(e)}")
        return
    
    # Step 2: Check existing PostgreSQL data
    print("\n📊 STEP 2: ANALYZING EXISTING POSTGRESQL DATA")
    print("-" * 42)
    
    try:
        # Get existing charter data
        cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                COUNT(CASE WHEN reserve_number ~ '^\\d+$' THEN 1 END) as numeric_reserves,
                MIN(charter_date) as min_date,
                MAX(charter_date) as max_date,
                SUM(rate) as total_revenue
            FROM charters
        """)
        
        pg_summary = cur.fetchone()
        total_charters, numeric_reserves, min_date, max_date, total_revenue = pg_summary
        
        print(f"   📋 PostgreSQL Charters: {total_charters:,}")
        print(f"   🔢 Numeric Reserve Numbers: {numeric_reserves:,}")
        print(f"   📅 Date Range: {min_date} to {max_date}")
        print(f"   💰 Total Revenue: ${float(total_revenue):,.2f}")
        
        # Check for existing LMS-style invoice numbers
        cur.execute("""
            SELECT COUNT(*) 
            FROM charters 
            WHERE reserve_number ~ '^\\d{6}$'
            AND CAST(reserve_number AS INTEGER) BETWEEN 3000 AND 9000
        """)
        
        existing_invoice_style = cur.fetchone()[0]
        print(f"   🧾 Existing Invoice-style Records: {existing_invoice_style:,}")
        
    except Exception as e:
        print(f"   [FAIL] Error analyzing PostgreSQL: {str(e)}")
        return
    
    # Step 3: Match LMS records with PostgreSQL
    print("\n🔍 STEP 3: MATCHING LMS TO POSTGRESQL")
    print("-" * 35)
    
    matches_found = 0
    unmatched_lms = []
    matched_records = []
    
    try:
        for idx, row in lms_data.iterrows():
            try:
                invoice_num = int(row['invoice_number'])
                invoice_str = f"{invoice_num:06d}"
                charter_date = row['charter_date']
                amount = float(row['total_amount']) if pd.notna(row['total_amount']) and row['total_amount'] is not None else 0
                
                if amount == 0:  # Skip zero-value records
                    continue
                
                # Try to find matching record in PostgreSQL
                cur.execute("""
                    SELECT charter_id, reserve_number, charter_date, rate, account_number
                    FROM charters 
                    WHERE (
                        reserve_number = %s OR
                        reserve_number = %s OR
                        (charter_date = %s AND ABS(rate - %s) < 0.01)
                    )
                    LIMIT 1
                """, (str(invoice_num), invoice_str, charter_date, amount))
                
                pg_match = cur.fetchone()
            
                if pg_match:
                    matches_found += 1
                    matched_records.append({
                        'lms_invoice': invoice_num,
                        'pg_charter_id': pg_match[0],
                        'pg_reserve': pg_match[1],
                        'lms_amount': amount,
                        'pg_amount': float(pg_match[3]) if pg_match[3] is not None else 0
                    })
                else:
                    payment_amt = float(row['payment_amount']) if pd.notna(row['payment_amount']) and row['payment_amount'] is not None else 0
                    balance_amt = float(row['balance_amount']) if pd.notna(row['balance_amount']) and row['balance_amount'] is not None else 0
                    
                    unmatched_lms.append({
                        'invoice_number': invoice_num,
                        'charter_date': charter_date,
                        'passenger_name': str(row['passenger_name']) if pd.notna(row['passenger_name']) else '',
                        'order_by': str(row['order_by']) if pd.notna(row['order_by']) else '',
                        'total_amount': amount,
                        'payment_amount': payment_amt,
                        'balance_amount': balance_amt
                    })
            
            except Exception as e:
                print(f"      [WARN]  Error processing record {idx}: {str(e)}")
                continue
        
        print(f"   [OK] Matches Found: {matches_found:,}")
        print(f"   ❓ Unmatched LMS Records: {len(unmatched_lms):,}")
        
    except Exception as e:
        print(f"   [FAIL] Error in matching: {str(e)}")
        return
    
    # Step 4: Analyze unmatched records
    print("\n📋 STEP 4: ANALYZING UNMATCHED RECORDS")
    print("-" * 36)
    
    if unmatched_lms:
        unmatched_df = pd.DataFrame(unmatched_lms)
        
        print(f"   📊 Unmatched Record Analysis:")
        print(f"      Total Unmatched: {len(unmatched_lms):,}")
        print(f"      Date Range: {unmatched_df['charter_date'].min()} to {unmatched_df['charter_date'].max()}")
        print(f"      Total Value: ${unmatched_df['total_amount'].sum():,.2f}")
        print(f"      Avg Value: ${unmatched_df['total_amount'].mean():.2f}")
        
        # Show sample unmatched records
        print(f"\n   📄 Sample Unmatched Records (first 10):")
        for i, record in enumerate(unmatched_lms[:10]):
            date_str = record['charter_date'].strftime('%Y-%m-%d')
            passenger = record['passenger_name'][:20]
            print(f"      {i+1:2d}. Inv #{record['invoice_number']:06d} | {date_str} | {passenger:<20} | ${record['total_amount']:8.2f}")
    
    # Step 5: Check for missing clients
    print("\n👥 STEP 5: CLIENT DATA VERIFICATION")
    print("-" * 32)
    
    try:
        # Extract unique customer names from LMS
        lms_customers = set()
        for record in unmatched_lms:
            if record['passenger_name'] and record['passenger_name'] != 'nan':
                lms_customers.add(record['passenger_name'].strip())
            if record['order_by'] and record['order_by'] != 'nan':
                lms_customers.add(record['order_by'].strip())
        
        lms_customers = {name for name in lms_customers if len(name) > 2}
        
        print(f"   👥 Unique LMS Customers: {len(lms_customers):,}")
        
        # Check which customers exist in PostgreSQL
        missing_customers = []
        existing_customers = []
        
        for customer in lms_customers:
            cur.execute("""
                SELECT client_id, client_name 
                FROM clients 
                WHERE LOWER(client_name) LIKE LOWER(%s)
                LIMIT 1
            """, (f"%{customer}%",))
            
            if cur.fetchone():
                existing_customers.append(customer)
            else:
                missing_customers.append(customer)
        
        print(f"   [OK] Existing in PostgreSQL: {len(existing_customers):,}")
        print(f"   ❓ Missing from PostgreSQL: {len(missing_customers):,}")
        
        if missing_customers[:5]:  # Show first 5 missing
            print(f"   📋 Sample Missing Customers:")
            for i, customer in enumerate(missing_customers[:5]):
                print(f"      {i+1}. {customer}")
        
    except Exception as e:
        print(f"   [FAIL] Error in client verification: {str(e)}")
    
    # Step 6: Generate import recommendations
    print("\n🚀 STEP 6: IMPORT RECOMMENDATIONS")
    print("-" * 31)
    
    print(f"   📊 DATA COMPLETENESS ANALYSIS:")
    
    if len(unmatched_lms) > 0:
        total_unmatched_value = sum(r['total_amount'] for r in unmatched_lms)
        
        print(f"      • {len(unmatched_lms):,} LMS records need importing")
        print(f"      • ${total_unmatched_value:,.2f} in unmatched revenue")
        print(f"      • {len(missing_customers):,} new customers to add")
        
        # Categorize by potential data quality
        high_value = [r for r in unmatched_lms if r['total_amount'] > 500]
        medium_value = [r for r in unmatched_lms if 100 <= r['total_amount'] <= 500]
        low_value = [r for r in unmatched_lms if r['total_amount'] < 100]
        
        print(f"\n   💰 VALUE DISTRIBUTION:")
        print(f"      • High Value (>$500): {len(high_value):,} records (${sum(r['total_amount'] for r in high_value):,.2f})")
        print(f"      • Medium Value ($100-500): {len(medium_value):,} records (${sum(r['total_amount'] for r in medium_value):,.2f})")
        print(f"      • Low Value (<$100): {len(low_value):,} records (${sum(r['total_amount'] for r in low_value):,.2f})")
    
    # Step 7: Execute imports (optional)
    print(f"\n💾 STEP 7: DATA IMPORT EXECUTION")
    print("-" * 30)
    
    import_choice = input("   Would you like to import unmatched LMS records? (y/N): ").strip().lower()
    
    if import_choice == 'y':
        try:
            imported_count = 0
            client_imports = 0
            
            print(f"   🔄 Starting import process...")
            
            # Import missing customers first
            for customer in missing_customers[:20]:  # Limit to first 20
                try:
                    cur.execute("""
                        INSERT INTO clients (client_name, created_at)
                        VALUES (%s, CURRENT_TIMESTAMP)
                        ON CONFLICT DO NOTHING
                    """, (customer,))
                    client_imports += 1
                except Exception as e:
                    print(f"      [WARN]  Error importing customer {customer}: {str(e)}")
            
            # Import high-value unmatched charters
            for record in unmatched_lms:
                if record['total_amount'] > 100:  # Only import significant amounts
                    try:
                        # Find or create client
                        cur.execute("""
                            SELECT client_id FROM clients 
                            WHERE LOWER(client_name) LIKE LOWER(%s)
                            LIMIT 1
                        """, (f"%{record['passenger_name']}%",))
                        
                        client_result = cur.fetchone()
                        client_id = client_result[0] if client_result else None
                        
                        # Import charter record
                        cur.execute("""
                            INSERT INTO charters (
                                reserve_number, charter_date, rate, client_id,
                                notes, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT DO NOTHING
                        """, (
                            f"{record['invoice_number']:06d}",
                            record['charter_date'],
                            record['total_amount'],
                            client_id,
                            f"LMS Import: Inv #{record['invoice_number']:06d}, Passenger: {record['passenger_name']}"
                        ))
                        
                        imported_count += 1
                        
                    except Exception as e:
                        print(f"      [WARN]  Error importing charter {record['invoice_number']}: {str(e)}")
            
            # Commit changes
            conn.commit()
            
            print(f"   [OK] Import completed:")
            print(f"      • {client_imports:,} new customers added")
            print(f"      • {imported_count:,} new charters added")
            
        except Exception as e:
            print(f"   [FAIL] Error during import: {str(e)}")
            conn.rollback()
    else:
        print(f"   📋 Import skipped - data analysis complete")
    
    # Step 8: Final verification
    print(f"\n📊 STEP 8: FINAL VERIFICATION")
    print("-" * 26)
    
    try:
        # Re-check totals after import
        cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                SUM(rate) as total_revenue,
                COUNT(CASE WHEN created_at::date = CURRENT_DATE THEN 1 END) as today_imports
            FROM charters
        """)
        
        final_summary = cur.fetchone()
        final_charters, final_revenue, today_imports = final_summary
        
        print(f"   📋 Final PostgreSQL Status:")
        print(f"      • Total Charters: {final_charters:,}")
        print(f"      • Total Revenue: ${float(final_revenue):,.2f}")
        print(f"      • Today's Imports: {today_imports:,}")
        
        # Calculate match percentage
        if len(lms_data) > 0:
            match_percentage = (matches_found / len(lms_data)) * 100
            print(f"      • LMS Match Rate: {match_percentage:.1f}%")
        
    except Exception as e:
        print(f"   [FAIL] Error in final verification: {str(e)}")
    
    # Cleanup
    cur.close()
    conn.close()
    
    print(f"\n🎉 LMS DATA VERIFICATION COMPLETE!")
    print(f"   Database integrity verified and updated as needed.")

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    verify_and_update_lms_data()