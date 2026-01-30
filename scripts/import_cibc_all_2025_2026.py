#!/usr/bin/env python3
"""
CIBC Banking Import - Import all 3 accounts including historical 2025 data
- Handles 3 CIBC accounts with both current (Jan 2026) and historical (2025) files
- Account 0228362: cibc8362.csv + cibc 8362 2025.csv
- Account 8314462: cibc4462.csv + cibc 4462 2025.csv  
- Account 3648117: cibc8117.csv (only has current data)
- Deduplicates transactions (skip if already exists by date+description+amount)
- Creates receipts with GL coding via fuzzy matching
- Idempotent: Only imports NEW transactions
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple, List
import csv
import hashlib

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Load environment
load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DRY_RUN = "--dry-run" in sys.argv
WRITE = "--write" in sys.argv

# CIBC Account mappings - both current and historical files
CIBC_ACCOUNTS = {
    "0228362": {
        "name": "CIBC Checking Account",
        "files": [
            r"l:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc8362.csv",
            r"l:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2025.csv",
        ],
        "bank_id": 1,
        "type": "checking"
    },
    "3648117": {
        "name": "CIBC Business Deposit Account",
        "files": [
            r"l:\limo\CIBC UPLOADS\3648117 (CIBC Business Deposit account, alias for 0534\cibc8117.csv",
        ],
        "bank_id": 1,
        "type": "savings"
    },
    "8314462": {
        "name": "CIBC Vehicle Loans Account",
        "files": [
            r"l:\limo\CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc4462.csv",
            r"l:\limo\CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 2025.csv",
        ],
        "bank_id": 1,
        "type": "loan"
    }
}

# GL Code/Vendor matching rules (fuzzy matching)
GL_MAPPING = {
    "FUEL": ["GAS", "PETRO", "SHELL", "ESSO", "HUSKY", "FAS GAS", "DIESEL", "BULK", "FUEL"],
    "HEFFNER": ["HEFFNER", "AUTO", "VEHICLE MAINTENANCE"],
    "PAYROLL": ["PAYROLL", "SALARY", "WAGES", "EMPLOYEE PAYMENT"],
    "E-TRANSFER": ["E-TRANSFER", "EMT", "INTERAC", "MONEY TRANSFER"],
    "ATM_CASH": ["ATM", "WITHDRAWAL", "CASH"],
    "BANKING_FEES": ["FEE", "SERVICE CHARGE", "NSF", "OVERDRAFT", "PREAUTHORIZED DEBIT"],
    "DEPOSITS": ["DEPOSIT", "CASH DEP", "CHECK", "CHEQUE"],
    "SQUARE": ["SQUARE", "SQ *"],
    "INTERNET_TRANSFER": ["INTERNET TRANSFER"],
}

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def generate_transaction_hash(date_str: str, description: str, amount: str) -> str:
    """Generate unique hash to detect duplicates."""
    combined = f"{date_str}|{description}|{amount}"
    return hashlib.md5(combined.encode()).hexdigest()

def fuzzy_categorize(description: str) -> str:
    """Fuzzy match description to GL code."""
    desc_upper = description.upper()
    
    for gl_code, keywords in GL_MAPPING.items():
        for keyword in keywords:
            if keyword in desc_upper:
                return gl_code
    
    return "UNCATEGORIZED"

def parse_cibc_transaction(date_str: str, description: str, debit: str, credit: str) -> Optional[Tuple[str, str, Decimal, str]]:
    """
    Parse CIBC CSV row format: Date, Description, Debit, Credit
    Returns: (date_str, description, amount_decimal, txn_type) or None if invalid
    """
    try:
        # Validate and clean inputs
        date_str = date_str.strip()
        description = description.strip()
        debit = debit.strip()
        credit = credit.strip()
        
        if not date_str or not description:
            return None
        
        # Validate date format (YYYY-MM-DD)
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None
        
        # Parse amounts
        amount = None
        txn_type = None
        
        if debit:
            try:
                amount = Decimal(debit)
                txn_type = "expense"
            except:
                pass
        
        if not amount and credit:
            try:
                amount = Decimal(credit)
                txn_type = "deposit"
            except:
                pass
        
        if not amount or amount == 0:
            return None
        
        return (date_str, description, amount, txn_type)
    except Exception as e:
        return None

def import_cibc_files(cur, account_id: str, account_info: dict) -> Tuple[int, int]:
    """
    Import transactions from one CIBC account (may have multiple CSV files).
    Returns: (imported_count, skipped_count)
    """
    print(f"\nProcessing {account_info['name']} ({account_id})")
    
    total_imported = 0
    total_skipped = 0
    
    for csv_path in account_info["files"]:
        print(f"   File: {Path(csv_path).name}")
        
        if not os.path.exists(csv_path):
            print(f"   ERROR: File not found!")
            continue
        
        imported = 0
        skipped = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                for row_num, row in enumerate(reader, 1):
                    # Skip empty rows or rows with wrong column count
                    if not row or len(row) < 4:
                        continue
                    
                    # CIBC format: Date, Description, Debit, Credit
                    date_str, description, debit, credit = row[0], row[1], row[2], row[3]
                    
                    parsed = parse_cibc_transaction(date_str, description, debit, credit)
                    if not parsed:
                        continue
                    
                    date_str, description, amount, txn_type = parsed
                    
                    # Check if transaction already exists
                    txn_hash = generate_transaction_hash(date_str, description, str(amount))
                    
                    cur.execute("""
                        SELECT transaction_id FROM banking_transactions 
                        WHERE account_number = %s
                          AND transaction_date = %s 
                          AND description = %s 
                          AND (ABS(debit_amount - %s) < 0.01 OR ABS(credit_amount - %s) < 0.01)
                        LIMIT 1
                    """, (account_id, date_str, description, float(amount), float(amount)))
                    
                    if cur.fetchone():
                        skipped += 1
                        continue
                    
                    # Insert new banking transaction
                    if WRITE and not DRY_RUN:
                        try:
                            if txn_type == "expense":
                                cur.execute("""
                                    INSERT INTO banking_transactions 
                                    (account_number, transaction_date, description, debit_amount, 
                                     bank_id, source_hash, category)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    account_id,
                                    date_str,
                                    description,
                                    float(amount),
                                    account_info["bank_id"],
                                    txn_hash,
                                    fuzzy_categorize(description)
                                ))
                            else:  # deposit
                                cur.execute("""
                                    INSERT INTO banking_transactions 
                                    (account_number, transaction_date, description, credit_amount,
                                     bank_id, source_hash, category)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    account_id,
                                    date_str,
                                    description,
                                    float(amount),
                                    account_info["bank_id"],
                                    txn_hash,
                                    fuzzy_categorize(description)
                                ))
                            imported += 1
                            
                            # Create corresponding receipt with GL coding
                            gl_code = fuzzy_categorize(description)
                            
                            # Insert receipt
                            cur.execute("""
                                INSERT INTO receipts 
                                (receipt_date, vendor_name, expense, expense_account, created_from_banking, description)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (
                                date_str,
                                description[:60],
                                float(amount) if txn_type == "expense" else 0,
                                gl_code,
                                True,
                                f"CIBC {account_id} | {gl_code}"
                            ))
                        except Exception as e:
                            print(f"   WARNING: Error importing {date_str} {description}: {e}")
                            imported = imported  # Don't count failed imports
                    elif DRY_RUN:
                        imported += 1
                        gl_code = fuzzy_categorize(description)
                        if row_num <= 5 or row_num > 998:  # Show first 5 and last few
                            print(f"      {date_str} | {description[:40]:40s} | ${amount:8.2f} | {gl_code}")
        
        except Exception as e:
            print(f"   ERROR: Error reading CSV: {e}")
        
        total_imported += imported
        total_skipped += skipped
        print(f"   [STATS] Imported: {imported} | Skipped (duplicates): {skipped}")
    
    return total_imported, total_skipped

