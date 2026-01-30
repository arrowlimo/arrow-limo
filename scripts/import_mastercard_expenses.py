#!/usr/bin/env python
"""
Import Canadian Tire Triangle Mastercard Business Expenses

This script processes Mastercard statements and imports business expenses
paid by David into the receipts table.

Usage:
    # Step 1: Extract all transactions from PDFs to CSV for review
    python import_mastercard_expenses.py --extract --pdf-dir "l:/limo/Canadian Tire mastercard"
    
    # Step 2: Mark business expenses in the CSV (add 'Y' in business_expense column)
    # Edit: l:/limo/reports/mastercard_transactions.csv
    
    # Step 3: Import marked business expenses to database
    python import_mastercard_expenses.py --import --csv "l:/limo/reports/mastercard_transactions.csv" --write
    
    # Step 4: Dry-run to preview what will be imported
    python import_mastercard_expenses.py --import --csv "l:/limo/reports/mastercard_transactions.csv"

Author: AI Assistant
Date: October 2025
"""

import os
import sys
import argparse
import csv
from pathlib import Path
from datetime import datetime
import re
import hashlib

# PDF processing
try:
    import PyPDF2
except ImportError:
    print("[WARN] PyPDF2 not installed. Install with: pip install PyPDF2")
    sys.exit(1)

# Database connection
try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("[WARN] psycopg2 not installed. Install with: pip install psycopg2")
    sys.exit(1)

# Excel export
try:
    import pandas as pd
except ImportError:
    print("[WARN] pandas not installed. Install with: pip install pandas openpyxl")
    sys.exit(1)

# Database connection helper
def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# Merchant categorization patterns
MERCHANT_CATEGORIES = {
    'fuel': [
        'shell', 'petro', 'esso', 'fas gas', 'chevron', 'co-op', 'husky',
        'canadian tire gas', 'gas bar', 'fuel', 'gasoline', 'diesel'
    ],
    'maintenance': [
        'canadian tire', 'autozone', 'napa', 'car quest', 'jiffy lube',
        'midas', 'meineke', 'repair', 'automotive', 'brake', 'tire', 'oil change'
    ],
    'office': [
        'staples', 'office depot', 'grand & toy', 'office supplies',
        'stationery', 'paper', 'ink', 'toner'
    ],
    'insurance': [
        'aviva', 'sgi', 'insurance', 'premium', 'policy'
    ],
    'licensing': [
        'sgi', 'registration', 'license', 'permit', 'vehicle registration'
    ],
    'communication': [
        'sasktel', 'rogers', 'bell', 'telus', 'phone', 'internet', 'cell'
    ],
    'meals': [
        'restaurant', 'cafe', 'coffee', 'tim hortons', 'starbucks', 
        'subway', 'mcdonald', 'wendy', 'burger king', 'pizza'
    ],
    'parking': [
        'parking', 'impark', 'park plus', 'parking meter'
    ],
    'tolls': [
        'toll', 'highway', 'etoll', '407 etr'
    ],
    'cleaning': [
        'car wash', 'detail', 'cleaning', 'janitorial'
    ],
    'bank_fees': [
        'bank fee', 'service charge', 'interest', 'finance charge', 'annual fee'
    ]
}

def categorize_merchant(merchant_name):
    """Auto-categorize merchant based on name patterns."""
    merchant_lower = merchant_name.lower()
    
    for category, keywords in MERCHANT_CATEGORIES.items():
        if any(keyword in merchant_lower for keyword in keywords):
            return category
    
    return 'uncategorized'

def calculate_gst_included(gross_amount, province='AB'):
    """
    Calculate GST that is INCLUDED in the gross amount.
    Alberta: 5% GST only.
    
    Formula: GST = gross × (0.05 / 1.05)
    """
    gst_rate = 0.05  # Alberta
    gst_amount = gross_amount * gst_rate / (1 + gst_rate)
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

