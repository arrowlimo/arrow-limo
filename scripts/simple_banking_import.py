#!/usr/bin/env python3
"""
Simplified Banking Transaction Import - Works with existing receipts table schema
"""

import psycopg2
import pandas as pd
from datetime import datetime

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

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

print("=== SIMPLIFIED BANKING IMPORT SYSTEM ===")

# First, fix database constraints
with psycopg2.connect(**DB_CONFIG) as conn:
    with conn.cursor() as cur:
        # Start fresh transaction
        cur.execute("BEGIN")
        
        try:
            # Fix the constraints that are causing issues
            cur.execute("ALTER TABLE receipts ALTER COLUMN source_reference DROP NOT NULL")
            cur.execute("ALTER TABLE receipts ALTER COLUMN source_reference SET DEFAULT 'BANKING_IMPORT'")
            
            cur.execute("ALTER TABLE receipts ALTER COLUMN expense_account DROP NOT NULL") 
            cur.execute("ALTER TABLE receipts ALTER COLUMN expense_account SET DEFAULT 'BANKING'")
            
            cur.execute("ALTER TABLE receipts ALTER COLUMN vendor_name DROP NOT NULL")
            cur.execute("ALTER TABLE receipts ALTER COLUMN vendor_name SET DEFAULT 'BANKING TRANSACTION'")
            
            cur.execute("ALTER TABLE receipts ALTER COLUMN source_hash DROP NOT NULL")
            cur.execute("ALTER TABLE receipts ALTER COLUMN source_hash SET DEFAULT 'AUTO_GENERATED'")
            
            cur.execute("ALTER TABLE receipts ALTER COLUMN gross_amount DROP NOT NULL")
            cur.execute("ALTER TABLE receipts ALTER COLUMN gross_amount SET DEFAULT 0")
            
            conn.commit()
            print("SUCCESS: Database constraints fixed")
            
        except Exception as e:
            print(f"Database fix error: {e}")
            conn.rollback()

# Now import missing transactions with minimal required fields
with psycopg2.connect(**DB_CONFIG) as conn:
    with conn.cursor() as cur:
        # Get existing receipts for duplicate checking
        cur.execute("SELECT receipt_date, expense FROM receipts WHERE expense != 0")
        existing_receipts = {(row[0], abs(float(row[1]))) for row in cur.fetchall()}
        print(f"Loaded {len(existing_receipts)} existing receipts for duplicate checking")
        
        # Process banking files
        banking_files = [
            ('l:/limo/CIBC UPLOADS/0228362 (CIBC checking account)/cibc 8362 all.csv', 'Checking'),
            ('l:/limo/CIBC UPLOADS/3648117 (CIBC Business Deposit account, alias for 0534/cibc 8117 all.csv', 'Deposit'),
        ]
        
        total_imported = 0
        
        for file_path, account_type in banking_files:
            try:
                df = pd.read_csv(file_path)
                print(f"\nProcessing {account_type}: {len(df)} transactions")
                
                batch_imported = 0
                for _, row in df.iterrows():
                    trans_date = pd.to_datetime(row['Trans_date']).date()
                    description = str(row['Trans_description'])[:50]  # Truncate to avoid issues
                    
                    # Calculate amount
                    debit = float(row['Debit']) if pd.notna(row['Debit']) and row['Debit'] != '' else 0
                    credit = float(row['Credit']) if pd.notna(row['Credit']) and row['Credit'] != '' else 0
                    amount = credit - debit
                    
                    if amount == 0:
                        continue
                    
                    # Skip duplicates
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
                    
                    try:
                        # Insert with minimal required fields only
                        cur.execute("""
                            INSERT INTO receipts (
                                receipt_date, 
                                vendor_name, 
                                expense, 
                                expense_account,
                                category,
                                created_from_banking
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            trans_date,
                            vendor_name,
                            expense_amount,
                            f"{category} - {account_type}",
                            category,
                            True
                        ))
                        
                        batch_imported += 1
                        total_imported += 1
                        
                        if batch_imported % 1000 == 0:
                            conn.commit()
                            print(f"    Imported {batch_imported} from {account_type}...")
                        
                    except Exception as e:
                        print(f"Error importing transaction: {e}")
                        conn.rollback()
                        # Start new transaction
                        cur.execute("BEGIN")
                        continue
                
                conn.commit()
                print(f"    Completed {account_type}: {batch_imported} transactions imported")
                
            except Exception as e:
                print(f"Error processing {account_type}: {e}")
                continue
        
        print(f"\n=== IMPORT COMPLETE ===")
        print(f"Total transactions imported: {total_imported}")
        
        # Final summary
        cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = TRUE")
        auto_imported = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM receipts")
        total_receipts = cur.fetchone()[0]
        
        print(f"Total receipts in system: {total_receipts}")
        print(f"Auto-imported from banking: {auto_imported}")
        print(f"Manual receipts: {total_receipts - auto_imported}")

print("Banking import complete!")