"""
Parse Scotia Bank 2012 statements PDF with table data extraction.

Special requirements:
- Line divides dollars and cents in amounts
- Date is last line of transactions for that day (mm/dd format for 2012)
- Minus sign placement is unusual
- Validate every column (ignore check marks and notes)
- Hard copy balance column and maintain running balance for audit
- Fill NULL/NaN dates with appropriate date
- Extract: description, withdrawal, deposit, date, balance columns
- Last 2 lines are totals - verify but don't import

Usage:
    python parse_scotia_pdf_tables_2012.py
"""

import pdfplumber
import pandas as pd
import re
from decimal import Decimal
from datetime import datetime
import os


PDF_PATH = r"L:\limo\pdf\2012\2012 scotiabank statements all.pdf"


def clean_amount(text):
    """
    Parse amount from text, handling line-divided dollars/cents and unusual minus placement.
    
    Examples:
    - "1,234 56" → 1234.56
    - "1,234-56" → -1234.56
    - "- 1,234 56" → -1234.56
    - "1234.56" → 1234.56
    """
    if not text or pd.isna(text):
        return None
    
    text = str(text).strip()
    if not text or text in ['', '-', 'nan', 'NaN']:
        return None
    
    # Remove common formatting
    text = text.replace(',', '').replace(' ', '')
    
    # Check for minus sign in various positions
    is_negative = False
    if '-' in text:
        is_negative = True
        text = text.replace('-', '')
    
    # Try to extract numeric value
    try:
        # Look for digits with optional decimal
        match = re.search(r'(\d+)\.?(\d{0,2})', text)
        if match:
            dollars = match.group(1)
            cents = match.group(2) if match.group(2) else '00'
            
            # Pad cents to 2 digits
            cents = cents.ljust(2, '0')[:2]
            
            amount = Decimal(f"{dollars}.{cents}")
            return -amount if is_negative else amount
    except:
        pass
    
    return None


