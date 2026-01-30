#!/usr/bin/env python3
"""
Import 2013 Excel expense data - Phase 1 of multi-year recovery.

Following the spectacular success of 2012 ($286K recovered),
this script targets 2013 for similar expense recovery.

Based on: import_2012_excel_expenses.py
"""

import sys
import os
import pandas as pd
from decimal import Decimal
import psycopg2
from datetime import datetime
import hashlib
import glob

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

def find_2013_excel_files():
    """Find all 2013 Excel files for processing."""
    
    docs_path = r"L:\limo\docs"
    excel_files = []
    
    # Search recursively for 2013 Excel files
    for root, dirs, files in os.walk(docs_path):
        for file in files:
            if '2013' in file and file.endswith(('.xlsx', '.xlsm')):  # Skip .xls for now
                full_path = os.path.join(root, file)
                excel_files.append(full_path)
    
    return excel_files

def analyze_file_for_expenses(file_path):
    """Analyze a file to see if it contains expense data."""
    
    print(f"Analyzing: {os.path.basename(file_path)}")
    
    try:
        xl = pd.ExcelFile(file_path)
        sheets = xl.sheet_names
        
        expense_sheets = []
        
        for sheet in sheets:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet, nrows=20)  # Sample first 20 rows
                
                # Look for expense indicators
                has_amounts = False
                has_dates = False
                has_vendors = False
                
                for col in df.columns:
                    col_str = str(col).lower()
                    
                    # Amount columns
                    if any(keyword in col_str for keyword in ['debit', 'credit', 'amount', 'total', 'expense']):
                        series = pd.to_numeric(df[col], errors='coerce')
                        if series.sum() > 1000:  # Significant amounts
                            has_amounts = True
                    
                    # Date columns
                    if any(keyword in col_str for keyword in ['date', 'time']):
                        has_dates = True
                    
                    # Vendor/description columns  
                    if any(keyword in col_str for keyword in ['name', 'vendor', 'payee', 'description', 'memo']):
                        has_vendors = True
                
                # Check if sheet name suggests expenses
                sheet_lower = sheet.lower()
                expense_keywords = ['fuel', 'repair', 'maintenance', 'insurance', 'bank', 'office',
                                 'rent', 'phone', 'utilities', 'payroll', 'advertising', 'meal',
                                 'lease', 'misc', 'expense', 'hosp', 'supplies', 'cost']
                
                is_expense_sheet = any(keyword in sheet_lower for keyword in expense_keywords)
                
                if (has_amounts and (has_dates or has_vendors)) or is_expense_sheet:
                    expense_sheets.append({
                        'sheet': sheet,
                        'has_amounts': has_amounts,
                        'has_dates': has_dates,
                        'has_vendors': has_vendors,
                        'is_expense_category': is_expense_sheet,
                        'rows': len(df)
                    })
            
            except Exception as e:
                continue
        
        if expense_sheets:
            print(f"  Found {len(expense_sheets)} potential expense sheets")
            for sheet_info in expense_sheets[:3]:  # Show first 3
                print(f"    - {sheet_info['sheet']} ({sheet_info['rows']} rows)")
        
        return expense_sheets
        
    except Exception as e:
        print(f"  Error analyzing: {e}")
        return []

def extract_expenses_from_file(file_path, dry_run=True):
    """Extract expense transactions from a 2013 Excel file."""
    
    expense_sheets = analyze_file_for_expenses(file_path)
    
    if not expense_sheets:
        return []
    
    all_transactions = []
    
    for sheet_info in expense_sheets:
        sheet_name = sheet_info['sheet']
        
        try:
            print(f"\nProcessing sheet: {sheet_name}")
            
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            transactions = []
            
            # Find amount and description columns
            amount_col = None
            date_col = None
            vendor_col = None
            desc_col = None
            
            for col in df.columns:
                col_str = str(col).lower()
                
                if 'debit' in col_str and not amount_col:
                    amount_col = col
                elif 'amount' in col_str and not amount_col:
                    amount_col = col
                elif 'date' in col_str and not date_col:
                    date_col = col
                elif any(keyword in col_str for keyword in ['name', 'vendor', 'payee']) and not vendor_col:
                    vendor_col = col
                elif any(keyword in col_str for keyword in ['description', 'memo', 'notes']) and not desc_col:
                    desc_col = col
            
            if not amount_col:
                print(f"  No amount column found in {sheet_name}")
                continue
            
            # Extract transactions
            for idx, row in df.iterrows():
                amount_val = row.get(amount_col, 0)
                
                if pd.isna(amount_val) or amount_val <= 0:
                    continue
                
                # Extract other fields
                date_val = row.get(date_col) if date_col else datetime(2013, 6, 15).date()  # Default mid-year
                vendor_val = row.get(vendor_col, 'Unknown Vendor') if vendor_col else 'Unknown Vendor'
                desc_val = row.get(desc_col, '') if desc_col else ''
                
                # Convert date if needed
                if pd.notna(date_val):
                    try:
                        if hasattr(date_val, 'date'):
                            transaction_date = date_val.date()
                        else:
                            transaction_date = pd.to_datetime(date_val).date()
                    except:
                        transaction_date = datetime(2013, 6, 15).date()
                else:
                    transaction_date = datetime(2013, 6, 15).date()
                
                # Ensure date is in 2013
                if transaction_date.year != 2013:
                    transaction_date = datetime(2013, 6, 15).date()
                
                transactions.append({
                    'receipt_date': transaction_date,
                    'vendor_name': str(vendor_val).strip() if pd.notna(vendor_val) else 'Unknown Vendor',
                    'gross_amount': float(amount_val),
                    'description': str(desc_val).strip() if pd.notna(desc_val) else '',
                    'category': sheet_name.lower().replace(' ', '_'),
                    'source_reference': f"2013_Excel_{os.path.basename(file_path)}_{sheet_name}_{idx}",
                })
            
            if transactions:
                sheet_total = sum(t['gross_amount'] for t in transactions)
                print(f"  Extracted {len(transactions)} transactions, total: ${sheet_total:,.2f}")
                all_transactions.extend(transactions)
            
        except Exception as e:
            print(f"  Error processing {sheet_name}: {e}")
    
    return all_transactions