def generate_import_summary(cur):
    """Generate summary of what was imported."""
    print("\n=== IMPORT SUMMARY ===")
    
    cur.execute("""
        SELECT COUNT(*) as banking_txn_count, 
               COALESCE(SUM(debit_amount), 0) as total_debit,
               COALESCE(SUM(credit_amount), 0) as total_credit
        FROM banking_transactions
        WHERE transaction_date >= '2025-10-01'
    """)
    result = cur.fetchone()
    if result:
        count, debit, credit = result
        print(f"[OK] Banking transactions: {count} (Debit: ${debit:.2f}, Credit: ${credit:.2f})")
    
    cur.execute("""
        SELECT COUNT(*) as receipt_count, SUM(COALESCE(expense, 0)) as total_expense
        FROM receipts
        WHERE created_from_banking = true
          AND receipt_date >= '2025-10-01'
    """)
    result = cur.fetchone()
    if result:
        count, total = result
        print(f"[OK] Receipts from banking: {count} (Expenses: ${total:.2f})")

if __name__ == "__main__":
    print("CIBC BANKING IMPORT - 3 ACCOUNTS (Oct 2025 - Jan 2026)")
    print(f"Mode: {'DRY-RUN' if DRY_RUN else 'WRITE' if WRITE else 'REPORT ONLY'}")
    
    total_imported = 0
    total_skipped = 0
    
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            for account_id, account_info in CIBC_ACCOUNTS.items():
                imported, skipped = import_cibc_files(cur, account_id, account_info)
                total_imported += imported
                total_skipped += skipped
            
            if WRITE and not DRY_RUN:
                conn.commit()
                print(f"\n[SUCCESS] COMMITTED {total_imported} new transactions")
            elif DRY_RUN:
                print(f"\n[DRY-RUN] Would import {total_imported} new transactions")
                print(f"[DRY-RUN] Would skip {total_skipped} duplicate transactions")
            else:
                conn.rollback()
            
            generate_import_summary(cur)
    
    if DRY_RUN:
        print("\n[WARNING] DRY-RUN MODE: No changes written to database")
        print("Run with --write flag to apply changes")
    elif WRITE:
        print("\n[SUCCESS] IMPORT COMPLETE")
    else:
        print("\n[INFO] Use --dry-run to preview or --write to apply changes")
