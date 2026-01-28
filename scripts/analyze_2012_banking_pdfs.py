#!/usr/bin/env python3
"""
Parse 2012 Banking PDFs and Identify Missing Data

Analyzes all 2012 banking PDFs (CIBC, Scotia, QuickBooks) and compares
against existing database to identify missing transactions.
"""

import pdfplumber
import psycopg2
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import re
from collections import defaultdict
import json

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def extract_date_patterns(text):
    """Extract dates in various formats."""
    dates = []
    
    # YYYY-MM-DD
    dates.extend(re.findall(r'(\d{4}-\d{2}-\d{2})', text))
    
    # MM/DD/YYYY or MM/DD/YY
    dates.extend(re.findall(r'(\d{1,2}/\d{1,2}/\d{2,4})', text))
    
    # DD-MMM-YYYY (e.g., 15-Jan-2012)
    dates.extend(re.findall(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', text))
    
    return dates

def extract_amounts(text):
    """Extract dollar amounts with sign context and return token list.
    Returns list of dicts: {'value': float, 'sign': '+/-/None', 'raw': str, 'index': int}
    """
    tokens = []
    pattern = re.compile(r'(?P<sign>[+-])?\$?\s*(?P<num>[\d,]+\.\d{2})')
    for m in pattern.finditer(text):
        raw = m.group(0)
        sign = m.group('sign')
        num = m.group('num')
        value = float(num.replace(',', ''))
        tokens.append({'value': value, 'sign': sign, 'raw': raw.strip(), 'index': m.start()})
    return tokens

def derive_transaction_amounts(line, amount_tokens):
    """Apply heuristics to remove running balance / duplicate amounts and keep probable transaction amounts.
    Heuristics:
      - Use explicit signed (negative) amount if present (store absolute value).
      - Drop consecutive duplicate amounts (likely amount + balance repetition).
      - If multiple amounts and last is >5x first, treat first as transaction and drop last (large running balance).
      - If two amounts and identical, keep one.
      - For 'Deposit', 'Cheque', 'Bill Pmt', 'General Journal' lines: prefer first token.
      - Fallback: first token only.
    Returns list of float values (transaction amounts) or empty list.
    """
    if not amount_tokens:
        return []
    # Remove consecutive duplicates
    dedup = []
    for i, t in enumerate(amount_tokens):
        if i > 0 and t['value'] == amount_tokens[i-1]['value']:
            continue
        dedup.append(t)
    tokens = dedup
    if len(tokens) == 1:
        return [tokens[0]['value']]
    negatives = [t for t in tokens if t['sign'] == '-']
    if negatives:
        return [abs(negatives[0]['value'])]
    # Large final balance heuristic
    if tokens[-1]['value'] > 5 * tokens[0]['value']:
        return [tokens[0]['value']]
    # Two identical amounts
    if len(tokens) == 2 and tokens[0]['value'] == tokens[1]['value']:
        return [tokens[0]['value']]
    lowered = line.lower()
    if any(kw in lowered for kw in ['deposit', 'cheque', 'bill pmt', 'general journal']):
        return [tokens[0]['value']]
    # Fallback: choose first whose value is not extreme (e.g., < 100000)
    for t in tokens:
        if t['value'] < 100000:
            return [t['value']]
    return [tokens[0]['value']]

def parse_cibc_statement(pdf_path):
    """Parse CIBC bank statement PDF."""
    transactions = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            
            # Look for transaction lines
            lines = text.split('\n')
            for line in lines:
                # Skip headers and summaries
                if any(skip in line.lower() for skip in ['balance', 'statement', 'account', 'page', 'total']):
                    continue
                
                # Extract date
                dates = extract_date_patterns(line)
                if not dates:
                    continue
                
                # Extract amounts
                amount_tokens = extract_amounts(line)
                if not amount_tokens:
                    continue
                
                # Parse transaction
                for date_str in dates:
                    try:
                        if '/' in date_str:
                            parts = date_str.split('/')
                            if len(parts[2]) == 2:
                                date_str = f"{parts[0]}/{parts[1]}/20{parts[2]}"
                            txn_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                        elif '-' in date_str and len(date_str) > 10:
                            txn_date = datetime.strptime(date_str, '%d-%b-%Y').date()
                        else:
                            txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        
                        if txn_date.year == 2012:
                            txn_amounts = derive_transaction_amounts(line, amount_tokens)
                            if txn_amounts:
                                transactions.append({
                                    'date': txn_date,
                                    'description': line.strip(),
                                    'amounts': txn_amounts,
                                    'source': pdf_path.name,
                                    'page': page_num
                                })
                    except:
                        pass
    
    return transactions

def parse_scotia_statement(pdf_path):
    """Parse Scotia bank statement PDF."""
    transactions = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            
            # Scotia statements have different format
            lines = text.split('\n')
            for line in lines:
                # Look for transaction patterns
                if any(skip in line.lower() for skip in ['balance', 'statement', 'account', 'page']):
                    continue
                
                dates = extract_date_patterns(line)
                amount_tokens = extract_amounts(line)
                
                if dates and amount_tokens:
                    for date_str in dates:
                        try:
                            if '/' in date_str:
                                parts = date_str.split('/')
                                if len(parts[2]) == 2:
                                    date_str = f"{parts[0]}/{parts[1]}/20{parts[2]}"
                                txn_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                            else:
                                txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                            
                            if txn_date.year == 2012:
                                txn_amounts = derive_transaction_amounts(line, amount_tokens)
                                if txn_amounts:
                                    transactions.append({
                                        'date': txn_date,
                                        'description': line.strip(),
                                        'amounts': txn_amounts,
                                        'source': pdf_path.name,
                                        'page': page_num
                                    })
                        except:
                            pass
    
    return transactions

def parse_qb_reconciliation(pdf_path):
    """Parse QuickBooks reconciliation PDF."""
    transactions = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Try to extract tables
            tables = page.extract_tables()
            
            if tables:
                for table in tables:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        
                        # Look for date in first column
                        date_str = str(row[0]) if row[0] else ''
                        dates = extract_date_patterns(date_str)
                        
                        if dates:
                            # Look for amounts in row
                            row_text = ' '.join([str(cell) for cell in row if cell])
                            amount_tokens = extract_amounts(row_text)
                            
                            if amount_tokens:
                                for date_str in dates:
                                    try:
                                        if '/' in date_str:
                                            parts = date_str.split('/')
                                            if len(parts[2]) == 2:
                                                date_str = f"{parts[0]}/{parts[1]}/20{parts[2]}"
                                            txn_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                                        else:
                                            txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                        
                                        if txn_date.year == 2012:
                                            txn_amounts = derive_transaction_amounts(row_text, amount_tokens)
                                            if txn_amounts:
                                                transactions.append({
                                                    'date': txn_date,
                                                    'description': row_text,
                                                    'amounts': txn_amounts,
                                                    'source': pdf_path.name,
                                                    'page': page_num
                                                })
                                    except:
                                        pass
            
            # Also try text extraction
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                for line in lines:
                    dates = extract_date_patterns(line)
                    amount_tokens = extract_amounts(line)
                    
                    if dates and amount_tokens:
                        for date_str in dates:
                            try:
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts[2]) == 2:
                                        date_str = f"{parts[0]}/{parts[1]}/20{parts[2]}"
                                    txn_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                                else:
                                    txn_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                                
                                if txn_date.year == 2012:
                                    txn_amounts = derive_transaction_amounts(line, amount_tokens)
                                    if txn_amounts:
                                        transactions.append({
                                            'date': txn_date,
                                            'description': line.strip(),
                                            'amounts': txn_amounts,
                                            'source': pdf_path.name,
                                            'page': page_num
                                        })
                            except:
                                pass
    
    return transactions

def check_transaction_exists(cur, date, amount, tolerance=0.01):
    """Check if transaction exists in database."""
    cur.execute("""
        SELECT transaction_id, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date = %s
          AND (
              ABS(COALESCE(debit_amount, 0) - %s) <= %s
              OR ABS(COALESCE(credit_amount, 0) - %s) <= %s
          )
    """, (date, amount, tolerance, amount, tolerance))
    
    return cur.fetchall()

def analyze_pdf_file(pdf_path, cur):
    """Analyze a single PDF file."""
    print(f"\n{'='*80}")
    print(f"Analyzing: {pdf_path.name}")
    print(f"{'='*80}")
    
    # Determine parser based on filename
    if 'cibc' in pdf_path.name.lower():
        transactions = parse_cibc_statement(pdf_path)
        account = 'CIBC'
    elif 'scotia' in pdf_path.name.lower():
        transactions = parse_scotia_statement(pdf_path)
        account = 'Scotia'
    elif 'quickbooks' in pdf_path.name.lower():
        transactions = parse_qb_reconciliation(pdf_path)
        account = 'QuickBooks'
    else:
        transactions = parse_cibc_statement(pdf_path)  # Default
        account = 'Unknown'
    
    print(f"Account Type: {account}")
    print(f"Transactions Extracted: {len(transactions)}")
    
    if not transactions:
        print(f"[WARN] No transactions found in PDF")
        return {
            'file': pdf_path.name,
            'account': account,
            'extracted': 0,
            'missing': [],
            'missing_count': 0,
            'found': 0,
            'match_rate': 0
        }
    
    # Group by date
    by_date = defaultdict(list)
    for txn in transactions:
        by_date[txn['date']].append(txn)
    
    print(f"Date Range: {min(by_date.keys())} to {max(by_date.keys())}")
    print(f"Unique Dates: {len(by_date)}")
    
    # Check which transactions are missing
    missing = []
    found_count = 0
    
    for date, txns in sorted(by_date.items()):
        for txn in txns:
            for amount in txn['amounts']:
                matches = check_transaction_exists(cur, date, amount)
                
                if matches:
                    found_count += 1
                else:
                    missing.append({
                        'date': str(date),
                        'amount': amount,
                        'description': txn['description'][:100],
                        'source': txn['source'],
                        'page': txn['page']
                    })
    
    total_amounts = sum(len(txn['amounts']) for txns in by_date.values() for txn in txns)
    match_rate = (found_count / total_amounts * 100) if total_amounts > 0 else 0
    
    print(f"\n📊 Analysis Results:")
    print(f"   Total Amount Entries: {total_amounts}")
    print(f"   Found in Database: {found_count}")
    print(f"   Missing from Database: {len(missing)}")
    print(f"   Match Rate: {match_rate:.1f}%")
    
    if missing:
        print(f"\n[WARN] Sample Missing Transactions (first 10):")
        for txn in missing[:10]:
            print(f"   {txn['date']} | ${txn['amount']:,.2f} | {txn['description'][:60]}")
    
    return {
        'file': pdf_path.name,
        'account': account,
        'extracted': total_amounts,
        'found': found_count,
        'missing_count': len(missing),
        'match_rate': match_rate,
        'missing': missing
    }

def main():
    pdf_files = [
        "L:\\limo\\pdf\\2012cibc banking jun-dec_ocred.pdf",
        "L:\\limo\\pdf\\2012 quickbooks cibc bank reconciliation detailed_ocred.pdf",
        "L:\\limo\\pdf\\2012 quickbooks cibc bank reconciliation summary_ocred.pdf",
        "L:\\limo\\pdf\\2012 quickbooks monthly summary4_ocred.pdf",
        "L:\\limo\\pdf\\2012 quickbooks scotiabank_ocred dec.pdf",
        "L:\\limo\\pdf\\2012 scotia bank statements 2_ocred.pdf",
        "L:\\limo\\pdf\\2012 scotia bank statements 3_ocred.pdf",
        "L:\\limo\\pdf\\2012 scotia bank statements 4_ocred.pdf",
        "L:\\limo\\pdf\\2012 scotia bank statements 5_ocred.pdf",
        "L:\\limo\\pdf\\2012 scotia bank statements 6_ocred.pdf",
        "L:\\limo\\pdf\\2012 scotia bank statements_ocred.pdf",
        "L:\\limo\\pdf\\2012cibc banking apr- may_ocred.pdf",
        "L:\\limo\\pdf\\2012cibc banking jan-mar_ocred.pdf"
    ]
    
    print("\n" + "="*80)
    print("2012 BANKING PDF ANALYSIS - MISSING DATA IDENTIFICATION")
    print("="*80)
    
    conn = get_conn()
    cur = conn.cursor()
    
    results = []
    
    for pdf_path_str in pdf_files:
        pdf_path = Path(pdf_path_str)
        
        if not pdf_path.exists():
            print(f"\n[WARN] File not found: {pdf_path.name}")
            continue
        
        try:
            result = analyze_pdf_file(pdf_path, cur)
            results.append(result)
        except Exception as e:
            print(f"\n[FAIL] Error processing {pdf_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    cur.close()
    conn.close()
    
    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY - ALL BANKING PDFs")
    print(f"{'='*80}")
    
    print(f"\n📁 Files Analyzed: {len(results)}")
    
    total_extracted = sum(r['extracted'] for r in results)
    total_found = sum(r['found'] for r in results)
    total_missing = sum(r['missing_count'] for r in results)
    
    print(f"\n📊 Overall Statistics:")
    print(f"   Total Transactions Extracted: {total_extracted:,}")
    print(f"   Found in Database: {total_found:,}")
    print(f"   Missing from Database: {total_missing:,}")
    
    if total_extracted > 0:
        overall_match = (total_found / total_extracted * 100)
        print(f"   Overall Match Rate: {overall_match:.1f}%")
    
    print(f"\n📋 File-by-File Results:")
    print(f"   {'File':<60} {'Extracted':>10} {'Found':>8} {'Missing':>8} {'Rate':>6}")
    print(f"   {'-'*100}")
    
    for r in results:
        print(f"   {r['file']:<60} {r['extracted']:>10} {r['found']:>8} {r['missing_count']:>8} {r['match_rate']:>5.1f}%")
    
    # Files with most missing data
    if results:
        sorted_by_missing = sorted(results, key=lambda x: x['missing_count'], reverse=True)
        
        print(f"\n[WARN] Files with Most Missing Transactions:")
        for r in sorted_by_missing[:5]:
            if r['missing_count'] > 0:
                print(f"   {r['file']}: {r['missing_count']} missing transactions")
    
    # Save detailed results
    output_path = Path('l:/limo/reports/2012_banking_pdf_analysis.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'files_analyzed': len(results),
            'total_extracted': total_extracted,
            'total_found': total_found,
            'total_missing': total_missing,
            'overall_match_rate': (total_found / total_extracted * 100) if total_extracted > 0 else 0
        },
        'file_results': results
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Detailed results saved to: {output_path}")
    
    print(f"\n💡 Next Steps:")
    print(f"   • Review missing transactions in JSON output")
    print(f"   • Determine if missing transactions should be imported")
    print(f"   • Check if missing data is already in database under different dates/amounts")
    print(f"   • Investigate files with low match rates")

if __name__ == '__main__':
    main()
