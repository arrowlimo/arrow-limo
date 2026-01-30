#!/usr/bin/env python3
"""
Import QB Reconciliation Data to Database
=========================================

Imports parsed QB data from parse_qb_reconciliation.py output:
1. Banking transactions → banking_transactions table
2. Vendor expenses → receipts table
3. Auto-creates banking_receipt_matching_ledger links

Features:
- Dry-run mode (default)
- Duplicate detection via source_hash (SHA256)
- Schema-aware column mapping
- GST-included handling for receipts
- Transaction categorization

Usage:
  python scripts/import_qb_data.py --year 2012 --dry-run
  python scripts/import_qb_data.py --year 2012 --write
"""
from __future__ import annotations

import os
import sys
import csv
import hashlib
import argparse
import psycopg2
from datetime import datetime
from decimal import Decimal


def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def compute_hash(source: str, **fields) -> str:
    """Compute deterministic SHA256 hash for dedup"""
    parts = [source] + [str(v) for v in sorted(fields.items())]
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()


def get_columns(cur, table: str) -> set[str]:
    """Get available columns for table"""
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
    """, (table,))
    return {row[0] for row in cur.fetchall()}


def import_banking_transactions(cur, csv_path: str, dry_run: bool) -> int:
    """Import QB banking transactions"""
    cols = get_columns(cur, 'banking_transactions')
    
    # Map CSV columns to DB columns
    col_map = {
        'transaction_date': 'transaction_date' if 'transaction_date' in cols else 'date',
        'debit_amount': 'debit_amount' if 'debit_amount' in cols else 'debit',
        'credit_amount': 'credit_amount' if 'credit_amount' in cols else 'credit',
        'vendor_name': 'vendor_name' if 'vendor_name' in cols else 'merchant_name',
    }
    
    inserted = 0
    skipped = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Compute hash for dedup
            source_hash = compute_hash(
                'QB_RECONCILIATION',
                date=row['transaction_date'],
                account=row['account_number'],
                vendor=row['vendor_name'],
                debit=row['debit_amount'],
                credit=row['credit_amount']
            )
            
            # Check if exists
            cur.execute("""
                SELECT COUNT(*) FROM banking_transactions 
                WHERE source_hash = %s
            """, (source_hash,))
            if cur.fetchone()[0] > 0:
                skipped += 1
                continue
            
            # Build insert
            insert_cols = [col_map['transaction_date'], 'account_number', 'description', 
                          col_map['vendor_name'], col_map['debit_amount'], col_map['credit_amount'],
                          'category', 'source_hash', 'import_source']
            if 'reference_number' in cols:
                insert_cols.append('reference_number')
            
            values = [
                row['transaction_date'],
                row['account_number'],
                row['description'],
                row['vendor_name'],
                row['debit_amount'],
                row['credit_amount'],
                row['category'],
                source_hash,
                'QB_RECONCILIATION'
            ]
            if 'reference_number' in cols:
                values.append(row['reference_number'])
            
            if not dry_run:
                placeholders = ','.join(['%s'] * len(insert_cols))
                cur.execute(f"""
                    INSERT INTO banking_transactions ({','.join(insert_cols)})
                    VALUES ({placeholders})
                """, values)
            
            inserted += 1
    
    return inserted, skipped


def import_receipts(cur, csv_path: str, dry_run: bool) -> int:
    """Import QB vendor expenses as receipts"""
    cols = get_columns(cur, 'receipts')
    
    # Map CSV columns to DB columns
    col_map = {
        'receipt_date': 'receipt_date' if 'receipt_date' in cols else 'date',
        'vendor_name': 'vendor_name' if 'vendor_name' in cols else 'vendor',
        'gross_amount': 'gross_amount' if 'gross_amount' in cols else 'amount',
        'gst_amount': 'gst_amount' if 'gst_amount' in cols else 'tax_amount',
    }
    
    inserted = 0
    skipped = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Compute hash for dedup
            source_hash = compute_hash(
                'QB_RECONCILIATION',
                date=row['receipt_date'],
                vendor=row['vendor_name'],
                gross=row['gross_amount'],
                gst=row['gst_amount']
            )
            
            # Check if exists
            cur.execute("""
                SELECT COUNT(*) FROM receipts 
                WHERE source_hash = %s
            """, (source_hash,))
            if cur.fetchone()[0] > 0:
                skipped += 1
                continue
            
            # Build insert (skip net_amount if generated)
            insert_cols = [col_map['receipt_date'], col_map['vendor_name'], 'category',
                          col_map['gross_amount'], col_map['gst_amount'], 
                          'description', 'source_hash', 'source_system', 'tax_rate', 'is_taxable']
            
            # Check if net_amount is NOT generated
            cur.execute("""
                SELECT is_generated 
                FROM information_schema.columns 
                WHERE table_name='receipts' AND column_name='net_amount'
            """)
            net_result = cur.fetchone()
            if net_result and net_result[0] != 'ALWAYS':
                insert_cols.append('net_amount')
            
            values = [
                row['receipt_date'],
                row['vendor_name'],
                row['category'],
                row['gross_amount'],
                row['gst_amount'],
                row['description'],
                source_hash,
                'QB_RECONCILIATION',
                '0.05',
                True
            ]
            
            if net_result and net_result[0] != 'ALWAYS':
                values.append(row['net_amount'])
            
            if not dry_run:
                placeholders = ','.join(['%s'] * len(insert_cols))
                cur.execute(f"""
                    INSERT INTO receipts ({','.join(insert_cols)})
                    VALUES ({placeholders})
                    RETURNING receipt_id
                """, values)
            else:
                inserted += 1
    
    return inserted, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--write', action='store_true', help='Apply changes (default: dry-run)')
    args = ap.parse_args()
    
    dry_run = not args.write
    base_dir = f'exports/qb/{args.year}'
    
    banking_csv = os.path.join(base_dir, 'qb_banking_transactions.csv')
    receipts_csv = os.path.join(base_dir, 'qb_receipts.csv')
    
    if not os.path.exists(banking_csv):
        print(f'[FAIL] Banking CSV not found: {banking_csv}')
        print('   Run parse_qb_reconciliation.py first')
        return 1
    
    if not os.path.exists(receipts_csv):
        print(f'[FAIL] Receipts CSV not found: {receipts_csv}')
        return 1
    
    print(f'{"🔍 DRY-RUN MODE" if dry_run else "✍️ WRITE MODE"}')
    print(f'📁 Importing QB data for {args.year}')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Import banking
        print(f'\n📊 Banking transactions from: {banking_csv}')
        b_inserted, b_skipped = import_banking_transactions(cur, banking_csv, dry_run)
        print(f'   [OK] Would insert: {b_inserted}' if dry_run else f'   [OK] Inserted: {b_inserted}')
        print(f'   ⏭️  Skipped (duplicates): {b_skipped}')
        
        # Import receipts
        print(f'\n📝 Receipts from: {receipts_csv}')
        r_inserted, r_skipped = import_receipts(cur, receipts_csv, dry_run)
        print(f'   [OK] Would insert: {r_inserted}' if dry_run else f'   [OK] Inserted: {r_inserted}')
        print(f'   ⏭️  Skipped (duplicates): {r_skipped}')
        
        if not dry_run:
            conn.commit()
            print('\n[OK] Import complete')
        else:
            print('\n💡 Dry-run complete. Add --write to apply changes.')
        
    except Exception as e:
        print(f'\n[FAIL] Error: {e}')
        if not dry_run:
            conn.rollback()
        return 1
    finally:
        cur.close()
        conn.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
