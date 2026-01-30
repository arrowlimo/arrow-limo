#!/usr/bin/env python3
"""
Individual Banking Import - Handles each transaction separately to avoid transaction blocks
"""

import psycopg2
from psycopg2 import sql
import pandas as pd
from datetime import datetime
import hashlib
import os

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres', 
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

def generate_unique_reference(date_str, description, amount, account):
    """Generate a unique reference for each transaction"""
    timestamp = str(int(datetime.now().timestamp() * 1000000))  # microsecond precision
    combined = f"{date_str}_{description}_{amount}_{account}_{timestamp}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]

def auto_categorize_transaction(description):
    """Categorize based on description keywords"""
    desc = description.upper()
    
    if any(word in desc for word in ['ATM', 'WITHDRAWAL', 'FEE', 'SERVICE CHARGE', 'NSF', 'OVERDRAFT']):
        return 'BANKING'
    elif any(word in desc for word in ['SQUARE', 'SQ *', 'DEPOSIT', 'CASH']):
        return 'DEPOSITS'  
    elif any(word in desc for word in ['LOAN', 'HEFFNER', 'INTEREST']):
        return 'LOANS'
    elif any(word in desc for word in ['GAS', 'FUEL', 'PETRO', 'SHELL', 'ESSO', 'HUSKY', 'FAS GAS']):
        return 'FUEL'
    elif any(word in desc for word in ['E-TRANSFER', 'INTERAC', 'EMT', 'TRANSFER']):
        return 'TRANSFERS'
    else:
        return 'UNCATEGORIZED'

def insert_single_transaction(date_str, description, amount, account_type):
    """Insert a single transaction with individual error handling"""
    try:
        # Connect fresh for each transaction to avoid transaction block issues
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Parse date
        trans_date = pd.to_datetime(date_str).date()
        
        # Skip zero amounts  
        if abs(amount) < 0.01:
            conn.close()
            return False, "Zero amount"
            
        # Skip internal transfers
        if any(word in description.upper() for word in ['INTERNET TRANSFER 00000', 'INTERNAL TRANSFER']):
            conn.close()
            return False, "Internal transfer"
            
        # Categorize
        category = auto_categorize_transaction(description)
        
        # Prepare vendor name and amount per Epson workflow
        if amount > 0:
            # Revenue - negative amount for Epson  
            expense_amount = -abs(amount)
            vendor_name = f"REVENUE - {description[:25]}"
        else:
            # Expense - positive amount
            expense_amount = abs(amount)
            vendor_name = description[:40]
            
        # Generate unique reference
        unique_ref = generate_unique_reference(date_str, description, amount, account_type)
        
        # Insert record
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name, 
                expense,
                expense_account,
                category,
                created_from_banking,
                source_system,
                source_reference,
                source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            trans_date,
            vendor_name,
            expense_amount, 
            f"{category} - {account_type}",
            category,
            True,
            'BANKING_IMPORT',
            unique_ref,
            unique_ref  # Use same unique_ref for source_hash
        ))
        
        conn.close()
        return True, f"Imported: {vendor_name[:30]}..."
        
    except Exception as e:
        if conn:
            conn.close()
        return False, str(e)[:100]

def main():
    """Process CIBC files with individual transaction handling"""
    print("Starting Individual Banking Import...")
    
    # File paths
    files_to_process = [
        ('CHECKING', r'CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 all.csv'),
        ('DEPOSIT', r'CIBC UPLOADS\3648117 (CIBC Business Deposit account, alias for 0534\cibc 8117 all.csv'),
        ('LOANS', r'CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 all.csv')
    ]
    
    total_imported = 0
    total_processed = 0
    
    for account_type, file_path in files_to_process:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        print(f"\nProcessing {account_type} account...")
        
        # Read CSV
        df = pd.read_csv(file_path)
        file_imported = 0
        file_processed = 0
        
        for index, row in df.iterrows():
            file_processed += 1
            total_processed += 1
            
            try:
                # Get transaction data
                date_str = str(row['Trans_date']).strip()
                description = str(row['Trans_description']).strip()
                debit = float(row['Debit']) if pd.notna(row['Debit']) and str(row['Debit']).strip() else 0
                credit = float(row['Credit']) if pd.notna(row['Credit']) and str(row['Credit']).strip() else 0
                
                # Skip invalid data
                if not date_str or date_str == 'Trans_date' or not description or description == 'Trans_description':
                    continue
                    
                amount = credit - debit
                
                # Try to insert transaction
                success, message = insert_single_transaction(date_str, description, amount, account_type)
                
                if success:
                    file_imported += 1
                    total_imported += 1
                    
                    if file_imported % 100 == 0:
                        print(f"  Imported {file_imported} transactions...")
                else:
                    # Print first 10 failures for debugging
                    if file_processed <= 10:
                        print(f"    Failed row {file_processed}: {message}")
                        
            except Exception as e:
                # Print first 10 processing errors for debugging  
                if file_processed <= 10:
                    print(f"    Error row {file_processed}: {str(e)[:100]}")
                continue
                
        print(f"  {account_type}: {file_imported} imported from {file_processed} processed")
    
    print(f"\n=== IMPORT COMPLETE ===")
    print(f"Total processed: {total_processed:,}")
    print(f"Total imported: {total_imported:,}")
    
    # Get final database status
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM receipts")
        total_receipts = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = true")
        banking_receipts = cur.fetchone()[0]
        
        print(f"\nFINAL DATABASE STATUS:")
        print(f"Total receipts: {total_receipts:,}")
        print(f"Banking receipts: {banking_receipts:,}")
        print(f"Manual receipts: {total_receipts - banking_receipts:,}")
        
        # Show categories
        cur.execute("""
            SELECT category, COUNT(*) 
            FROM receipts 
            WHERE created_from_banking = true 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
        """)
        
        print(f"\nImported categories:")
        for category, count in cur.fetchall():
            print(f"  {category}: {count:,} transactions")
            
        conn.close()
        
    except Exception as e:
        print(f"Error getting final status: {e}")
    
    print(f"\n[OK] BANKING IMPORT COMPLETE!")

if __name__ == "__main__":
    main()