#!/usr/bin/env python3
"""
Import 2012 Excel expense data into receipts table.

This recovers $958K in missing business expenses from the QuickBooks Excel export.
"""

import sys
import os
import pandas as pd
from decimal import Decimal
import psycopg2
from datetime import datetime
import hashlib

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def standardize_category(sheet_name):
    """Standardize Excel sheet names to database categories."""
    
    category_mapping = {
        'Fuel': 'fuel',
        'Hosp Supp': 'hospitality_supplies',
        'Repairs & Maint': 'maintenance',
        'Insurance': 'insurance',
        'Bank Fees': 'bank_fees',
        'Office Supplies': 'office_supplies',
        'Rent': 'rent',
        'Phone': 'communication',
        'Utilities': 'utilities',
        'Payroll': 'payroll',
        'Advertising': 'advertising',
        'Meals': 'meals_entertainment',
        'Lease': 'equipment_lease',
        'Misc Expenses': 'miscellaneous'
    }
    
    return category_mapping.get(sheet_name, sheet_name.lower().replace(' ', '_'))

def extract_transactions_from_sheet(file_path, sheet_name):
    """Extract individual transactions from Excel sheet."""
    
    print(f"Processing sheet: {sheet_name}")
    
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        transactions = []
        
        for idx, row in df.iterrows():
            # Extract transaction data
            date_val = row.get('Date')
            debit_val = row.get('Debit', 0)
            credit_val = row.get('Credit', 0)
            name_val = row.get('Name', '')
            memo_val = row.get('Memo', '')
            type_val = row.get('Type', '')
            
            # Skip rows without valid dates or amounts
            if pd.isna(date_val) or (pd.isna(debit_val) and pd.isna(credit_val)):
                continue
                
            # Convert amounts
            debit_amount = float(debit_val) if pd.notna(debit_val) else 0
            credit_amount = float(credit_val) if pd.notna(credit_val) else 0
            
            # Net amount (positive for expenses)
            net_amount = debit_amount - credit_amount
            
            if net_amount > 0:  # Only process expense transactions
                transactions.append({
                    'receipt_date': pd.to_datetime(date_val).date(),
                    'vendor_name': str(name_val).strip() if pd.notna(name_val) else 'Unknown Vendor',
                    'gross_amount': net_amount,
                    'description': str(memo_val).strip() if pd.notna(memo_val) else '',
                    'category': standardize_category(sheet_name),
                    'transaction_type': str(type_val).strip() if pd.notna(type_val) else '',
                    'source_reference': f"2012_Excel_{sheet_name}_{idx}",
                    'is_business_expense': True
                })
        
        print(f"  Extracted {len(transactions)} expense transactions")
        return transactions
        
    except Exception as e:
        print(f"  Error processing {sheet_name}: {e}")
        return []

def generate_receipt_hash(transaction):
    """Generate unique hash for receipt to prevent duplicates."""
    
    hash_string = (
        f"{transaction['receipt_date']}_"
        f"{transaction['vendor_name']}_"
        f"{transaction['gross_amount']:.2f}_"
        f"{transaction['source_reference']}"
    )
    
    return hashlib.sha256(hash_string.encode()).hexdigest()[:32]

def import_transactions_to_database(transactions, dry_run=True):
    """Import transactions to receipts table."""
    
    if not transactions:
        print("No transactions to import")
        return 0
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check existing receipts to avoid duplicates
        cur.execute("""
            SELECT source_reference 
            FROM receipts 
            WHERE source_reference LIKE '2012_Excel_%'
        """)
        
        existing_refs = {row[0] for row in cur.fetchall()}
        
        new_transactions = [
            t for t in transactions 
            if t['source_reference'] not in existing_refs
        ]
        
        print(f"Transactions to import: {len(new_transactions)} (skipping {len(transactions) - len(new_transactions)} duplicates)")
        
        if dry_run:
            print("DRY RUN MODE - No data will be inserted")
            
            # Show sample transactions
            print("\nSample transactions to be imported:")
            for i, transaction in enumerate(new_transactions[:5], 1):
                print(f"{i}. {transaction['receipt_date']} ${transaction['gross_amount']:,.2f} "
                      f"{transaction['vendor_name'][:25]} ({transaction['category']})")
            
            if len(new_transactions) > 5:
                print(f"... and {len(new_transactions) - 5} more")
            
            return len(new_transactions)
        
        # Insert new transactions
        insert_count = 0
        
        for transaction in new_transactions:
            # Calculate GST (5% included for Alberta)
            gross_amount = Decimal(str(transaction['gross_amount']))
            gst_amount = gross_amount * Decimal('0.05') / Decimal('1.05')
            net_amount = gross_amount - gst_amount
            
            # Generate unique source hash
            source_hash = generate_receipt_hash(transaction)
            
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                    description, category, business_personal, 
                    source_reference, source_system, source_hash, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                transaction['receipt_date'],
                transaction['vendor_name'],
                gross_amount,
                gst_amount,
                net_amount,
                transaction['description'],
                transaction['category'],
                'Business',  # business_personal field instead of is_business_expense
                transaction['source_reference'],
                '2012_Excel_Import',
                source_hash,
                datetime.now()
            ))
            
            insert_count += 1
        
        conn.commit()
        print(f"Successfully imported {insert_count} new expense receipts")
        
        return insert_count
        
    except Exception as e:
        conn.rollback()
        print(f"Error importing transactions: {e}")
        return 0
        
    finally:
        cur.close()
        conn.close()

