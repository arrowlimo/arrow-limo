#!/usr/bin/env python3
"""
Demonstrate the new GST staging table workflow for receipt imports.
This shows how to handle GST calculations in staging before inserting into receipts table.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def demonstrate_gst_staging_workflow():
    """Demonstrate the complete staging workflow"""
    print("📋 GST STAGING WORKFLOW DEMONSTRATION")
    print("=" * 50)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Step 1: Insert raw receipt data into staging
        print("📥 STEP 1: Insert raw receipt data into staging")
        
        sample_receipts = [
            {
                'source_system': 'DEMO-QuickBooks',
                'source_reference': 'QB-DEMO-001',
                'receipt_date': '2024-10-15',
                'vendor_name': 'Shell Gas Station',
                'description': 'Fuel purchase - company vehicle',
                'raw_amount': 82.50,  # Tax included amount
                'province_code': 'AB',
                'tax_included': True
            },
            {
                'source_system': 'DEMO-QuickBooks', 
                'source_reference': 'QB-DEMO-002',
                'receipt_date': '2024-10-16',
                'vendor_name': 'Office Depot',
                'description': 'Office supplies',
                'raw_amount': 150.00,  # Pre-tax amount
                'province_code': 'ON',
                'tax_included': False
            },
            {
                'source_system': 'DEMO-Banking',
                'source_reference': 'BANK-DEMO-003', 
                'receipt_date': '2024-10-17',
                'vendor_name': 'Heffner Auto Finance',
                'description': 'Vehicle loan payment',
                'raw_amount': 650.00,  # Tax included
                'province_code': 'AB',
                'tax_included': True
            }
        ]
        
        for receipt in sample_receipts:
            cur.execute("""
                INSERT INTO receipts_gst_staging (
                    source_system, source_reference, receipt_date, vendor_name,
                    description, raw_amount, province_code, tax_included
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                receipt['source_system'],
                receipt['source_reference'], 
                receipt['receipt_date'],
                receipt['vendor_name'],
                receipt['description'],
                receipt['raw_amount'],
                receipt['province_code'],
                receipt['tax_included']
            ))
            
        print(f"   Inserted {len(sample_receipts)} raw receipts into staging")
        
        # Step 2: Run GST calculations
        print(f"\n🧮 STEP 2: Calculate GST amounts using staging function")
        
        cur.execute("""
            UPDATE receipts_gst_staging 
            SET (gross_amount, gst_amount, net_amount) = (
                SELECT gross_amount, gst_amount, net_amount
                FROM calculate_gst_amounts(raw_amount, province_code, tax_included)
            )
            WHERE validation_status = 'pending'
        """)
        
        # Step 3: Auto-categorize expenses  
        print(f"📊 STEP 3: Auto-categorize expenses")
        
        cur.execute("""
            UPDATE receipts_gst_staging 
            SET category = CASE
                WHEN LOWER(vendor_name) LIKE '%shell%' OR LOWER(vendor_name) LIKE '%gas%' THEN 'fuel'
                WHEN LOWER(vendor_name) LIKE '%office%' OR LOWER(description) LIKE '%supplies%' THEN 'office_supplies'
                WHEN LOWER(vendor_name) LIKE '%heffner%' OR LOWER(description) LIKE '%loan%' THEN 'vehicle_finance'
                ELSE 'expense'
            END,
            validation_status = 'calculated'
            WHERE validation_status = 'pending'
        """)
        
        # Step 4: Review calculated results
        print(f"\n📋 STEP 4: Review calculated results in staging")
        
        cur.execute("""
            SELECT 
                source_reference,
                vendor_name,
                raw_amount,
                province_code,
                tax_included,
                gross_amount,
                gst_amount, 
                net_amount,
                category
            FROM receipts_gst_staging
            WHERE source_system LIKE 'DEMO%'
            ORDER BY source_reference
        """)
        
        results = cur.fetchall()
        print(f"{'Ref':<12} {'Vendor':<20} {'Raw':<8} {'Prov':<4} {'TaxInc':<6} {'Gross':<8} {'GST':<6} {'Net':<8} {'Category':<15}")
        print(f"{'-' * 12} {'-' * 20} {'-' * 8} {'-' * 4} {'-' * 6} {'-' * 8} {'-' * 6} {'-' * 8} {'-' * 15}")
        
        for row in results:
            ref, vendor, raw, prov, tax_inc, gross, gst, net, cat = row
            vendor_short = vendor[:18] if vendor else ''
            print(f"{ref:<12} {vendor_short:<20} ${raw:<7.2f} {prov:<4} {'Yes' if tax_inc else 'No':<6} ${gross:<7.2f} ${gst:<5.2f} ${net:<7.2f} {cat:<15}")
        
        # Step 5: Validate calculations
        print(f"\n[OK] STEP 5: Validate calculations")
        
        cur.execute("""
            SELECT COUNT(*) as total_records,
                   COUNT(*) FILTER (WHERE ABS(gross_amount - (gst_amount + net_amount)) < 0.01) as valid_calcs,
                   SUM(gross_amount) as total_gross,
                   SUM(gst_amount) as total_gst,
                   SUM(net_amount) as total_net
            FROM receipts_gst_staging 
            WHERE source_system LIKE 'DEMO%'
        """)
        
        total, valid, gross_sum, gst_sum, net_sum = cur.fetchone()
        print(f"   Total records: {total}")
        print(f"   Valid calculations: {valid}/{total}")
        print(f"   Total gross: ${gross_sum:.2f}")
        print(f"   Total GST: ${gst_sum:.2f}")
        print(f"   Total net: ${net_sum:.2f}")
        print(f"   Calculation verification: ${gross_sum:.2f} = ${gst_sum:.2f} + ${net_sum:.2f} = ${gst_sum + net_sum:.2f}")
        
        # Step 6: Promote to receipts table
        print(f"\n📤 STEP 6: Promote validated records to receipts table")
        
        cur.execute("""
            INSERT INTO receipts (
                source_system, source_reference, receipt_date, vendor_name,
                description, currency, gross_amount, gst_amount, net_amount,
                category, validation_status, created_at, source_hash
            )
            SELECT 
                source_system, source_reference, receipt_date, vendor_name,
                description, currency, gross_amount, gst_amount, net_amount,
                category, 'imported_from_staging', NOW(),
                MD5(CONCAT(receipt_date::text, '|', vendor_name, '|', gross_amount::text, '|', description, '|', source_reference)) as source_hash
            FROM receipts_gst_staging 
            WHERE source_system LIKE 'DEMO%' AND validation_status = 'calculated'
            RETURNING id, source_reference, gross_amount, gst_amount, net_amount
        """)
        
        promoted = cur.fetchall()
        print(f"   Promoted {len(promoted)} records to receipts table:")
        for receipt_id, ref, gross, gst, net in promoted:
            print(f"     ID {receipt_id}: {ref} = ${gross:.2f} (${gst:.2f} GST + ${net:.2f} net)")
        
        # Step 7: Update staging with receipt IDs
        cur.execute("""
            UPDATE receipts_gst_staging s
            SET receipt_id = r.id,
                processed_at = NOW(),
                validation_status = 'completed'
            FROM receipts r
            WHERE s.source_system = r.source_system 
              AND s.source_reference = r.source_reference
              AND s.source_system LIKE 'DEMO%'
        """)
        
        conn.commit()
        
        print(f"\n🎯 WORKFLOW COMPLETE!")
        print(f"   [OK] Raw data imported to staging")
        print(f"   [OK] GST calculations performed")
        print(f"   [OK] Auto-categorization applied")
        print(f"   [OK] Validation completed")
        print(f"   [OK] Records promoted to receipts table")
        print(f"   [OK] Staging updated with final IDs")
        
        # Clean up demo records
        print(f"\n🧹 Cleaning up demo records...")
        cur.execute("DELETE FROM receipts WHERE source_system LIKE 'DEMO%'")
        cur.execute("DELETE FROM receipts_gst_staging WHERE source_system LIKE 'DEMO%'")
        conn.commit()
        print(f"   Demo records removed")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        conn.rollback()
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    demonstrate_gst_staging_workflow()

if __name__ == "__main__":
    main()