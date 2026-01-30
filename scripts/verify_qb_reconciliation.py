#!/usr/bin/env python3
"""
Verify QuickBooks reconciliation data against CIBC banking_transactions, receipts, and payments tables.

QuickBooks Format:
  Type Date Num Name Cir Amount Balance
  
Sections:
  - Beginning Balance
  - Cleared Transactions (Deposits/Credits, Cheques/Payments)
  - New Transactions (Deposits/Credits, Cheques/Payments)
  - Ending Balance

Usage:
  python verify_qb_reconciliation.py [--input FILE] [--output-json FILE] [--account ACCT]
"""

import os
import sys
import re
import csv
import json
import psycopg2
from datetime import datetime, date
from decimal import Decimal
from difflib import SequenceMatcher

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def parse_qb_line(line):
    """Parse QuickBooks reconciliation line."""
    # Pattern: Type Date Num Name Cir Amount Balance
    # Type can be: Cheque, Bill Pmt -Cheque, General Journal, Deposit, etc.
    
    parts = line.split()
    if len(parts) < 3:
        return None
    
    # Extract type (may be multi-word like "Bill Pmt -Cheque")
    type_idx = 0
    tx_type = parts[type_idx]
    
    # Check for multi-word types
    if len(parts) > 1 and parts[1].startswith('-'):
        tx_type = parts[0] + ' ' + parts[1]
        type_idx = 1
    elif parts[0] == 'Bill' and parts[1] == 'Pmt':
        tx_type = 'Bill Pmt -Cheque'
        type_idx = 2
    
    # Extract date (MM/DD/YYYY)
    date_idx = type_idx + 1
    if date_idx >= len(parts):
        return None
    
    date_str = parts[date_idx]
    date_match = re.match(r'(\d{2})/(\d{2})/(\d{4})', date_str)
    if not date_match:
        return None
    
    month, day, year = date_match.groups()
    tx_date = date(int(year), int(month), int(day))
    
    # Extract num/name/amount/balance from remaining parts
    remaining = parts[date_idx + 1:]
    
    # Balance is always last (may be negative)
    balance_str = remaining[-1]
    balance = parse_amount(balance_str)
    
    # Amount is second-to-last
    amount_str = remaining[-2] if len(remaining) >= 2 else None
    amount = parse_amount(amount_str) if amount_str else None
    
    # Name/description is everything between num and amount
    # Num is typically first item after date (or may be "DD", "Auto", "Online", etc.)
    num = remaining[0] if remaining else None
    
    # Name is middle section
    name_parts = remaining[1:-2] if len(remaining) > 3 else []
    name = ' '.join(name_parts) if name_parts else None
    
    return {
        'type': tx_type,
        'date': tx_date,
        'num': num,
        'name': name,
        'amount': amount,
        'balance': balance,
        'raw_line': line
    }

def parse_amount(amount_str):
    """Parse amount string to Decimal."""
    if not amount_str:
        return None
    
    # Remove commas, handle negatives
    cleaned = amount_str.replace(',', '').replace('$', '').strip()
    
    try:
        return Decimal(cleaned)
    except:
        return None

