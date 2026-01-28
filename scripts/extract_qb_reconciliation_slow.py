#!/usr/bin/env python
"""
SLOW BUT ACCURATE extraction of QuickBooks reconciliation data.
Uses character-level positioning and table extraction to handle poor OCR.
"""

import pdfplumber
import psycopg2
import os
import re
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def extract_tables_from_page(page):
    """Extract tables using pdfplumber's table detection"""
    tables = page.extract_tables()
    return tables

def extract_chars_from_page(page):
    """Extract individual characters with positions"""
    chars = page.chars
    return chars

def reconstruct_lines_from_chars(chars, y_tolerance=3):
    """
    Reconstruct text lines from individual characters.
    Groups characters by Y position with tolerance.
    """
    if not chars:
        return []
    
    # Group characters by Y position
    lines_dict = defaultdict(list)
    
    for char in chars:
        y = round(char['top'] / y_tolerance) * y_tolerance
        lines_dict[y].append(char)
    
    # Sort each line by X position
    lines = []
    for y in sorted(lines_dict.keys()):
        line_chars = sorted(lines_dict[y], key=lambda c: c['x0'])
        # Reconstruct text
        text = ''.join(c['text'] for c in line_chars)
        lines.append({
            'y': y,
            'text': text.strip(),
            'chars': line_chars
        })
    
    return lines

def parse_cheque_line(line_text):
    """
    Parse a cheque transaction line.
    Expected format: Cheque DATE NUM NAME AMOUNT
    """
    line_text = line_text.strip()
    
    # Look for date pattern MM/DD/YYYY
    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line_text)
    if not date_match:
        return None
    
    date_str = date_match.group(1)
    remaining = line_text[date_match.end():].strip()
    
    # Look for cheque number (usually 'dd' for direct debit or actual number)
    # After date, might have: dd, or actual cheque number
    parts = remaining.split()
    if not parts:
        return None
    
    # Check if first part is a number (cheque number)
    cheque_num = None
    name_start_idx = 0
    
    if parts[0].isdigit():
        cheque_num = parts[0]
        name_start_idx = 1
    elif parts[0] == 'dd':
        cheque_num = 'dd'
        name_start_idx = 1
    
    # Look for amount at the end (with possible negative sign)
    amount_match = re.search(r'(-?\d{1,3}(?:,\d{3})*\.\d{2})\s*$', remaining)
    if not amount_match:
        return None
    
    amount_str = amount_match.group(1).replace(',', '')
    
    # Everything between cheque number and amount is the payee name
    amount_start = amount_match.start()
    name_end = amount_start
    
    if name_start_idx < len(parts):
        # Reconstruct name from remaining text
        name_text = remaining[:name_end].strip()
        # Remove cheque number from name if present
        if cheque_num:
            name_text = name_text[len(cheque_num):].strip()
    else:
        name_text = ""
    
    try:
        trans_date = datetime.strptime(date_str, '%m/%d/%Y').date()
        amount = Decimal(amount_str)
        
        return {
            'type': 'Cheque',
            'date': trans_date,
            'cheque_number': cheque_num,
            'payee': name_text.strip(),
            'amount': abs(amount),  # Make positive for comparison
            'original_amount': amount,
            'line': line_text
        }
    except Exception as e:
        print(f"[WARN] Parse error: {e} | Line: {line_text[:80]}")
        return None