def extract_transactions_from_pdf(pdf_path):
    """
    Extract transaction data from Canadian Tire Mastercard PDF statement.
    
    Returns list of dicts with: date, merchant, amount, description
    """
    transactions = []
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"
            
            # Parse statement date from filename (YYYY-MM-DD format)
            filename = os.path.basename(pdf_path)
            statement_date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', filename)
            statement_year = int(statement_date_match.group(1)) if statement_date_match else datetime.now().year
            statement_month = int(statement_date_match.group(2)) if statement_date_match else datetime.now().month
            
            # Pattern for transaction lines (varies by statement format)
            # Example: "Jan 15  SHELL GAS STATION           45.67"
            # Example: "01/15   SHELL GAS STATION           $45.67"
            
            transaction_patterns = [
                # Pattern 1: Mon DD  Merchant  Amount
                r'([A-Z][a-z]{2})\s+(\d{1,2})\s+([A-Z][A-Z\s\.\-&]+?)\s+(\d+\.\d{2})',
                # Pattern 2: MM/DD  Merchant  Amount
                r'(\d{1,2})/(\d{1,2})\s+([A-Z][A-Z\s\.\-&]+?)\s+\$?(\d+\.\d{2})',
                # Pattern 3: DD-MM  Merchant  Amount
                r'(\d{1,2})-(\d{1,2})\s+([A-Z][A-Z\s\.\-&]+?)\s+\$?(\d+\.\d{2})',
            ]
            
            for line in full_text.split('\n'):
                line = line.strip()
                
                # Try each pattern
                for pattern in transaction_patterns:
                    match = re.search(pattern, line)
                    if match:
                        groups = match.groups()
                        
                        # Parse date based on pattern
                        if len(groups) == 4:
                            if groups[0].isalpha():  # Pattern 1 (Mon DD)
                                month_abbr = groups[0]
                                day = int(groups[1])
                                month = datetime.strptime(month_abbr, '%b').month
                                merchant = groups[2].strip()
                                amount = float(groups[3])
                            else:  # Pattern 2 or 3 (MM/DD or DD-MM)
                                month = int(groups[0])
                                day = int(groups[1])
                                merchant = groups[2].strip()
                                amount = float(groups[3])
                            
                            # Construct full date
                            try:
                                transaction_date = datetime(statement_year, month, day)
                            except ValueError:
                                # Invalid date, skip
                                continue
                            
                            # Skip if amount is too small (likely not a real transaction)
                            if amount < 0.01:
                                continue
                            
                            # Skip common non-transaction lines
                            skip_merchants = [
                                'TOTAL', 'BALANCE', 'PAYMENT', 'CREDIT', 'MINIMUM',
                                'DUE DATE', 'STATEMENT', 'PAGE', 'ACCOUNT', 'PREVIOUS'
                            ]
                            if any(skip in merchant.upper() for skip in skip_merchants):
                                continue
                            
                            transactions.append({
                                'date': transaction_date.strftime('%Y-%m-%d'),
                                'merchant': merchant.title(),  # Title case for readability
                                'amount': amount,
                                'description': f"{merchant.title()} - {transaction_date.strftime('%b %d, %Y')}",
                                'category': categorize_merchant(merchant),
                                'source_file': filename
                            })
                            
                            break  # Found match, no need to try other patterns
    
    except Exception as e:
        print(f"[WARN] Error processing {pdf_path}: {e}")
        return []
    
    return transactions