def similar(a, b):
    """Calculate similarity ratio between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_banking_match(cur, tx, account_number='3714081'):
    """Find matching banking transaction."""
    # Try exact date + amount match first
    cur.execute("""
        SELECT transaction_id, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date = %s
        AND (
            (debit_amount IS NOT NULL AND ABS(ABS(debit_amount) - ABS(%s)) < 0.01)
            OR (credit_amount IS NOT NULL AND ABS(credit_amount - %s) < 0.01)
        )
    """, (account_number, tx['date'], tx['amount'], tx['amount']))
    
    matches = cur.fetchall()
    
    if len(matches) == 1:
        return {
            'found': True,
            'match_type': 'exact',
            'transaction_id': matches[0][0],
            'description': matches[0][1],
            'db_debit': matches[0][2],
            'db_credit': matches[0][3],
            'db_balance': matches[0][4]
        }
    
    # Multiple matches - try name matching
    if len(matches) > 1 and tx['name']:
        best_match = None
        best_score = 0.0
        
        for m in matches:
            score = similar(tx['name'], m[1])
            if score > best_score:
                best_score = score
                best_match = m
        
        if best_score > 0.6:  # 60% similarity threshold
            return {
                'found': True,
                'match_type': 'fuzzy',
                'transaction_id': best_match[0],
                'description': best_match[1],
                'db_debit': best_match[2],
                'db_credit': best_match[3],
                'db_balance': best_match[4],
                'similarity': best_score
            }
    
    return {
        'found': False,
        'candidates': len(matches)
    }

def find_receipt_match(cur, tx):
    """Find matching receipt for expense."""
    if tx['amount'] is None or tx['amount'] >= 0:
        return None
    
    # Search receipts by date and amount
    cur.execute("""
        SELECT receipt_id, vendor_name, description, gross_amount
        FROM receipts
        WHERE receipt_date = %s
        AND ABS(gross_amount - ABS(%s)) < 0.01
        LIMIT 5
    """, (tx['date'], tx['amount']))
    
    matches = cur.fetchall()
    
    if len(matches) == 1:
        return {
            'found': True,
            'receipt_id': matches[0][0],
            'vendor': matches[0][1],
            'description': matches[0][2],
            'amount': matches[0][3]
        }
    
    if len(matches) > 1 and tx['name']:
        best_match = None
        best_score = 0.0
        
        for m in matches:
            vendor_score = similar(tx['name'], m[1] or '')
            desc_score = similar(tx['name'], m[2] or '')
            score = max(vendor_score, desc_score)
            
            if score > best_score:
                best_score = score
                best_match = m
        
        if best_score > 0.5:
            return {
                'found': True,
                'receipt_id': best_match[0],
                'vendor': best_match[1],
                'description': best_match[2],
                'amount': best_match[3],
                'similarity': best_score
            }
    
    return {
        'found': False,
        'candidates': len(matches)
    }

def find_payment_match(cur, tx):
    """Find matching payment for deposit."""
    if tx['amount'] is None or tx['amount'] <= 0:
        return None
    
    # Search payments by date and amount
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_method, notes
        FROM payments
        WHERE payment_date = %s
        AND ABS(amount - %s) < 0.01
        LIMIT 5
    """, (tx['date'], tx['amount']))
    
    matches = cur.fetchall()
    
    if len(matches) == 1:
        return {
            'found': True,
            'payment_id': matches[0][0],
            'reserve_number': matches[0][1],
            'amount': matches[0][2],
            'method': matches[0][3],
            'notes': matches[0][4]
        }
    
    return {
        'found': False,
        'candidates': len(matches)
    }

