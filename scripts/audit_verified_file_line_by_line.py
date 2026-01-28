#!/usr/bin/env python3
"""
Line-by-line audit of 2012_cibc_complete_running_balance_verification.md
Validates EVERY transaction line against database with detailed reporting.
"""

import psycopg2
import os
import re
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def parse_verified_file():
    """Parse every transaction line from verified file."""
    filepath = r'L:\limo\reports\2012_cibc_complete_running_balance_verification.md'
    
    transactions = []
    current_month = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and dividers
            if not line or line.startswith('---') or line.startswith('**'):
                continue
            
            # Detect main month sections (## January 2012)
            month_match = re.match(r'^##\s+(\w+)\s+2012', line)
            if month_match:
                current_month = month_match.group(1)
                continue
            
            # Parse transaction table rows
            # Format: | Date | Description | Type | Amount | Prev Balance | Expected Balance | PDF Balance | Status |
            if line.startswith('|') and '|' in line[1:]:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) < 8:
                    continue
                
                date_str = parts[1]
                description = parts[2]
                tx_type = parts[3]
                amount_str = parts[4]
                pdf_balance_str = parts[7]
                
                # Skip header rows and separator rows
                if 'Date' in date_str or '---' in date_str or 'Description' in description:
                    continue
                
                # Skip opening/closing/balance forward entries (no amount)
                if 'Opening balance' in description or 'Closing balance' in description or 'Balance forward' in description:
                    continue
                
                # Skip rows without amounts
                if not amount_str or amount_str in ['-', '']:
                    continue
                
                # Parse date (format: Jan 3 or Jan 03)
                if current_month and date_str:
                    try:
                        # Extract day number from date column
                        day_match = re.search(r'(\d+)', date_str)
                        if not day_match:
                            continue
                        
                        day = int(day_match.group(1))
                        
                        # Map month names to numbers
                        month_map = {
                            'January': 1, 'Jan': 1,
                            'February': 2, 'Feb': 2,
                            'March': 3, 'Mar': 3,
                            'April': 4, 'Apr': 4,
                            'May': 5,
                            'June': 6, 'Jun': 6,
                            'July': 7, 'Jul': 7,
                            'August': 8, 'Aug': 8,
                            'September': 9, 'Sep': 9,
                            'October': 10, 'Oct': 10,
                            'November': 11, 'Nov': 11,
                            'December': 12, 'Dec': 12
                        }
                        
                        month_num = month_map.get(current_month)
                        if not month_num:
                            continue
                        
                        tx_date = datetime(2012, month_num, day).date()
                        
                        # Parse amount
                        amount = None
                        amount_clean = amount_str.replace(',', '').replace('$', '').strip()
                        if amount_clean:
                            try:
                                amount = float(amount_clean)
                            except:
                                pass
                        
                        # Parse balance
                        balance = None
                        balance_clean = pdf_balance_str.replace(',', '').replace('$', '').strip()
                        # Remove status markers
                        balance_clean = re.sub(r'\[OK\].*|\[WARN\].*', '', balance_clean).strip()
                        if balance_clean:
                            try:
                                balance = float(balance_clean)
                            except:
                                pass
                        
                        if tx_date and description and amount is not None:
                            transactions.append({
                                'line_num': line_num,
                                'date': tx_date,
                                'description': description,
                                'type': tx_type,
                                'amount': amount,
                                'balance': balance,
                                'month': current_month
                            })
                    
                    except Exception as e:
                        # Skip malformed lines
                        pass
    
    return transactions

def find_in_database(cur, tx):
    """Find transaction in database with multiple matching strategies."""
    
    # Strategy 1: Exact match (date + description + amount)
    cur.execute("""
        SELECT transaction_id, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date = %s
        AND description = %s
        AND (
            (debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.01)
            OR (credit_amount IS NOT NULL AND ABS(credit_amount - %s) < 0.01)
        )
    """, (tx['date'], tx['description'], tx['amount'], tx['amount']))
    
    exact_match = cur.fetchone()
    if exact_match:
        return {
            'found': True,
            'match_type': 'exact',
            'transaction_id': exact_match[0],
            'db_description': exact_match[1],
            'db_debit': exact_match[2],
            'db_credit': exact_match[3],
            'db_balance': exact_match[4]
        }
    
    # Strategy 2: Fuzzy description match (date + amount + similar description)
    # Get all transactions on same date with same amount
    cur.execute("""
        SELECT transaction_id, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date = %s
        AND (
            (debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.01)
            OR (credit_amount IS NOT NULL AND ABS(credit_amount - %s) < 0.01)
        )
    """, (tx['date'], tx['amount'], tx['amount']))
    
    candidates = cur.fetchall()
    
    # Check for partial description matches
    tx_desc_lower = tx['description'].lower()
    for candidate in candidates:
        db_desc_lower = candidate[1].lower()
        
        # Check if key words match
        tx_words = set(tx_desc_lower.split())
        db_words = set(db_desc_lower.split())
        
        # If significant word overlap, consider it a match
        common_words = tx_words & db_words
        if len(common_words) >= 2:  # At least 2 words in common
            return {
                'found': True,
                'match_type': 'fuzzy',
                'transaction_id': candidate[0],
                'db_description': candidate[1],
                'db_debit': candidate[2],
                'db_credit': candidate[3],
                'db_balance': candidate[4]
            }
    
    # Strategy 3: Date + amount only (for heavily abbreviated descriptions)
    if len(candidates) == 1:  # Only one transaction on that date with that amount
        return {
            'found': True,
            'match_type': 'date_amount',
            'transaction_id': candidates[0][0],
            'db_description': candidates[0][1],
            'db_debit': candidates[0][2],
            'db_credit': candidates[0][3],
            'db_balance': candidates[0][4]
        }
    
    return {
        'found': False,
        'match_type': None,
        'candidates': len(candidates)
    }

