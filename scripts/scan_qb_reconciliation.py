#!/usr/bin/env python
"""
Scan specific QuickBooks CIBC reconciliation PDF and match to banking_transactions.
"""

import psycopg2
import os
import re
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdfplumber or PyPDF2"""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except ImportError:
        print("[WARN] pdfplumber not available, trying PyPDF2...")
        try:
            import PyPDF2
            text = ""
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except ImportError:
            print("[FAIL] Neither pdfplumber nor PyPDF2 available")
            print("   Install with: pip install pdfplumber")
            return None

def parse_cheque_transactions(text):
    """
    Parse cheque transactions from QuickBooks reconciliation report.
    Looking for patterns like:
    - Cheque number, date, payee, amount
    - May have multiple formats depending on QB export
    """
    transactions = []
    
    # Pattern 1: Standard cheque line with number, date, description, amount
    # Example: "17086706    01/04/2012    PAYEE NAME    1,234.56"
    pattern1 = re.compile(
        r'(\d{8})\s+(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        re.IGNORECASE
    )
    
    # Pattern 2: Date first format
    # Example: "01/04/2012    17086706    PAYEE NAME    1,234.56"
    pattern2 = re.compile(
        r'(\d{2}/\d{2}/\d{4})\s+(\d{8})\s+(.+?)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        re.IGNORECASE
    )
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Try pattern 1 (cheque number first)
        match = pattern1.search(line)
        if match:
            cheque_num = match.group(1)
            date_str = match.group(2)
            payee = match.group(3).strip()
            amount_str = match.group(4).replace(',', '')
            
            try:
                date = datetime.strptime(date_str, '%m/%d/%Y').date()
                amount = Decimal(amount_str)
                transactions.append({
                    'cheque_number': cheque_num,
                    'date': date,
                    'payee': payee,
                    'amount': amount,
                    'line': line
                })
                continue
            except:
                pass
        
        # Try pattern 2 (date first)
        match = pattern2.search(line)
        if match:
            date_str = match.group(1)
            cheque_num = match.group(2)
            payee = match.group(3).strip()
            amount_str = match.group(4).replace(',', '')
            
            try:
                date = datetime.strptime(date_str, '%m/%d/%Y').date()
                amount = Decimal(amount_str)
                transactions.append({
                    'cheque_number': cheque_num,
                    'date': date,
                    'payee': payee,
                    'amount': amount,
                    'line': line
                })
            except:
                pass
    
    return transactions

def match_to_cheque_register(transactions, cur):
    """Match parsed transactions to cheque_register"""
    matched = []
    unmatched = []
    
    for trans in transactions:
        # Try exact cheque number match
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
                },
                'payee_match': reg_payee == 'Unknown' or reg_payee is None
            })
        else:
            # Try amount and date match
            cur.execute("""
                SELECT id, cheque_number, cheque_date, cleared_date, payee, amount, banking_transaction_id
                FROM cheque_register
                WHERE ABS(amount - %s) < 0.01
                AND (cheque_date = %s OR cleared_date = %s)
            """, (trans['amount'], trans['date'], trans['date']))
            
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
                    },
                    'payee_match': reg_payee == 'Unknown' or reg_payee is None,
                    'number_mismatch': True
                })
            else:
                unmatched.append(trans)
    
    return matched, unmatched

def update_payees(matched, cur, conn, dry_run=True):
    """Update payee information for matched cheques"""
    updates = []
    
    for match in matched:
        if match.get('payee_match'):  # Payee is Unknown or None
            pdf_payee = match['pdf']['payee']
            reg_id = match['register']['id']
            reg_num = match['register']['number']
            
            if not dry_run:
                cur.execute("""
                    UPDATE cheque_register
                    SET payee = %s
                    WHERE id = %s
                """, (pdf_payee, reg_id))
            
            updates.append({
                'id': reg_id,
                'cheque_number': reg_num,
                'new_payee': pdf_payee,
                'amount': match['register']['amount']
            })
    
    if not dry_run:
        conn.commit()
    
    return updates

def main():
    pdf_path = r"L:\limo\pdf\2012\2012 quickbooks cibc bank reconciliation detailed_ocred.pdf"
    
    print(f"=== SCANNING QUICKBOOKS RECONCILIATION PDF ===")
    print(f"File: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print(f"[FAIL] File not found: {pdf_path}")
        return
    
    print(f"[OK] File exists ({os.path.getsize(pdf_path):,} bytes)")
    
    # Extract text
    print("\n=== EXTRACTING TEXT ===")
    text = extract_text_from_pdf(pdf_path)
    if not text:
        print("[FAIL] Failed to extract text from PDF")
        return
    
    print(f"[OK] Extracted {len(text):,} characters")
    
    # Parse transactions
    print("\n=== PARSING TRANSACTIONS ===")
    transactions = parse_cheque_transactions(text)
    print(f"[OK] Found {len(transactions)} cheque transactions")
    
    if transactions:
        print("\nFirst 5 transactions:")
        for i, trans in enumerate(transactions[:5]):
            print(f"  {i+1}. Cheque #{trans['cheque_number']} | {trans['date']} | {trans['payee'][:40]} | ${trans['amount']:,.2f}")
    
    # Match to database
    print("\n=== MATCHING TO CHEQUE REGISTER ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    matched, unmatched = match_to_cheque_register(transactions, cur)
    
    print(f"[OK] Matched: {len(matched)}")
    print(f"[WARN] Unmatched: {len(unmatched)}")
    
    # Show matches with missing payee info
    needs_update = [m for m in matched if m.get('payee_match')]
    print(f"\n=== CHEQUES NEEDING PAYEE UPDATE ===")
    print(f"Found {len(needs_update)} cheques with Unknown/missing payee")
    
    if needs_update:
        print("\nFirst 10 updates needed:")
        for i, match in enumerate(needs_update[:10]):
            reg = match['register']
            pdf = match['pdf']
            mismatch = " [NUMBER MISMATCH]" if match.get('number_mismatch') else ""
            print(f"  {i+1}. ID:{reg['id']} | Cheque #{reg['number']} | {pdf['date']} | ${reg['amount']:,.2f}")
            print(f"      Current: {reg['payee']}")
            print(f"      PDF says: {pdf['payee']}{mismatch}")
    
    # Dry run update
    print("\n=== DRY RUN: UPDATING PAYEES ===")
    updates = update_payees(matched, cur, conn, dry_run=True)
    print(f"Would update {len(updates)} cheque payees")
    
    # Show unmatched
    if unmatched:
        print(f"\n=== UNMATCHED TRANSACTIONS (First 10) ===")
        for i, trans in enumerate(unmatched[:10]):
            print(f"  {i+1}. Cheque #{trans['cheque_number']} | {trans['date']} | {trans['payee'][:40]} | ${trans['amount']:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n=== SUMMARY ===")
    print(f"Total PDF transactions: {len(transactions)}")
    print(f"Matched to register: {len(matched)}")
    print(f"Unmatched: {len(unmatched)}")
    print(f"Payees to update: {len(needs_update)}")
    print("\nTo apply updates, add --write flag")

if __name__ == '__main__':
    import sys
    if '--write' in sys.argv:
        print("[WARN] --write not yet implemented for safety")
    main()