def extract_all_transactions(pdf_path, max_pages=None):
    """
    Extract all transactions from PDF using multiple methods.
    Goes page by page for accuracy.
    """
    print(f"\n=== OPENING PDF: {os.path.basename(pdf_path)} ===")
    
    all_transactions = []
    
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages) if max_pages is None else min(len(pdf.pages), max_pages)
        print(f"Processing {num_pages} pages...")
        
        for page_num in range(num_pages):
            print(f"\n--- Page {page_num + 1}/{num_pages} ---")
            page = pdf.pages[page_num]
            
            # Method 1: Try table extraction
            print("  Attempting table extraction...")
            tables = extract_tables_from_page(page)
            if tables:
                print(f"  ✓ Found {len(tables)} tables")
                for table_idx, table in enumerate(tables):
                    print(f"    Table {table_idx + 1}: {len(table)} rows")
            else:
                print("  ✗ No tables found")
            
            # Method 2: Character-level reconstruction
            print("  Extracting characters...")
            chars = extract_chars_from_page(page)
            print(f"  ✓ Found {len(chars)} characters")
            
            print("  Reconstructing lines from characters...")
            lines = reconstruct_lines_from_chars(chars, y_tolerance=2)
            print(f"  ✓ Reconstructed {len(lines)} lines")
            
            # Method 3: Standard text extraction as backup
            print("  Extracting standard text...")
            text = page.extract_text()
            text_lines = [l.strip() for l in text.split('\n') if l.strip()]
            print(f"  ✓ Standard extraction: {len(text_lines)} lines")
            
            # Parse transactions from reconstructed lines
            print("  Parsing transactions...")
            page_transactions = []
            
            for line in lines:
                line_text = line['text']
                
                # Skip header/footer lines
                if any(skip in line_text for skip in ['Reconciliation Detail', 'CIBC Bank', 'Beginning Balance', 'Cleared Balance', 'Type Date Num']):
                    continue
                
                # Look for Cheque lines
                if line_text.startswith('Cheque'):
                    trans = parse_cheque_line(line_text)
                    if trans:
                        page_transactions.append(trans)
            
            print(f"  ✓ Found {len(page_transactions)} transactions on this page")
            
            # Show first 3 transactions from this page
            if page_transactions:
                print("  Sample transactions:")
                for i, trans in enumerate(page_transactions[:3]):
                    print(f"    {i+1}. {trans['date']} | #{trans['cheque_number']} | {trans['payee'][:40]} | ${trans['amount']:,.2f}")
            
            all_transactions.extend(page_transactions)
    
    return all_transactions

def match_to_database(transactions, cur):
    """Match transactions to cheque_register"""
    print(f"\n=== MATCHING {len(transactions)} TRANSACTIONS TO DATABASE ===")
    
    matched = []
    unmatched = []
    needs_payee_update = []
    
    for trans in transactions:
        # Skip 'dd' (direct debit) transactions - those aren't in cheque register
        if trans['cheque_number'] == 'dd':
            continue
        
        # Try matching by cheque number
        if trans['cheque_number'] and trans['cheque_number'].isdigit():
            cur.execute("""
                SELECT id, cheque_number, cheque_date, cleared_date, payee, amount, banking_transaction_id
                FROM cheque_register
                WHERE cheque_number = %s
            """, (trans['cheque_number'],))
            
            result = cur.fetchone()
            if result:
                reg_id, reg_num, reg_date, cleared_date, reg_payee, reg_amount, bank_id = result
                matched.append({
                    'pdf': trans,
                    'register': {
                        'id': reg_id,
                        'number': reg_num,
                        'date': reg_date,
                        'cleared_date': cleared_date,
                        'payee': reg_payee,
                        'amount': reg_amount,
                        'banking_id': bank_id
                    }
                })
                
                # Check if payee needs updating
                if not reg_payee or reg_payee == 'Unknown':
                    needs_payee_update.append({
                        'id': reg_id,
                        'cheque_number': reg_num,
                        'current_payee': reg_payee,
                        'new_payee': trans['payee'],
                        'amount': reg_amount
                    })
                continue
        
        # Try matching by date and amount
        cur.execute("""
            SELECT id, cheque_number, cheque_date, cleared_date, payee, amount, banking_transaction_id
            FROM cheque_register
            WHERE (cheque_date = %s OR cleared_date = %s)
            AND ABS(amount - %s) < 0.01
        """, (trans['date'], trans['date'], trans['amount']))
        
        results = cur.fetchall()
        if results:
            if len(results) == 1:
                reg_id, reg_num, reg_date, cleared_date, reg_payee, reg_amount, bank_id = results[0]
                matched.append({
                    'pdf': trans,
                    'register': {
                        'id': reg_id,
                        'number': reg_num,
                        'date': reg_date,
                        'cleared_date': cleared_date,
                        'payee': reg_payee,
                        'amount': reg_amount,
                        'banking_id': bank_id
                    },
                    'matched_by': 'date_amount'
                })
                
                if not reg_payee or reg_payee == 'Unknown':
                    needs_payee_update.append({
                        'id': reg_id,
                        'cheque_number': reg_num,
                        'current_payee': reg_payee,
                        'new_payee': trans['payee'],
                        'amount': reg_amount
                    })
            else:
                # Multiple matches - add to unmatched for manual review
                unmatched.append(trans)
        else:
            unmatched.append(trans)
    
    print(f"✓ Matched: {len(matched)}")
    print(f"✓ Need payee update: {len(needs_payee_update)}")
    print(f"⚠ Unmatched: {len(unmatched)}")
    
    return matched, needs_payee_update, unmatched

