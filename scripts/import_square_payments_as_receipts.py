#!/usr/bin/env python3
"""
Import Square Capital loan payments as receipts for GL coding.
Creates receipt records for all automatic loan payments.
"""

import os
import psycopg2
from datetime import datetime
from decimal import Decimal

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def get_or_create_square_vendor(conn):
    """Get or create SQUARE CAPITAL vendor."""
    cur = conn.cursor()
    
    # Check if vendor exists
    cur.execute("""
        SELECT id FROM vendors 
        WHERE UPPER(vendor_name) = 'SQUARE CAPITAL'
    """)
    
    result = cur.fetchone()
    if result:
        vendor_id = result[0]
        print(f"✓ Using existing vendor: SQUARE CAPITAL (id={vendor_id})")
    else:
        # Create vendor
        cur.execute("""
            INSERT INTO vendors (vendor_name, qb_vendor_type)
            VALUES ('SQUARE CAPITAL', 'Financing')
            RETURNING id
        """)
        vendor_id = cur.fetchone()[0]
        conn.commit()
        print(f"✓ Created vendor: SQUARE CAPITAL (id={vendor_id})")
    
    cur.close()
    return vendor_id


def import_loan_payments_as_receipts(conn, vendor_name, dry_run=True):
    """Import Square loan payments as receipts."""
    cur = conn.cursor()
    
    try:
        # Get all automatic payments (these are expenses - money out)
        cur.execute("""
            SELECT 
                id,
                activity_date,
                description,
                amount,
                source_file
            FROM square_capital_activity
            WHERE description ILIKE '%automatic payment%'
            ORDER BY activity_date
        """)
        
        payments = cur.fetchall()
        
        print(f"\n📋 Found {len(payments)} loan payment transactions")
        
        if len(payments) == 0:
            print("⚠️  No payment records found")
            return
        
        # Check which already have receipts
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE UPPER(vendor_name) = %s
            AND description ILIKE '%%square%%loan%%payment%%'
        """, (vendor_name.upper(),))
        
        existing = cur.fetchone()[0]
        print(f"💾 Existing receipts: {existing}")
        
        inserted = 0
        skipped = 0
        
        for activity_id, pay_date, description, amount, source_file in payments:
            # Check if receipt already exists for this activity
            cur.execute("""
                SELECT receipt_id 
                FROM receipts 
                WHERE UPPER(vendor_name) = %s
                AND receipt_date = %s 
                AND gross_amount = %s
            """, (vendor_name.upper(), pay_date, amount))
            
            if cur.fetchone():
                skipped += 1
                continue
            
            if not dry_run:
                # Insert receipt
                cur.execute("""
                    INSERT INTO receipts (
                        vendor_name,
                        receipt_date,
                        gross_amount,
                        net_amount,
                        gst_amount,
                        description,
                        payment_method,
                        category,
                        created_from_banking
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING receipt_id
                """, (
                    vendor_name,
                    pay_date,
                    amount,  # Gross (principal + fee)
                    amount,  # Net (no GST on loan payments)
                    Decimal('0.00'),  # No GST
                    f"Square Capital Loan Payment - {description}",
                    'bank_transfer',
                    'Financing Costs',  # Category
                    True  # Mark as auto-created
                ))
                
                receipt_id = cur.fetchone()[0]
                inserted += 1
                
                if inserted <= 5:  # Show first 5
                    print(f"  [{pay_date}] Receipt #{receipt_id}: ${amount:.2f} - {description[:50]}")
            else:
                inserted += 1
                
                if inserted <= 5:  # Show first 5 in dry run
                    print(f"  [DRY RUN] {pay_date}: ${amount:.2f} - {description[:50]}")
        
        if inserted > 5:
            print(f"  ... and {inserted - 5} more")
        
        if not dry_run and inserted > 0:
            conn.commit()
        
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
        print(f"  New receipts: {inserted}")
        print(f"  Duplicates skipped: {skipped}")
        print(f"  Total Square receipts: {existing + inserted}")
        
        # Calculate totals
        cur.execute("""
            SELECT 
                SUM(gross_amount) as total_expense,
                MIN(receipt_date) as first_payment,
                MAX(receipt_date) as last_payment,
                COUNT(*) as payment_count
            FROM receipts
            WHERE UPPER(vendor_name) = %s
        """, (vendor_name.upper(),))
        
        total_exp, first_pay, last_pay, pay_count = cur.fetchone()
        
        if pay_count > 0:
            print(f"\n💰 Square Capital Expense Summary:")
            print(f"  Period: {first_pay} to {last_pay}")
            print(f"  Payments: {pay_count}")
            print(f"  Total Expense: ${total_exp:,.2f}")
        
        return inserted, skipped
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    print("=" * 70)
    print("SQUARE LOAN PAYMENTS → RECEIPTS IMPORT")
    print("=" * 70)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --write to apply changes\n")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        # Get/create Square vendor
        vendor_name = 'SQUARE CAPITAL'
        print(f"✓ Using vendor: {vendor_name}\n")
        
        # Import payments as receipts
        import_loan_payments_as_receipts(conn, vendor_name, dry_run)
        
        print("\n" + "=" * 70)
        print("✓ IMPORT COMPLETE")
        print("=" * 70)
        
        if dry_run:
            print("\n💡 Run with --write to create receipt records")
        else:
            print("\n✅ Square loan payments now tracked in receipts table")
            print("   Category: Financing Costs")
            print("   Vendor: SQUARE CAPITAL")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
