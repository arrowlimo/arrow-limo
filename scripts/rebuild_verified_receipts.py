#!/usr/bin/env python3
"""
Step 2: Add tracking columns and rebuild receipts from verified banking.
"""
import psycopg2
from datetime import datetime
from decimal import Decimal

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def calculate_gst(gross_amount, tax_rate=0.05):
    """GST is INCLUDED in amount (Alberta 5% GST)."""
    if not gross_amount:
        return 0, gross_amount or 0
    
    gst_amount = gross_amount * Decimal(str(tax_rate)) / (Decimal('1') + Decimal(str(tax_rate)))
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*70)
    print("STEP 2: ADD TRACKING COLUMNS & REBUILD FROM VERIFIED BANKING")
    print("="*70)
    
    # Add tracking columns
    print("\n📋 Adding tracking columns to receipts table...")
    
    columns_to_add = [
        ("verified_source", "TEXT", "Source of verification (e.g., 'CIBC 1615 PDF', 'Scotia PDF')"),
        ("is_verified_banking", "BOOLEAN DEFAULT FALSE", "True if created from PDF-verified banking"),
        ("potential_duplicate", "BOOLEAN DEFAULT FALSE", "True if might be a QuickBooks duplicate"),
        ("duplicate_check_key", "TEXT", "Hash of date+amount for duplicate detection"),
    ]
    
    for col_name, col_type, description in columns_to_add:
        # Check if column exists
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'receipts' AND column_name = %s
        """, (col_name,))
        
        if cur.fetchone()[0] == 0:
            print(f"  Adding {col_name}...")
            cur.execute(f"ALTER TABLE receipts ADD COLUMN {col_name} {col_type}")
            print(f"    ✅ Added: {description}")
        else:
            print(f"  ✓ {col_name} already exists")
    
    conn.commit()
    print("\n✅ Tracking columns ready\n")
    
    # Disable banking triggers
    print("🔓 Disabling banking triggers temporarily...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER ALL;")
    print("✅ Triggers disabled\n")
    
    # Get verified banking transactions
    print("="*70)
    print("REBUILDING RECEIPTS FROM VERIFIED BANKING")
    print("="*70)
    
    verified_sources = [
        ('verified_2013_2014_scotia', 'Scotia PDF 2013-2014', 2),
        ('CIBC_7461615_2012_2017_VERIFIED.xlsx', 'CIBC 1615 PDF 2012-2017', 4),
    ]
    
    total_created = 0
    
    for source_file, verified_label, bank_id in verified_sources:
        print(f"\n{'='*70}")
        print(f"Processing: {verified_label}")
        print(f"Source: {source_file}")
        print(f"{'='*70}\n")
        
        # Get banking transactions for this source
        cur.execute("""
            SELECT 
                transaction_id,
                account_number,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                vendor_extracted
            FROM banking_transactions
            WHERE source_file = %s
            ORDER BY transaction_date, transaction_id
        """, (source_file,))
        
        transactions = cur.fetchall()
        print(f"Found {len(transactions):,} banking transactions")
        
        created_count = 0
        skipped_count = 0
        
        for trans in transactions:
            trans_id, account_num, trans_date, description, debit, credit, vendor = trans
            
            # Determine amount (debit = expense, credit = revenue/deposit)
            if debit and debit != 0:
                gross_amount = abs(debit)
                is_expense = True
            elif credit and credit != 0:
                gross_amount = abs(credit)
                is_expense = False
            else:
                skipped_count += 1
                continue  # Skip zero-amount transactions
            
            # Calculate GST
            gst_amount, net_amount = calculate_gst(gross_amount)
            
            # Create duplicate check key (date + amount)
            dup_key = f"{trans_date}_{gross_amount}"
            
            # Insert receipt
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date,
                    vendor_name,
                    description,
                    gross_amount,
                    gst_amount,
                    net_amount,
                    banking_transaction_id,
                    created_from_banking,
                    verified_source,
                    is_verified_banking,
                    duplicate_check_key,
                    mapped_bank_account_id,
                    source_system
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING receipt_id
            """, (
                trans_date,
                vendor or 'Unknown',
                description,
                gross_amount if is_expense else None,  # expense in gross_amount
                gst_amount,
                net_amount,
                trans_id,
                True,
                verified_label,
                True,
                dup_key,
                bank_id,
                'verified_banking'
            ))
            
            receipt_id = cur.fetchone()[0]
            
            # Update banking transaction to link back to receipt
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (receipt_id, trans_id))
            
            created_count += 1
            
            if created_count % 500 == 0:
                print(f"  Created {created_count:,} receipts...")
        
        conn.commit()
        
        print(f"\n✅ {verified_label}:")
        print(f"   Created: {created_count:,} receipts")
        if skipped_count > 0:
            print(f"   Skipped: {skipped_count:,} (zero amount)")
        
        total_created += created_count
    
    # Re-enable triggers
    print(f"\n🔒 Re-enabling banking triggers...")
    cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER ALL;")
    print("✅ Triggers re-enabled")
    
    print(f"\n{'='*70}")
    print(f"STEP 2 COMPLETE")
    print(f"{'='*70}")
    print(f"Total receipts created from verified banking: {total_created:,}")
    
    # Final count
    cur.execute("SELECT COUNT(*) FROM receipts")
    final_total = cur.fetchone()[0]
    print(f"Total receipts in database: {final_total:,}")
    
    # Count by verification status
    cur.execute("""
        SELECT is_verified_banking, COUNT(*) 
        FROM receipts 
        GROUP BY is_verified_banking
        ORDER BY is_verified_banking DESC NULLS LAST
    """)
    print(f"\nBreakdown:")
    for row in cur.fetchall():
        verified = row[0]
        count = row[1]
        label = "Verified banking" if verified else "Other sources"
        print(f"  {label}: {count:,}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