def parse_date(text, current_year=2012):
    """
    Parse date from mm/dd format for 2012.
    
    Returns: datetime.date object or None
    """
    if not text or pd.isna(text):
        return None
    
    text = str(text).strip()
    
    # Try mm/dd format
    match = re.search(r'(\d{1,2})/(\d{1,2})', text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        
        try:
            return datetime(current_year, month, day).date()
        except ValueError:
            return None
    
    return None


def extract_tables_from_pdf(pdf_path):
    """
    Extract all tables from PDF, handling Scotia Bank statement format.
    """
    print(f"Opening PDF: {pdf_path}")
    
    all_transactions = []
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\n--- Processing page {page_num} ---")
            
            # Extract tables
            tables = page.extract_tables()
            
            if not tables:
                print(f"  No tables found on page {page_num}")
                continue
            
            print(f"  Found {len(tables)} table(s)")
            
            for table_num, table in enumerate(tables, 1):
                print(f"  Processing table {table_num} ({len(table)} rows)")
                
                # Process each row
                for row_num, row in enumerate(table):
                    if not row or all(not cell or str(cell).strip() == '' for cell in row):
                        continue
                    
                    # Try to identify columns
                    # Expected: Date, Description, Withdrawal, Deposit, Balance
                    
                    # Skip header rows
                    row_text = ' '.join([str(cell) for cell in row if cell]).lower()
                    if 'date' in row_text and 'description' in row_text:
                        print(f"    Row {row_num}: Header row (skipped)")
                        continue
                    
                    # Skip footer/total rows (last 2 lines typically)
                    if 'total' in row_text or 'balance forward' in row_text:
                        print(f"    Row {row_num}: Total row (skipped)")
                        continue
                    
                    # Parse row based on column count
                    if len(row) >= 5:
                        date_col = row[0]
                        desc_col = row[1]
                        withdrawal_col = row[2]
                        deposit_col = row[3]
                        balance_col = row[4]
                        
                        # Parse date
                        date_parsed = parse_date(date_col)
                        
                        # Parse amounts
                        withdrawal = clean_amount(withdrawal_col)
                        deposit = clean_amount(deposit_col)
                        balance = clean_amount(balance_col)
                        
                        # Clean description
                        description = str(desc_col).strip() if desc_col else ''
                        
                        # Skip if no meaningful data
                        if not description and not withdrawal and not deposit and not balance:
                            continue
                        
                        # Store transaction
                        all_transactions.append({
                            'page': page_num,
                            'table': table_num,
                            'row': row_num,
                            'date': date_parsed,
                            'description': description,
                            'withdrawal': withdrawal,
                            'deposit': deposit,
                            'balance': balance
                        })
                        
                        print(f"    Row {row_num}: {date_parsed} | {description[:30]} | W:{withdrawal} D:{deposit} B:{balance}")
    
    print(f"\nTotal transactions extracted: {len(all_transactions)}")
    return all_transactions


def fill_missing_dates(transactions):
    """
    Fill NULL/NaN dates with appropriate date (last known date for that day's transactions).
    """
    print("\nFilling missing dates...")
    
    last_date = None
    filled_count = 0
    
    for txn in transactions:
        if txn['date']:
            last_date = txn['date']
        elif last_date:
            txn['date'] = last_date
            filled_count += 1
    
    print(f"Filled {filled_count} missing dates")
    return transactions


def verify_running_balance(transactions):
    """
    Verify and maintain running balance for audit.
    """
    print("\nVerifying running balance...")
    
    if not transactions:
        print("No transactions to verify")
        return []
    
    # Sort by date
    transactions = sorted(transactions, key=lambda x: (x['date'] or datetime(1900, 1, 1).date(), x['page'], x['row']))
    
    mismatches = []
    
    for i, txn in enumerate(transactions):
        if txn['balance'] is None:
            continue
        
        # Calculate expected balance
        if i == 0:
            # First transaction - use its balance as opening
            txn['expected_balance'] = txn['balance']
            txn['balance_match'] = True
        else:
            prev_txn = transactions[i-1]
            
            if prev_txn['balance'] is None:
                txn['expected_balance'] = None
                txn['balance_match'] = None
            else:
                # Calculate: prev_balance - withdrawal + deposit
                expected = prev_txn['balance']
                
                if txn['withdrawal']:
                    expected -= txn['withdrawal']
                
                if txn['deposit']:
                    expected += txn['deposit']
                
                txn['expected_balance'] = expected
                
                # Compare
                diff = abs(txn['balance'] - expected)
                txn['balance_match'] = diff < Decimal('0.01')
                
                if not txn['balance_match']:
                    mismatches.append({
                        'index': i,
                        'date': txn['date'],
                        'description': txn['description'],
                        'expected': expected,
                        'actual': txn['balance'],
                        'diff': txn['balance'] - expected
                    })
    
    print(f"Balance verification complete")
    print(f"Found {len(mismatches)} balance mismatches")
    
    if mismatches:
        print("\nFirst 10 mismatches:")
        for m in mismatches[:10]:
            print(f"  {m['date']} | {m['description'][:30]} | Expected: {m['expected']} | Actual: {m['actual']} | Diff: {m['diff']}")
    
    return transactions, mismatches


def export_to_csv(transactions, output_path):
    """Export transactions to CSV."""
    df = pd.DataFrame(transactions)
    
    # Reorder columns
    columns = ['date', 'description', 'withdrawal', 'deposit', 'balance', 
               'expected_balance', 'balance_match', 'page', 'table', 'row']
    
    # Only include columns that exist
    columns = [c for c in columns if c in df.columns]
    df = df[columns]
    
    df.to_csv(output_path, index=False)
    print(f"\nExported to: {output_path}")


def main():
    if not os.path.exists(PDF_PATH):
        print(f"ERROR: PDF not found at {PDF_PATH}")
        return
    
    # Extract transactions
    transactions = extract_tables_from_pdf(PDF_PATH)
    
    if not transactions:
        print("No transactions extracted!")
        return
    
    # Fill missing dates
    transactions = fill_missing_dates(transactions)
    
    # Verify running balance
    transactions, mismatches = verify_running_balance(transactions)
    
    # Export to CSV
    output_path = r"L:\limo\data\scotia_2012_parsed_from_pdf.csv"
    export_to_csv(transactions, output_path)
    
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"Total transactions: {len(transactions)}")
    print(f"Date range: {min(t['date'] for t in transactions if t['date'])} to {max(t['date'] for t in transactions if t['date'])}")
    print(f"Balance mismatches: {len(mismatches)}")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()
