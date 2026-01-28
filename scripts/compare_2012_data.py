#!/usr/bin/env python3
"""
Compare Parsed 2012 Data Against Database
=========================================

Compares parsed PDF data against almsdata to identify:
- Missing banking transactions
- Missing QuickBooks entries
- Discrepancies in amounts or dates

Outputs:
- Missing transactions report
- Reconciliation summary
- Import script for missing data

Safe: Read-only comparison.
"""
from __future__ import annotations

import os
import csv
import sys
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import DictCursor


DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

PARSED_DIR = r"L:\limo\staging\2012_parsed"
OUTPUT_DIR = r"L:\limo\staging\2012_comparison"


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def load_parsed_transactions(csv_path: str) -> list[dict]:
    """Load parsed transactions from CSV"""
    transactions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(row)
    return transactions


def parse_date(date_str: str) -> datetime | None:
    """Parse various date formats"""
    if not date_str:
        return None
    
    formats = [
        "%b %d, %Y",  # Jan 3, 2012
        "%m/%d/%Y",   # 01/03/2012
        "%Y-%m-%d",   # 2012-01-03
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    
    return None


def get_db_transactions(conn, year: int = 2012) -> list[dict]:
    """Get all banking transactions from database for the year"""
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT 
                transaction_id,
                transaction_date,
                description,
                COALESCE(debit_amount, 0) as debit,
                COALESCE(credit_amount, 0) as credit,
                balance
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date
            """,
            (year,),
        )
        return [dict(row) for row in cur.fetchall()]


def normalize_description(desc: str) -> str:
    """Normalize description for comparison"""
    if not desc:
        return ""
    # Remove extra whitespace, convert to uppercase
    return ' '.join(desc.upper().split())


def find_matching_transaction(parsed_tx, db_transactions, tolerance=0.01) -> dict | None:
    """Find a matching transaction in database"""
    parsed_date = parse_date(parsed_tx['date'])
    if not parsed_date:
        return None
    
    parsed_desc = normalize_description(parsed_tx['description'])
    
    # Try to get amount
    parsed_amount = None
    if parsed_tx.get('withdrawal'):
        try:
            parsed_amount = abs(float(parsed_tx['withdrawal']))
        except:
            pass
    elif parsed_tx.get('deposit'):
        try:
            parsed_amount = abs(float(parsed_tx['deposit']))
        except:
            pass
    
    if not parsed_amount:
        return None
    
    # Look for matches within ±1 day and same amount (within tolerance)
    for db_tx in db_transactions:
        db_date = db_tx['transaction_date']
        if not db_date:
            continue
        
        # Check date within 1 day
        date_diff = abs((parsed_date.date() - db_date).days)
        if date_diff > 1:
            continue
        
        # Check amount
        db_amount = float(db_tx['debit']) if db_tx['debit'] > 0 else float(db_tx['credit'])
        if abs(parsed_amount - db_amount) <= tolerance:
            # Check description similarity (optional, for extra confidence)
            db_desc = normalize_description(db_tx['description'])
            if db_desc and parsed_desc:
                # Simple substring check
                if parsed_desc in db_desc or db_desc in parsed_desc:
                    return db_tx
            else:
                # If no description, match on date and amount alone
                return db_tx
    
    return None


def main():
    print("=" * 80)
    print("COMPARING 2012 PARSED DATA AGAINST DATABASE")
    print("=" * 80)
    print()
    
    ensure_dir(OUTPUT_DIR)
    
    # Load parsed data
    cibc_path = os.path.join(PARSED_DIR, '2012_cibc_transactions.csv')
    qb_path = os.path.join(PARSED_DIR, '2012_quickbooks_transactions.csv')
    
    cibc_transactions = load_parsed_transactions(cibc_path)
    qb_transactions = load_parsed_transactions(qb_path)
    
    print(f"📊 Loaded parsed data:")
    print(f"   CIBC transactions: {len(cibc_transactions)}")
    print(f"   QuickBooks transactions: {len(qb_transactions)}")
    
    # Connect to database
    try:
        with psycopg2.connect(**DSN) as conn:
            db_transactions = get_db_transactions(conn, 2012)
            print(f"   Database transactions (2012): {len(db_transactions)}")
            
            # Compare CIBC transactions
            print(f"\n🔍 Comparing CIBC transactions...")
            cibc_missing = []
            cibc_matched = 0
            
            for parsed_tx in cibc_transactions:
                match = find_matching_transaction(parsed_tx, db_transactions)
                if match:
                    cibc_matched += 1
                else:
                    cibc_missing.append(parsed_tx)
            
            print(f"   [OK] Matched: {cibc_matched}")
            print(f"   [FAIL] Missing: {len(cibc_missing)}")
            
            # Compare QuickBooks transactions
            print(f"\n🔍 Comparing QuickBooks transactions...")
            qb_missing = []
            qb_matched = 0
            
            for parsed_tx in qb_transactions:
                match = find_matching_transaction(parsed_tx, db_transactions)
                if match:
                    qb_matched += 1
                else:
                    qb_missing.append(parsed_tx)
            
            print(f"   [OK] Matched: {qb_matched}")
            print(f"   [FAIL] Missing: {len(qb_missing)}")
            
            # Save missing transactions
            if cibc_missing:
                missing_cibc_path = os.path.join(OUTPUT_DIR, 'missing_cibc_transactions.csv')
                with open(missing_cibc_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=cibc_missing[0].keys())
                    writer.writeheader()
                    writer.writerows(cibc_missing)
                print(f"\n💾 Saved missing CIBC transactions: {missing_cibc_path}")
            
            if qb_missing:
                missing_qb_path = os.path.join(OUTPUT_DIR, 'missing_quickbooks_transactions.csv')
                with open(missing_qb_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=qb_missing[0].keys())
                    writer.writeheader()
                    writer.writerows(qb_missing)
                print(f"💾 Saved missing QuickBooks transactions: {missing_qb_path}")
            
            # Generate summary report
            summary_path = os.path.join(OUTPUT_DIR, 'reconciliation_summary.txt')
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("2012 DATA RECONCILIATION SUMMARY\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Database Records (2012):\n")
                f.write(f"  Banking transactions: {len(db_transactions)}\n\n")
                f.write(f"Parsed from PDFs:\n")
                f.write(f"  CIBC statements: {len(cibc_transactions)}\n")
                f.write(f"  QuickBooks reconciliation: {len(qb_transactions)}\n\n")
                f.write(f"Comparison Results:\n")
                f.write(f"  CIBC - Matched: {cibc_matched}, Missing: {len(cibc_missing)}\n")
                f.write(f"  QuickBooks - Matched: {qb_matched}, Missing: {len(qb_missing)}\n\n")
                
                if cibc_missing or qb_missing:
                    f.write(f"Action Required:\n")
                    f.write(f"  - Review missing transaction CSVs\n")
                    f.write(f"  - Run import script to add missing records\n")
                else:
                    f.write(f"Status: [OK] All transactions reconciled!\n")
            
            print(f"\n📋 Saved reconciliation summary: {summary_path}")
            
            print("\n" + "=" * 80)
            print("COMPARISON COMPLETE")
            print("=" * 80)
            
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