def import_2013_transactions(transactions, dry_run=True):
    """Import 2013 transactions to database."""
    
    if not transactions:
        print("No transactions to import")
        return 0
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check for existing 2013 imports
        cur.execute("""
            SELECT COUNT(*) FROM receipts 
            WHERE source_reference LIKE '2013_Excel_%'
        """)
        
        existing_count = cur.fetchone()[0]
        print(f"Existing 2013 imports: {existing_count}")
        
        if dry_run:
            print(f"DRY RUN: Would import {len(transactions)} transactions")
            
            # Show summary by category
            categories = {}
            for t in transactions:
                cat = t['category']
                if cat not in categories:
                    categories[cat] = {'count': 0, 'total': 0}
                categories[cat]['count'] += 1
                categories[cat]['total'] += t['gross_amount']
            
            print(f"\nCategory breakdown:")
            total_amount = 0
            for cat, data in sorted(categories.items(), key=lambda x: x[1]['total'], reverse=True):
                print(f"  {cat:<20} ${data['total']:>10,.2f} ({data['count']:>3} transactions)")
                total_amount += data['total']
            
            print(f"\nTotal potential recovery: ${total_amount:,.2f}")
            print(f"Tax benefit (14%): ${total_amount * 0.14:,.2f}")
            
            return len(transactions)
        
        # Actually import
        insert_count = 0
        
        for transaction in transactions:
            # Calculate GST (5% included for Alberta)
            gross_amount = Decimal(str(transaction['gross_amount']))
            gst_amount = gross_amount * Decimal('0.05') / Decimal('1.05')
            net_amount = gross_amount - gst_amount
            
            # Generate unique hash
            hash_string = f"{transaction['source_reference']}_{transaction['receipt_date']}_{gross_amount}"
            source_hash = hashlib.sha256(hash_string.encode()).hexdigest()[:32]
            
            try:
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
                    transaction['vendor_name'][:200],  # Truncate if too long
                    gross_amount,
                    gst_amount,
                    net_amount,
                    transaction['description'][:500],  # Truncate if too long
                    transaction['category'],
                    'Business',
                    transaction['source_reference'],
                    '2013_Excel_Import',
                    source_hash,
                    datetime.now()
                ))
                
                insert_count += 1
                
            except psycopg2.IntegrityError:
                # Skip duplicates
                continue
        
        conn.commit()
        
        print(f"Successfully imported {insert_count} new 2013 expense receipts")
        
        return insert_count
        
    except Exception as e:
        conn.rollback()
        print(f"Error importing: {e}")
        return 0
    
    finally:
        cur.close()
        conn.close()

def main():
    """Process 2013 expense recovery - Phase 1."""
    
    import sys
    dry_run = '--write' not in sys.argv
    
    print("2013 EXPENSE RECOVERY - PHASE 1")
    print("=" * 50)
    print("Following 2012 success: $286K recovered")
    print("Target: $250K+ recovery for 2013")
    print()
    
    if dry_run:
        print("DRY RUN MODE (use --write to apply)")
    
    # Find 2013 files
    excel_files = find_2013_excel_files()
    print(f"Found {len(excel_files)} Excel files containing '2013'")
    
    all_transactions = []
    
    for file_path in excel_files[:3]:  # Process first 3 files initially
        print(f"\n--- Processing: {os.path.basename(file_path)} ---")
        
        transactions = extract_expenses_from_file(file_path, dry_run)
        
        if transactions:
            all_transactions.extend(transactions)
    
    if all_transactions:
        print(f"\n🎯 2013 RECOVERY SUMMARY:")
        print(f"Total transactions: {len(all_transactions)}")
        
        total_recovery = sum(t['gross_amount'] for t in all_transactions)
        print(f"Total recovery: ${total_recovery:,.2f}")
        print(f"Tax benefit: ${total_recovery * 0.14:,.2f}")
        
        # Import to database
        import_count = import_2013_transactions(all_transactions, dry_run)
        
        if not dry_run and import_count > 0:
            print(f"\n[OK] SUCCESS! Phase 1 (partial) complete")
            print(f"Imported {import_count} expense receipts")
            print(f"Continue with remaining 2013 files...")
        
    else:
        print("No expense transactions found in processed files")

if __name__ == "__main__":
    main()