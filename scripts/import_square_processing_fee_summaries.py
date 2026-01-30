#!/usr/bin/env python3
"""
Import Square processing fees from annual summary CSV files.
Creates receipt records for all Square merchant processing fees (2022-2025).
"""

import os
import csv
import psycopg2
from decimal import Decimal
from datetime import date

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")

FEE_FILES = [
    ("l:/limo/Square reports/Fees-01_01_2022 - 12_31_2022.csv", 2022),
    ("l:/limo/Square reports/Fees-01_01_2023 - 12_31_2023.csv", 2023),
    ("l:/limo/Square reports/Fees-01_01_2024 - 12_31_2024.csv", 2024),
    ("l:/limo/Square reports/Fees-01_01_2025 - 12_31_2025.csv", 2025),
]


def parse_currency(value):
    """Parse currency string to Decimal: 'CA$356,244.62' or '(CA$10,653.02)'"""
    # Remove CA$, commas, spaces
    clean = value.replace('CA$', '').replace(',', '').replace(' ', '').strip()
    
    # Handle negative values in parentheses
    if clean.startswith('(') and clean.endswith(')'):
        clean = '-' + clean[1:-1]
    
    return Decimal(clean)


def import_fee_file(conn, filepath, year, dry_run=True):
    """Import one fee summary file."""
    print(f"\n📄 Processing: {os.path.basename(filepath)}")
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:  # Handle BOM
        reader = csv.DictReader(f)
        
        rows_processed = 0
        for row in reader:
            fee_type = row.get('Fee Type', '').strip()
            
            # Skip total row and empty rows
            if not fee_type or fee_type.lower() == 'total':
                continue
            
            rows_processed += 1
            
            # Extract fee data
            payment_amt = parse_currency(row['Payment amount'])
            refund_amt = parse_currency(row['Refund amount'])
            total_fees = parse_currency(row['Total fees (incl. taxes)'])
            cost_pct = row['Cost of acceptance'].replace('%', '').strip()
            total_collected = parse_currency(row['Total collected'])
            
            print(f"\n  {fee_type}:")
            print(f"    Payments: ${payment_amt:,.2f}")
            print(f"    Refunds: ${refund_amt:,.2f}")
            print(f"    Total fees: ${abs(total_fees):,.2f}")
            print(f"    Fee rate: {cost_pct}%")
            
            # Create receipt for the total fees
            if total_fees != 0:
                create_fee_receipt(conn, year, fee_type, abs(total_fees), dry_run)
        
        return rows_processed > 0


def create_fee_receipt(conn, year, fee_type, fee_amount, dry_run=True):
    """Create a receipt for annual Square processing fees."""
    cur = conn.cursor()
    vendor_name = 'SQUARE PROCESSING FEES'
    
    # Use Dec 31 of the year as the receipt date
    receipt_date = date(year, 12, 31)
    description = f"Square {fee_type} - {year} Annual Total"
    
    try:
        # Check if receipt already exists
        cur.execute("""
            SELECT receipt_id 
            FROM receipts 
            WHERE UPPER(vendor_name) = %s
            AND receipt_date = %s
            AND description ILIKE %s
        """, (vendor_name.upper(), receipt_date, f"%{year}%"))
        
        if cur.fetchone():
            print(f"    ⚠️  Receipt already exists for {year}")
            return False
        
        if not dry_run:
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
                receipt_date,
                fee_amount,
                fee_amount,  # No GST on processing fees
                Decimal('0.00'),
                description,
                'bank_transfer',
                'Merchant Services',
                True
            ))
            
            receipt_id = cur.fetchone()[0]
            conn.commit()
            print(f"    ✓ Created receipt #{receipt_id}: ${fee_amount:,.2f}")
            return True
        else:
            print(f"    [DRY RUN] Would create receipt: ${fee_amount:,.2f}")
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"    ❌ Error: {e}")
        return False
    finally:
        cur.close()


def main():
    import sys
    dry_run = '--write' not in sys.argv
    
    print("=" * 70)
    print("SQUARE PROCESSING FEES IMPORT (Annual Summaries)")
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
        total_imported = 0
        
        for filepath, year in FEE_FILES:
            if os.path.exists(filepath):
                result = import_fee_file(conn, filepath, year, dry_run)
                if result:
                    total_imported += 1
            else:
                print(f"\n⚠️  File not found: {filepath}")
        
        print("\n" + "=" * 70)
        print("✓ IMPORT COMPLETE")
        print("=" * 70)
        
        if dry_run:
            print("\n💡 Run with --write to create receipt records")
        else:
            print(f"\n✅ Created {total_imported} Square processing fee receipts")
            print("   Category: Merchant Services")
            print("   Vendor: SQUARE PROCESSING FEES")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