def main():
    pdf_path = r"L:\limo\pdf\2012\2012 quickbooks cibc bank reconciliation detailed_ocred.pdf"
    
    print("=" * 80)
    print("SLOW & ACCURATE QUICKBOOKS RECONCILIATION EXTRACTOR")
    print("=" * 80)
    print(f"\nPDF: {pdf_path}")
    print(f"Size: {os.path.getsize(pdf_path):,} bytes")
    
    # Extract transactions (process all pages)
    print("\n" + "=" * 80)
    print("STEP 1: EXTRACTING TRANSACTIONS FROM PDF")
    print("=" * 80)
    
    # Process ALL 65 pages
    transactions = extract_all_transactions(pdf_path, max_pages=None)
    
    print(f"\n" + "=" * 80)
    print(f"EXTRACTION COMPLETE: {len(transactions)} transactions found")
    print("=" * 80)
    
    # Show summary
    if transactions:
        print("\nFirst 10 transactions:")
        for i, trans in enumerate(transactions[:10]):
            cheque_num = trans['cheque_number'] or 'None'
            payee = trans['payee'][:45] if trans['payee'] else '(no payee)'
            print(f"  {i+1:2d}. {trans['date']} | Cheque #{cheque_num:>6s} | {payee:45s} | ${trans['amount']:>10,.2f}")
    
    # Match to database
    print("\n" + "=" * 80)
    print("STEP 2: MATCHING TO DATABASE")
    print("=" * 80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    matched, needs_update, unmatched = match_to_database(transactions, cur)
    
    # Show results
    print("\n" + "=" * 80)
    print("PAYEE UPDATES NEEDED")
    print("=" * 80)
    
    if needs_update:
        print(f"\nFound {len(needs_update)} cheques needing payee information:\n")
        for i, update in enumerate(needs_update[:20]):
            print(f"  {i+1:2d}. Cheque #{update['cheque_number']} | ${update['amount']:>10,.2f}")
            print(f"      Current: {update['current_payee'] or '(blank)'}")
            print(f"      PDF says: {update['new_payee']}")
            print()
    
    if unmatched:
        print("\n" + "=" * 80)
        print(f"UNMATCHED TRANSACTIONS: {len(unmatched)}")
        print("=" * 80)
        print("\nFirst 10 unmatched:")
        for i, trans in enumerate(unmatched[:10]):
            print(f"  {i+1:2d}. {trans['date']} | #{trans['cheque_number']} | {trans['payee'][:40]} | ${trans['amount']:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Pages processed: ALL 65 pages")
    print(f"Transactions extracted: {len(transactions)}")
    print(f"Matched to register: {len(matched)}")
    print(f"Payees to update: {len(needs_update)}")
    print(f"Unmatched: {len(unmatched)}")
    
    # Export payee updates to file for review
    if needs_update:
        update_file = r'L:\limo\data\cheque_payee_updates_from_qb.csv'
        import csv
        with open(update_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['cheque_register_id', 'cheque_number', 'current_payee', 'new_payee', 'amount'])
            for update in needs_update:
                writer.writerow([
                    update['id'],
                    update['cheque_number'],
                    update['current_payee'] or '',
                    update['new_payee'],
                    f"{update['amount']:.2f}"
                ])
        print(f"\n[OK] Exported payee updates to: {update_file}")
        print("   Review this file and run apply_cheque_payee_updates.py to update database")

if __name__ == '__main__':
    main()
