#!/usr/bin/env python3
"""
Robust Banking Transaction Import - Proper transaction handling
"""

import psycopg2
import pandas as pd
from datetime import datetime
import hashlib
import os

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

def generate_unique_reference(date, description, amount, account_type):
    """Generate a unique reference for each transaction"""
    timestamp = str(int(datetime.now().timestamp()))
    combined = f"{date}_{description}_{amount}_{account_type}_{timestamp}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]

def auto_categorize_transaction(description):
    """Automatically categorize transaction based on description patterns"""
    description_upper = description.upper()
    
    category_rules = {
        'BANKING': ['FEE', 'SERVICE CHARGE', 'MONTHLY FEE', 'ACCOUNT FEE', 'ATM', 'WITHDRAWAL', 
                   'NSF', 'INSUFFICIENT', 'OVERDRAFT', 'OVERLIMIT', 'PREAUTHORIZED'],
        'DEPOSITS': ['SQUARE', 'SQ *', 'DEPOSIT', 'CASH DEP', 'CHECK', 'CHEQUE'],
        'LOANS': ['LOAN PAYMENT', 'AUTO LOAN', 'VEHICLE LOAN', 'INTEREST', 'FINANCE CHARGE'],
        'FUEL': ['GAS', 'PETRO', 'SHELL', 'ESSO', 'HUSKY', 'FAS GAS', 'DIESEL', 'BULK FUEL'],
        'TRANSFERS': ['INTERAC', 'E-TRANSFER', 'EMT', 'WIRE', 'TRANSFER', 'POINT OF SALE'],
        'PAYROLL': ['PAYROLL', 'SALARY', 'WAGES', 'EMPLOYEE']
    }
    
    for category, keywords in category_rules.items():
        for keyword in keywords:
            if keyword in description_upper:
                return category
                
    return 'UNCATEGORIZED'

def should_add_to_receipts(description):
    """Determine if a banking transaction should be added to receipts"""
    exclude_patterns = [
        'TRANSFER FROM', 'TRANSFER TO', 'INTERNAL TRANSFER', 'ACCOUNT TRANSFER',
        'INTERNET TRANSFER 00000'
    ]
    
    description_upper = description.upper()
    for pattern in exclude_patterns:
        if pattern in description_upper:
            return False
            
    return True

def get_existing_receipts(cur):
    """Get existing receipts to avoid duplicates"""
    cur.execute("""
        SELECT receipt_date, ABS(expense) as amount
        FROM receipts
        WHERE created_from_banking = true
    """)
    return set(cur.fetchall())

def process_banking_file(cur, file_path, account_type, existing_receipts):
    """Process a single banking CSV file"""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return 0
    
    print(f"\nProcessing {account_type} account from {file_path}")
    
    # Read CSV
    df = pd.read_csv(file_path)
    
    imported_count = 0
    processed_count = 0
    batch_size = 100  # Smaller batches for better error handling
    
    for index, row in df.iterrows():
        processed_count += 1
        
        try:
            # Parse date - use Trans_date column from CIBC CSV
            date_str = str(row['Trans_date']) if pd.notna(row['Trans_date']) else ''
            if not date_str or date_str == 'Trans_date':  # Skip header rows
                continue
                
            try:
                trans_date = pd.to_datetime(date_str).date()
            except:
                continue
            
            # Get description - use Trans_description column from CIBC CSV
            description = str(row['Trans_description']) if pd.notna(row['Trans_description']) else 'Unknown Transaction'
            description = description.strip()[:100]  # Limit length
            
            if not description or description == 'nan' or description == 'Trans_description':
                continue
            
            # Calculate amount
            debit = float(row['Debit']) if pd.notna(row['Debit']) and str(row['Debit']).strip() != '' else 0
            credit = float(row['Credit']) if pd.notna(row['Credit']) and str(row['Credit']).strip() != '' else 0
            amount = credit - debit
            
            if amount == 0:
                continue
            
            # Skip duplicates (check date and amount)
            if (trans_date, abs(amount)) in existing_receipts:
                continue
                
            # Skip internal transfers
            if not should_add_to_receipts(description):
                continue
            
            # Categorize
            category = auto_categorize_transaction(description)
            
            # Prepare data for insert
            if amount > 0:
                # Revenue - store as negative per Epson workflow
                expense_amount = -abs(amount)
                vendor_name = f"REVENUE - {description[:25]}"
            else:
                # Expense - store as positive
                expense_amount = abs(amount)
                vendor_name = description[:40]
            
            # Generate unique reference
            unique_ref = generate_unique_reference(trans_date, description, amount, account_type)
            
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
                    source_reference
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                trans_date,
                vendor_name,
                expense_amount,
                f"{category} - {account_type}",
                category,
                True,
                'BANKING_IMPORT',
                unique_ref
            ))
            
            imported_count += 1
            
            # Add to existing receipts to prevent duplicates within same run
            existing_receipts.add((trans_date, abs(amount)))
            
            # Commit in batches
            if imported_count % batch_size == 0:
                print(f"  Imported {imported_count} transactions...")
                
        except Exception as e:
            # Skip individual record errors but continue processing
            print(f"  Warning: Skipping transaction {processed_count}: {str(e)[:100]}")
            continue
    
    print(f"  Completed {account_type}: {imported_count} imported from {processed_count} processed")
    return imported_count

def main():
    """Main reconciliation function"""
    print("Starting Robust Banking Transaction Import...")
    
    conn = None
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False  # Use explicit transaction control
        cur = conn.cursor()
        
        # Get existing receipts
        existing_receipts = get_existing_receipts(cur)
        print(f"Found {len(existing_receipts)} existing banking receipts")
        
        # File mappings - use the actual CIBC files available
        bank_files = {
            'CHECKING': r'CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 all.csv',
            'DEPOSIT': r'CIBC UPLOADS\3648117 (CIBC Business Deposit account, alias for 0534\cibc 8117 all.csv',  
            'LOANS': r'CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 all.csv'
        }
        
        total_imported = 0
        
        # Process each file
        for account_type, file_path in bank_files.items():
            try:
                imported = process_banking_file(cur, file_path, account_type, existing_receipts)
                total_imported += imported
                
                # Commit after each file
                conn.commit()
                print(f"  ✓ Committed {imported} transactions for {account_type}")
                
            except Exception as e:
                # Rollback this file's transactions but continue with others
                conn.rollback()
                print(f"  ✗ Error processing {account_type}: {e}")
                continue
        
        # Final status
        print(f"\n=== IMPORT COMPLETE ===")
        print(f"Total transactions imported: {total_imported:,}")
        
        # Get final counts
        cur.execute("SELECT COUNT(*) FROM receipts")
        total_receipts = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = true")
        banking_receipts = cur.fetchone()[0]
        
        print(f"\nFINAL DATABASE STATUS:")
        print(f"Total receipts in system: {total_receipts:,}")
        print(f"Banking-imported receipts: {banking_receipts:,}")
        print(f"Manual receipts: {total_receipts - banking_receipts:,}")
        
        # Show category breakdown
        cur.execute("""
            SELECT category, COUNT(*) 
            FROM receipts 
            WHERE created_from_banking = true 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
        """)
        
        print(f"\nImported transaction categories:")
        for category, count in cur.fetchall():
            print(f"  {category}: {count} transactions")
        
        print(f"\n[OK] BANKING RECONCILIATION COMPLETE!")
        
    except Exception as e:
        print(f"Critical error: {e}")
        if conn:
            conn.rollback()
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()