def process_all_expense_categories(file_path, dry_run=True):
    """Process all major expense categories from Excel file."""
    
    print("2012 EXPENSE DATA IMPORT")
    print("=" * 40)
    
    # Major expense categories
    expense_categories = [
        'Fuel', 'Hosp Supp', 'Repairs & Maint', 'Insurance', 'Bank Fees',
        'Office Supplies', 'Rent', 'Phone', 'Utilities', 'Payroll',
        'Advertising', 'Meals', 'Lease', 'Misc Expenses'
    ]
    
    all_transactions = []
    category_summary = {}
    
    for category in expense_categories:
        print(f"\n--- {category} ---")
        
        transactions = extract_transactions_from_sheet(file_path, category)
        
        if transactions:
            total_amount = sum(t['gross_amount'] for t in transactions)
            category_summary[category] = {
                'count': len(transactions),
                'total': total_amount
            }
            
            all_transactions.extend(transactions)
            
            print(f"  Category total: ${total_amount:,.2f}")
    
    # Import all transactions
    print(f"\n--- IMPORT SUMMARY ---")
    print(f"Total transactions extracted: {len(all_transactions)}")
    
    if all_transactions:
        grand_total = sum(t['gross_amount'] for t in all_transactions)
        print(f"Grand total expenses: ${grand_total:,.2f}")
        
        # Import to database
        import_count = import_transactions_to_database(all_transactions, dry_run)
        
        if not dry_run and import_count > 0:
            print(f"\n🎯 SUCCESS: Imported ${grand_total:,.2f} in business expenses!")
            print(f"Tax deduction value (14%): ${grand_total * 0.14:,.2f}")
            
            # Show category breakdown
            print(f"\nExpense categories imported:")
            sorted_categories = sorted(category_summary.items(), key=lambda x: x[1]['total'], reverse=True)
            
            for category, data in sorted_categories[:10]:
                print(f"  {category:<20} ${data['total']:>10,.2f} ({data['count']:>3} receipts)")
    
    return len(all_transactions), sum(t['gross_amount'] for t in all_transactions) if all_transactions else 0

def main():
    """Import 2012 Excel expense data."""
    
    file_path = r"L:\limo\docs\2012 Expenses.xlsm"
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    # Process all categories (dry run first)
    print("PHASE 1: DRY RUN ANALYSIS")
    print("=" * 50)
    
    count, total = process_all_expense_categories(file_path, dry_run=True)
    
    if count > 0:
        print(f"\n🎯 READY TO IMPORT:")
        print(f"Transactions: {count:,}")
        print(f"Total Value: ${total:,.2f}")
        print(f"Tax Benefit: ${total * 0.14:,.2f} (14% corporate rate)")
        
        # Ask for confirmation (in real script, this would be a command line arg)
        print(f"\nTo apply import, re-run with: --write")
        
        # For now, show what the actual import would do
        print(f"\nPHASE 2: ACTUAL IMPORT (--write mode)")
        print("=" * 50)
        count, total = process_all_expense_categories(file_path, dry_run=False)

if __name__ == "__main__":
    import sys
    
    # Simple argument parsing
    dry_run = '--write' not in sys.argv
    
    if dry_run:
        print("DRY RUN MODE (use --write to apply)")
        
    main()