def main():
    print("\n" + "="*80)
    print("LINE-BY-LINE AUDIT: 2012 CIBC Verified File vs Database")
    print("="*80)
    print("\nParsing verified file...")
    
    transactions = parse_verified_file()
    print(f"Found {len(transactions)} transaction lines in verified file\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Track results
    found_exact = []
    found_fuzzy = []
    found_date_amount = []
    not_found = []
    
    current_month = None
    
    for i, tx in enumerate(transactions, 1):
        # Print month header when month changes
        if tx['month'] != current_month:
            current_month = tx['month']
            print(f"\n{'='*80}")
            print(f"{current_month} 2012")
            print(f"{'='*80}")
        
        result = find_in_database(cur, tx)
        
        # Format output
        date_str = tx['date'].strftime('%Y-%m-%d')
        type_indicator = 'W' if tx['type'] == 'W' else 'D'
        
        if result['found']:
            match_symbol = {
                'exact': '[OK]',
                'fuzzy': '[FZ]',
                'date_amount': '[DA]'
            }[result['match_type']]
            
            balance_match = ""
            if tx['balance'] is not None and result['db_balance'] is not None:
                balance_diff = abs(tx['balance'] - float(result['db_balance']))
                if balance_diff < 0.01:
                    balance_match = " [BAL_OK]"
                else:
                    balance_match = f" [BAL_DIFF ${balance_diff:.2f}]"
            
            print(f"{match_symbol} Line {tx['line_num']:4d} | {date_str} | {type_indicator} ${tx['amount']:>8.2f} | ID {result['transaction_id']:5d}{balance_match}")
            print(f"   File: {tx['description'][:70]}")
            if result['match_type'] != 'exact':
                print(f"   DB:   {result['db_description'][:70]}")
            
            if result['match_type'] == 'exact':
                found_exact.append(tx)
            elif result['match_type'] == 'fuzzy':
                found_fuzzy.append(tx)
            else:
                found_date_amount.append(tx)
        
        else:
            print(f"[MISS] Line {tx['line_num']:4d} | {date_str} | {type_indicator} ${tx['amount']:>8.2f} | NOT FOUND")
            print(f"   File: {tx['description'][:70]}")
            if result.get('candidates', 0) > 0:
                print(f"   Note: {result['candidates']} similar transactions found but no match")
            not_found.append(tx)
    
    # Summary
    print("\n" + "="*80)
    print("AUDIT SUMMARY")
    print("="*80)
    print(f"Total lines in verified file: {len(transactions)}")
    
    if len(transactions) > 0:
        print(f"\nMatches:")
        print(f"  [OK] Exact matches:         {len(found_exact):4d} ({len(found_exact)/len(transactions)*100:5.1f}%)")
        print(f"  [FZ] Fuzzy matches:         {len(found_fuzzy):4d} ({len(found_fuzzy)/len(transactions)*100:5.1f}%)")
        print(f"  [DA] Date+Amount only:      {len(found_date_amount):4d} ({len(found_date_amount)/len(transactions)*100:5.1f}%)")
        print(f"  -------------------------------------")
        total_found = len(found_exact) + len(found_fuzzy) + len(found_date_amount)
        print(f"  Total found:                {total_found:4d} ({total_found/len(transactions)*100:5.1f}%)")
        print(f"\n  [MISS] Not found:           {len(not_found):4d} ({len(not_found)/len(transactions)*100:5.1f}%)")
    else:
        print("\n[WARN] No transaction lines found in verified file!")
        print("   Check that the file exists and has the expected format.")
    
    if not_found:
        print(f"\n{'='*80}")
        print("MISSING TRANSACTIONS DETAIL")
        print(f"{'='*80}")
        for tx in not_found:
            print(f"\nLine {tx['line_num']} | {tx['date']} | ${tx['amount']:.2f}")
            print(f"  Description: {tx['description']}")
            print(f"  Type: {tx['type']}")
            if tx['balance']:
                print(f"  Balance: ${tx['balance']:.2f}")
    
    print(f"\n{'='*80}")
    if len(not_found) == 0:
        print("[PASS] AUDIT PASSED: All verified file transactions found in database")
    else:
        print(f"[WARN] AUDIT INCOMPLETE: {len(not_found)} transactions not found in database")
    print(f"{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