def main():
    # Read from stdin or file
    input_file = None
    account_number = '3714081'  # Default to Scotia Bank
    for i, arg in enumerate(sys.argv):
        if arg == '--input' and i+1 < len(sys.argv):
            input_file = sys.argv[i+1]
        elif arg == '--account' and i+1 < len(sys.argv):
            account_number = sys.argv[i+1]
    
    if input_file:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()
    
    print("\n" + "="*80)
    print("QUICKBOOKS RECONCILIATION VERIFICATION")
    print(f"Account: {account_number}")
    print("="*80)
    
    conn = get_conn()
    cur = conn.cursor()
    
    results = {
        'beginning_balance': None,
        'ending_balance': None,
        'transactions': [],
        'summary': {
            'total_transactions': 0,
            'banking_matched': 0,
            'receipt_matched': 0,
            'payment_matched': 0,
            'balance_errors': 0
        }
    }
    
    current_section = None
    expected_balance = Decimal('0.00')
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Detect section headers
        if 'Beginning Balance' in line:
            # Extract amount
            match = re.search(r'([-\d,\.]+)$', line)
            if match:
                results['beginning_balance'] = parse_amount(match.group(1))
                expected_balance = results['beginning_balance']
            continue
        
        if 'Ending Balance' in line:
            match = re.search(r'([-\d,\.]+)\s+([-\d,\.]+)$', line)
            if match:
                results['ending_balance'] = parse_amount(match.group(2))
            continue
        
        if 'Cleared Transactions' in line or 'New Transactions' in line:
            current_section = line
            continue
        
        if 'Type' in line and 'Date' in line and 'Balance' in line:
            # Header row
            continue
        
        if line.startswith('Total ') or line.startswith('total '):
            # Summary line
            continue
        
        # Try to parse as transaction
        tx = parse_qb_line(line)
        if not tx or tx['date'] is None:
            continue
        
        # Find matches in database
        banking_match = find_banking_match(cur, tx, account_number)
        receipt_match = find_receipt_match(cur, tx) if tx['amount'] and tx['amount'] < 0 else None
        payment_match = find_payment_match(cur, tx) if tx['amount'] and tx['amount'] > 0 else None
        
        # Calculate expected balance
        if tx['amount'] is not None:
            expected_balance += tx['amount']
        
        # Check balance match
        balance_ok = True
        if tx['balance'] is not None and expected_balance is not None:
            if abs(tx['balance'] - expected_balance) > Decimal('0.01'):
                balance_ok = False
                results['summary']['balance_errors'] += 1
        
        # Record results
        tx_result = {
            'line_num': line_num,
            'type': tx['type'],
            'date': tx['date'].isoformat(),
            'num': tx['num'],
            'name': tx['name'],
            'amount': float(tx['amount']) if tx['amount'] else None,
            'balance': float(tx['balance']) if tx['balance'] else None,
            'expected_balance': float(expected_balance),
            'balance_ok': balance_ok,
            'banking_match': banking_match,
            'receipt_match': receipt_match,
            'payment_match': payment_match
        }
        
        results['transactions'].append(tx_result)
        results['summary']['total_transactions'] += 1
        
        if banking_match['found']:
            results['summary']['banking_matched'] += 1
        if receipt_match and receipt_match['found']:
            results['summary']['receipt_matched'] += 1
        if payment_match and payment_match['found']:
            results['summary']['payment_matched'] += 1
        
        # Print progress
        status = []
        if banking_match['found']:
            status.append('BANK')
        if receipt_match and receipt_match['found']:
            status.append('RCPT')
        if payment_match and payment_match['found']:
            status.append('PAY')
        if not balance_ok:
            status.append('BAL_ERR')
        
        status_str = ','.join(status) if status else 'UNMATCHED'
        print(f"Line {line_num:4d} | {tx['date']} | ${tx['amount']:>10,.2f} | {status_str:20s} | {tx['name'][:40] if tx['name'] else ''}")
    
    cur.close()
    conn.close()
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total transactions: {results['summary']['total_transactions']}")
    print(f"Banking matched: {results['summary']['banking_matched']} ({results['summary']['banking_matched']/max(results['summary']['total_transactions'],1)*100:.1f}%)")
    print(f"Receipt matched: {results['summary']['receipt_matched']}")
    print(f"Payment matched: {results['summary']['payment_matched']}")
    print(f"Balance errors: {results['summary']['balance_errors']}")
    
    if results['beginning_balance'] is not None:
        print(f"\nBeginning balance: ${results['beginning_balance']:,.2f}")
    if results['ending_balance'] is not None:
        print(f"Ending balance: ${results['ending_balance']:,.2f}")
    print(f"Calculated balance: ${expected_balance:,.2f}")
    
    # Output JSON if requested
    if '--output-json' in sys.argv:
        idx = sys.argv.index('--output-json')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
            
            # Convert Decimal to float for JSON serialization
            def decimal_default(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=decimal_default)
            print(f"\nJSON output written to {output_file}")

if __name__ == '__main__':
    main()