def extract_all_statements(pdf_dir, output_csv):
    """
    Extract transactions from all PDF statements in directory.
    
    Output CSV format:
    date,merchant,amount,description,category,business_expense,notes,source_file
    """
    pdf_dir = Path(pdf_dir)
    
    if not pdf_dir.exists():
        print(f"[FAIL] Directory not found: {pdf_dir}")
        return
    
    # Find all PDF files
    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    
    if not pdf_files:
        print(f"[FAIL] No PDF files found in: {pdf_dir}")
        return
    
    print(f"\n📄 Found {len(pdf_files)} PDF statement files")
    print("=" * 80)
    
    all_transactions = []
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}...", end=' ')
        transactions = extract_transactions_from_pdf(pdf_file)
        
        if transactions:
            all_transactions.extend(transactions)
            print(f"✓ {len(transactions)} transactions")
        else:
            print("[WARN] No transactions found")
    
    # Remove duplicates based on date+merchant+amount
    unique_transactions = []
    seen_hashes = set()
    
    for txn in all_transactions:
        txn_hash = hashlib.md5(
            f"{txn['date']}{txn['merchant']}{txn['amount']}".encode()
        ).hexdigest()
        
        if txn_hash not in seen_hashes:
            seen_hashes.add(txn_hash)
            unique_transactions.append(txn)
    
    print(f"\n📊 Total transactions extracted: {len(all_transactions)}")
    print(f"📊 Unique transactions (after dedup): {len(unique_transactions)}")
    
    # Write to CSV with business_expense column (empty for user to fill)
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'date', 'merchant', 'amount', 'description', 'category',
            'business_expense', 'notes', 'source_file'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for txn in sorted(unique_transactions, key=lambda x: x['date']):
            writer.writerow({
                'date': txn['date'],
                'merchant': txn['merchant'],
                'amount': txn['amount'],
                'description': txn['description'],
                'category': txn['category'],
                'business_expense': '',  # USER FILLS THIS: Y or N
                'notes': '',  # USER ADDS NOTES
                'source_file': txn['source_file']
            })
    
    print(f"\n[OK] Transactions exported to: {output_csv}")
    print("\n" + "=" * 80)
    print("📝 NEXT STEPS:")
    print("=" * 80)
    print("1. Open CSV in Excel/LibreOffice")
    print("2. Review 'category' column for auto-categorization accuracy")
    print("3. Mark business expenses:")
    print("   - Put 'Y' in 'business_expense' column for business purchases")
    print("   - Put 'N' or leave blank for personal purchases")
    print("4. Add any notes in 'notes' column")
    print("5. Save the CSV file")
    print("6. Run import step:")
    print(f"   python {os.path.basename(__file__)} --import --csv \"{output_csv}\" --write")
    print("=" * 80)

def get_david_employee_id(conn):
    """Get or create David's employee record."""
    cur = conn.cursor()
    
    # Look for David in employees table
    cur.execute("""
        SELECT employee_id FROM employees
        WHERE LOWER(full_name) LIKE '%david%'
        OR LOWER(first_name) = 'david'
        LIMIT 1
    """)
    
    result = cur.fetchone()
    
    if result:
        employee_id = result[0]
        print(f"✓ Found David's employee ID: {employee_id}")
    else:
        print("[WARN] David's employee record not found in database")
        print("   Creating placeholder employee record...")
        
        cur.execute("""
            INSERT INTO employees (
                full_name, first_name, last_name, 
                position, status, created_at
            )
            VALUES (
                'David (Owner)', 'David', '', 
                'Owner/Operator', 'active', NOW()
            )
            RETURNING employee_id
        """)
        employee_id = cur.fetchone()[0]
        conn.commit()
        print(f"✓ Created employee record for David: ID {employee_id}")
    
    cur.close()
    return employee_id

