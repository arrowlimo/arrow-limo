#!/usr/bin/env python
"""
Extract Canadian Tire purchases from OCR'd Mastercard statements.
Adds them to mastercard_business_expenses.csv for review/import.
"""

import re
import csv
from pathlib import Path
from datetime import datetime, date
import PyPDF2

def extract_transactions_from_ocr_pdf(pdf_path):
    """Extract transaction lines from OCR'd Triangle Mastercard PDF."""
    transactions = []
    
    try:
        reader = PyPDF2.PdfReader(str(pdf_path))
        full_text = ""
        for page in reader.pages:
            # Some pages may return None from extract_text; guard against that
            page_text = page.extract_text() or ""
            full_text += page_text + "\n"
        
        # Get statement date from filename: YYYY-MM-DD
        filename = pdf_path.name
        date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', filename)
        if date_match:
            statement_year = int(date_match.group(1))
            statement_month = int(date_match.group(2))
            statement_day = int(date_match.group(3))
            statement_date = date(statement_year, statement_month, statement_day)
        else:
            return []
        
        # Regex that spans across potential line wraps for purchases rows:
        # Captures: trans month/day, post month/day, description, optional province, amount
        mon = 'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
        pattern = re.compile(
            rf'({mon})\s+(\d{{1,2}})\s+({mon})\s+(\d{{1,2}})\s+(.*?)\s+(?:[A-Z]{{2}})?\s*([A-Z]{{0,2}}-?[\d,]*\.?\d{{2}})(?=\s+({mon})\s+\d{{1,2}}\s+({mon})\s+\d{{1,2}}|\s+WAYS TO PAY|$)',
            re.DOTALL
        )

        # Merchant alias patterns for Canadian Tire and Gas+ variants
        ct_alias = re.compile(r'(CANADIAN\s+TIRE|CDN\s*TIRE|CAN\s*TIRE|CT\s*GAS|GAS\+|TIRE\s*GAS|CANADIAN\s+TIRE\s+GAS\+|CDN\s*TIRE\s*STORE)', re.IGNORECASE)

        for m in pattern.finditer(full_text):
            trans_month_abbr, trans_day_str, _, _, desc_text, amount_raw, *_ = m.groups()
            # Normalize description and repair split whitespace
            desc_text_norm = ' '.join(desc_text.split())
            if not ct_alias.search(desc_text_norm):
                continue

            # Amount: strip any leading province letters that got merged
            amount_str = amount_raw
            amount_str = re.sub(r'^[A-Z]{1,2}', '', amount_str)  # drop leading letters like 'AB'
            try:
                amount_val = float(amount_str.replace(',', ''))
            except Exception:
                continue

            # Determine transaction date relative to statement date
            try:
                t_month = datetime.strptime(trans_month_abbr, '%b').month
            except Exception:
                continue
            t_day = int(trans_day_str)
            txn_year = statement_year
            txn_date = date(txn_year, t_month, t_day)
            if txn_date > statement_date:
                txn_year -= 1
                txn_date = date(txn_year, t_month, t_day)

            transactions.append({
                'receipt_date': txn_date.strftime('%Y-%m-%d'),
                'vendor_name': 'Canadian Tire',
                'gross_amount': amount_val,
                'description': desc_text_norm,
                'category': 'maintenance',
                'payment_method': 'Mastercard',
                'comment': 'Triangle Mastercard (David)',
                'business_personal': 'business',
                'employee_id': ''
            })
    
    except Exception as e:
        print(f"Error processing {pdf_path.name}: {e}")
    
    return transactions

def main():
    # Find all OCR'd PDFs
    pdf_dir = Path('l:/limo/pdf')
    ocr_pdfs = sorted(pdf_dir.glob('*mastercard*_ocred.pdf'))
    
    print(f"Found {len(ocr_pdfs)} OCR'd Mastercard statements")
    print("=" * 80)
    
    all_transactions = []
    
    for pdf_path in ocr_pdfs:
        print(f"Processing: {pdf_path.name}...", end=' ')
        transactions = extract_transactions_from_ocr_pdf(pdf_path)
        
        if transactions:
            all_transactions.extend(transactions)
            print(f"✓ {len(transactions)} Canadian Tire purchases")
        else:
            print("(no Canadian Tire purchases)")
    
    print(f"\n{'=' * 80}")
    print(f"Total Canadian Tire purchases found: {len(all_transactions)}")
    
    if not all_transactions:
        print("\n[WARN] No Canadian Tire purchases found in statements")
        return
    
    # Read existing CSV
    csv_path = Path('l:/limo/mastercard_business_expenses.csv')
    
    # Append to CSV
    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        fieldnames = [
            'receipt_date', 'vendor_name', 'gross_amount', 'description',
            'category', 'payment_method', 'comment', 'business_personal', 'employee_id'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        for txn in sorted(all_transactions, key=lambda x: x['receipt_date']):
            writer.writerow(txn)
    
    print(f"\n[OK] Added {len(all_transactions)} Canadian Tire purchases to: {csv_path}")
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Review the CSV file - check if purchases are business expenses")
    print("2. Adjust 'category' if needed (fuel, maintenance, office, etc.)")
    print("3. Change 'business_personal' to 'personal' for any personal purchases")
    print("4. Run import:")
    print("   python l:\\limo\\scripts\\import_mastercard_expenses.py --import --csv \"l:\\limo\\mastercard_business_expenses.csv\" --write")
    print("=" * 80)

if __name__ == '__main__':
    main()