def import_business_expenses(csv_path, write_mode=False):
    """
    Import business expenses from CSV to receipts table.
    
    CSV must have these columns (matching receipts table schema):
    - receipt_date (required)
    - vendor_name (required)
    - gross_amount (required)
    - description
    - category
    - payment_method (default: Mastercard)
    - comment
    - business_personal (business/personal)
    - employee_id (optional, will lookup David if empty)
    """
    if not os.path.exists(csv_path):
        print(f"[FAIL] CSV file not found: {csv_path}")
        return
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    required_cols = ['receipt_date', 'vendor_name', 'gross_amount']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"[FAIL] Missing required columns: {', '.join(missing_cols)}")
        print(f"   Available columns: {', '.join(df.columns)}")
        return
    
    # Filter to business expenses (business_personal = 'business' or not specified)
    if 'business_personal' in df.columns:
        business_mask = (df['business_personal'].fillna('business').str.lower() == 'business')
        business_df = df[business_mask].copy()
    else:
        business_df = df.copy()  # Assume all are business if column not specified
    
    if len(business_df) == 0:
        print("[WARN] No business expenses found in CSV")
        return
    
    print(f"\n💼 Found {len(business_df)} business expenses marked for import")
    print("=" * 80)
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get David's employee ID
    david_employee_id = get_david_employee_id(conn)
    
    # Process each business expense
    imported_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, row in business_df.iterrows():
        try:
            receipt_date = row['receipt_date']
            vendor_name = row['vendor_name']
            gross_amount = float(row['gross_amount'])
            description = row.get('description', vendor_name)
            category = row.get('category', 'uncategorized')
            payment_method = row.get('payment_method', 'Mastercard')
            comment = row.get('comment', 'Business expense paid by David - Canadian Tire Mastercard')
            business_personal = row.get('business_personal', 'business')
            
            # Get employee_id (use from CSV if provided, otherwise lookup David)
            if 'employee_id' in row and pd.notna(row['employee_id']) and row['employee_id'] != '':
                employee_id = int(row['employee_id'])
            else:
                employee_id = david_employee_id
            
            # Calculate GST (included in amount)
            gst_amount, net_amount = calculate_gst_included(gross_amount, 'AB')
            
            # Create source reference for deduplication
            source_ref = f"MASTERCARD_{receipt_date}_{vendor_name}_{gross_amount}"
            source_hash = hashlib.sha256(source_ref.encode()).hexdigest()
            
            # Check if already imported
            cur.execute("""
                SELECT id FROM receipts
                WHERE source_hash = %s
            """, (source_hash,))
            
            if cur.fetchone():
                print(f"⊘ Skipped (already imported): {receipt_date} {vendor_name} ${gross_amount}")
                skipped_count += 1
                continue
            
            if write_mode:
                # Insert into receipts table (matching schema exactly)
                cur.execute("""
                    INSERT INTO receipts (
                        source_system, source_reference, source_hash,
                        receipt_date, vendor_name, description,
                        gross_amount, gst_amount, net_amount,
                        category, payment_method, comment,
                        business_personal, 
                        created_at, auto_categorized
                    )
                    VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s,
                        NOW(), %s
                    )
                    RETURNING id
                """, (
                    'mastercard_import', source_ref, source_hash,
                    receipt_date, vendor_name, description,
                    gross_amount, gst_amount, net_amount,
                    category, payment_method, comment,
                    business_personal,
                    True  # auto_categorized
                ))
                
                receipt_id = cur.fetchone()[0]
                print(f"✓ Imported: {receipt_date} {vendor_name} ${gross_amount} (GST: ${gst_amount}) → Receipt ID {receipt_id}")
                imported_count += 1
            else:
                # Dry-run mode
                print(f"[DRY-RUN] Would import: {receipt_date} {vendor_name} ${gross_amount} (GST: ${gst_amount}, Net: ${net_amount})")
                print(f"           Category: {category}, Payment: {payment_method}")
                imported_count += 1
        
        except Exception as e:
            print(f"[FAIL] Error processing row {idx}: {e}")
            error_count += 1
    
    if write_mode:
        conn.commit()
        print(f"\n[OK] Import complete!")
    else:
        print(f"\n📋 DRY-RUN complete (no changes made)")
        print(f"   Run with --write flag to actually import data")
    
    print("=" * 80)
    print(f"Imported: {imported_count}")
    print(f"Skipped (already in DB): {skipped_count}")
    print(f"Errors: {error_count}")
    print("=" * 80)
    
    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Import Canadian Tire Mastercard business expenses paid by David',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Step 1: Extract transactions from PDFs
  python import_mastercard_expenses.py --extract --pdf-dir "l:/limo/Canadian Tire mastercard"
  
  # Step 2: Mark business expenses in CSV (open in Excel, add 'Y' to business_expense column)
  
  # Step 3: Preview import (dry-run)
  python import_mastercard_expenses.py --import --csv "l:/limo/reports/mastercard_transactions.csv"
  
  # Step 4: Actually import to database
  python import_mastercard_expenses.py --import --csv "l:/limo/reports/mastercard_transactions.csv" --write
        """
    )
    
    parser.add_argument('--extract', action='store_true',
                        help='Extract transactions from PDF statements')
    parser.add_argument('--import', dest='import_mode', action='store_true',
                        help='Import marked business expenses to database')
    parser.add_argument('--pdf-dir', type=str,
                        help='Directory containing Mastercard PDF statements')
    parser.add_argument('--csv', type=str,
                        help='CSV file with transactions (for import)')
    parser.add_argument('--write', action='store_true',
                        help='Actually write to database (default is dry-run)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.extract and args.import_mode:
        print("[FAIL] Cannot use both --extract and --import at the same time")
        sys.exit(1)
    
    if args.extract:
        if not args.pdf_dir:
            print("[FAIL] --pdf-dir required for --extract mode")
            sys.exit(1)
        
        output_csv = 'l:/limo/reports/mastercard_transactions.csv'
        extract_all_statements(args.pdf_dir, output_csv)
    
    elif args.import_mode:
        if not args.csv:
            print("[FAIL] --csv required for --import mode")
            sys.exit(1)
        
        import_business_expenses(args.csv, write_mode=args.write)
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
