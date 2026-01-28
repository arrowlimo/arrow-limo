#!/usr/bin/env python3
"""
Complete audit of 2012 CIBC verified file vs banking_transactions database.
Parses the verified markdown file and compares every transaction line-by-line.
"""

import psycopg2
import os
import re
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def parse_amount(amount_str):
    """Parse amount string to float, handling commas and negatives."""
    if not amount_str or amount_str == '-' or amount_str == '':
        return None
    amount_str = amount_str.strip().replace(',', '').replace('$', '')
    try:
        return float(amount_str)
    except ValueError:
        return None

def parse_verified_file(filepath):
    """Parse the verified markdown file and extract all transactions."""
    transactions = []
    current_month = None
    current_year = '2012'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detect month headers (e.g., "## January 2012", "## April 2012")
        month_match = re.match(r'^##\s+(\w+)\s+2012', line)
        if month_match:
            current_month = month_match.group(1)
            i += 1
            continue
        
        # Detect day headers (e.g., "### Jan 3", "### Mar 19")
        day_match = re.match(r'^###\s+(\w+)\s+(\d+)', line)
        if day_match:
            month_abbr = day_match.group(1)
            day = day_match.group(2).zfill(2)
            # Convert month abbreviation to number
            month_map = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
            }
            month_num = month_map.get(month_abbr[:3], '00')
            current_date = f"2012-{month_num}-{day}"
            i += 1
            continue
        
        # Parse transaction table rows (markdown format)
        # | Date  | Description | Type | Amount | Prev Balance | Expected Balance | PDF Balance | Status |
        if line.startswith('|') and '|' in line and current_month:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 8:
                date_str = parts[1]
                description = parts[2]
                tx_type = parts[3]
                amount_str = parts[4]
                pdf_balance_str = parts[7]
                
                # Skip header rows and balance forward rows
                if date_str in ['Date', '-------', ''] or description in ['Description', '-------', '']:
                    i += 1
                    continue
                
                if 'balance forward' in description.lower() or 'opening balance' in description.lower():
                    i += 1
                    continue
                
                # Parse date
                if date_str and date_str not in ['-', '']:
                    # Handle formats like "Jan 3", "Mar 19", or full dates
                    date_match = re.match(r'(\w+)\s+(\d+)', date_str)
                    if date_match:
                        month_abbr = date_match.group(1)
                        day = date_match.group(2).zfill(2)
                        month_map = {
                            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                        }
                        month_num = month_map.get(month_abbr[:3], '00')
                        tx_date = f"2012-{month_num}-{day}"
                    else:
                        tx_date = current_date
                else:
                    tx_date = current_date
                
                # Parse amount and type
                amount = parse_amount(amount_str)
                if amount and amount > 0:
                    is_withdrawal = (tx_type == 'W')
                    is_deposit = (tx_type == 'D')
                    
                    if is_withdrawal or is_deposit:
                        transactions.append({
                            'date': tx_date,
                            'description': description.strip(),
                            'type': tx_type,
                            'amount': amount,
                            'debit': amount if is_withdrawal else None,
                            'credit': amount if is_deposit else None,
                            'pdf_balance': parse_amount(pdf_balance_str),
                            'month': current_month,
                            'line_num': i + 1
                        })
        
        i += 1
    
    return transactions

def get_database_transactions(conn, account_number='0228362', year='2012'):
    """Get all transactions from database for the account and year."""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date, transaction_id
    """, (account_number, int(year)))
    
    transactions = []
    for row in cur.fetchall():
        transactions.append({
            'id': row[0],
            'date': str(row[1]),
            'description': row[2] or '',
            'debit': float(row[3]) if row[3] else None,
            'credit': float(row[4]) if row[4] else None,
            'balance': float(row[5]) if row[5] else None
        })
    
    cur.close()
    return transactions

def normalize_description(desc):
    """Normalize description for comparison."""
    # Remove extra whitespace
    desc = ' '.join(desc.split())
    # Remove common OCR artifacts
    desc = desc.replace('  ', ' ')
    # Uppercase for comparison
    return desc.upper().strip()

def fuzzy_match_description(desc1, desc2, threshold=0.7):
    """Check if two descriptions are similar enough."""
    norm1 = normalize_description(desc1)
    norm2 = normalize_description(desc2)
    
    # Exact match
    if norm1 == norm2:
        return True
    
    # Check if one contains the other
    if norm1 in norm2 or norm2 in norm1:
        return True
    
    # Check key words (for cheques, extract cheque number)
    if 'CHEQUE' in norm1 and 'CHEQUE' in norm2:
        num1 = re.search(r'CHEQUE\s+(\d+)', norm1)
        num2 = re.search(r'CHEQUE\s+(\d+)', norm2)
        if num1 and num2 and num1.group(1) == num2.group(1):
            return True
    
    # Similar length and some overlap
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    if len(words1) > 0 and len(words2) > 0:
        overlap = len(words1 & words2)
        similarity = overlap / min(len(words1), len(words2))
        return similarity >= threshold
    
    return False

def match_transactions(verified_txs, db_txs):
    """Match verified file transactions with database transactions."""
    matches = []
    missing_from_db = []
    extra_in_db = []
    
    # Group by date for faster lookup
    db_by_date = defaultdict(list)
    for tx in db_txs:
        db_by_date[tx['date']].append(tx)
    
    used_db_ids = set()
    
    print(f"\nMatching {len(verified_txs)} verified transactions against {len(db_txs)} database transactions...")
    print("=" * 100)
    
    for vtx in verified_txs:
        matched = False
        vtx_date = vtx['date']
        
        # Look for exact or fuzzy match on same date
        for dtx in db_by_date.get(vtx_date, []):
            if dtx['id'] in used_db_ids:
                continue
            
            # Check amount match
            amount_match = False
            if vtx['debit'] and dtx['debit']:
                amount_match = abs(vtx['debit'] - dtx['debit']) < 0.01
            elif vtx['credit'] and dtx['credit']:
                amount_match = abs(vtx['credit'] - dtx['credit']) < 0.01
            
            # Check description match
            desc_match = fuzzy_match_description(vtx['description'], dtx['description'])
            
            if amount_match and desc_match:
                matches.append({
                    'verified': vtx,
                    'database': dtx,
                    'status': 'EXACT_MATCH'
                })
                used_db_ids.add(dtx['id'])
                matched = True
                break
            elif amount_match:
                # Amount matches but description differs
                matches.append({
                    'verified': vtx,
                    'database': dtx,
                    'status': 'AMOUNT_MATCH_ONLY'
                })
                used_db_ids.add(dtx['id'])
                matched = True
                break
        
        if not matched:
            missing_from_db.append(vtx)
    
    # Find database transactions not matched
    for dtx in db_txs:
        if dtx['id'] not in used_db_ids:
            extra_in_db.append(dtx)
    
    return matches, missing_from_db, extra_in_db

def main():
    print("=" * 100)
    print("2012 CIBC VERIFIED FILE vs DATABASE AUDIT")
    print("=" * 100)
    print(f"Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Verified File: L:\\limo\\reports\\2012_cibc_complete_running_balance_verification.md")
    print(f"Database: almsdata.banking_transactions (account 0228362)")
    print("=" * 100)
    
    # Parse verified file
    print("\n1. Parsing verified file...")
    verified_file = r'L:\limo\reports\2012_cibc_complete_running_balance_verification.md'
    verified_txs = parse_verified_file(verified_file)
    print(f"   [OK] Found {len(verified_txs)} transactions in verified file")
    
    # Get database transactions
    print("\n2. Querying database...")
    conn = get_db_connection()
    db_txs = get_database_transactions(conn, '0228362', '2012')
    print(f"   [OK] Found {len(db_txs)} transactions in database")
    
    # Match transactions
    print("\n3. Matching transactions...")
    matches, missing_from_db, extra_in_db = match_transactions(verified_txs, db_txs)
    
    # Summary
    print("\n" + "=" * 100)
    print("AUDIT SUMMARY")
    print("=" * 100)
    print(f"Total verified transactions:     {len(verified_txs):>6}")
    print(f"Total database transactions:     {len(db_txs):>6}")
    print(f"Matched (exact):                 {sum(1 for m in matches if m['status'] == 'EXACT_MATCH'):>6}")
    print(f"Matched (amount only):           {sum(1 for m in matches if m['status'] == 'AMOUNT_MATCH_ONLY'):>6}")
    print(f"Missing from database:           {len(missing_from_db):>6}")
    print(f"Extra in database (not in file): {len(extra_in_db):>6}")
    
    match_rate = (len(matches) / len(verified_txs) * 100) if verified_txs else 0
    print(f"\nMatch Rate: {match_rate:.1f}%")
    
    # Detail missing transactions
    if missing_from_db:
        print("\n" + "=" * 100)
        print(f"MISSING FROM DATABASE ({len(missing_from_db)} transactions)")
        print("=" * 100)
        
        # Group by month
        by_month = defaultdict(list)
        for tx in missing_from_db:
            by_month[tx['month']].append(tx)
        
        for month in sorted(by_month.keys()):
            txs = by_month[month]
            print(f"\n{month} 2012: {len(txs)} missing transactions")
            print("-" * 100)
            for tx in txs[:10]:  # Show first 10 per month
                tx_type = 'W' if tx['debit'] else 'D'
                amount = tx['debit'] or tx['credit']
                print(f"  {tx['date']} | {tx_type} | ${amount:>10.2f} | {tx['description'][:60]}")
            if len(txs) > 10:
                print(f"  ... and {len(txs) - 10} more")
    
    # Detail extra transactions
    if extra_in_db:
        print("\n" + "=" * 100)
        print(f"EXTRA IN DATABASE (not in verified file) ({len(extra_in_db)} transactions)")
        print("=" * 100)
        
        # Group by month
        by_month = defaultdict(list)
        for tx in extra_in_db:
            month = tx['date'][:7]  # YYYY-MM
            by_month[month].append(tx)
        
        for month in sorted(by_month.keys()):
            txs = by_month[month]
            print(f"\n{month}: {len(txs)} extra transactions")
            print("-" * 100)
            for tx in txs[:10]:  # Show first 10 per month
                tx_type = 'W' if tx['debit'] else 'D'
                amount = tx['debit'] or tx['credit'] or 0
                print(f"  ID {tx['id']} | {tx['date']} | {tx_type} | ${amount:>10.2f} | {tx['description'][:60]}")
            if len(txs) > 10:
                print(f"  ... and {len(txs) - 10} more")
    
    # Description mismatches
    amount_only_matches = [m for m in matches if m['status'] == 'AMOUNT_MATCH_ONLY']
    if amount_only_matches:
        print("\n" + "=" * 100)
        print(f"DESCRIPTION MISMATCHES ({len(amount_only_matches)} transactions)")
        print("=" * 100)
        print("These transactions have matching amounts and dates but different descriptions:")
        print()
        for m in amount_only_matches[:20]:  # Show first 20
            vtx = m['verified']
            dtx = m['database']
            amount = vtx['debit'] or vtx['credit']
            print(f"{vtx['date']} | ${amount:.2f}")
            print(f"  Verified: {vtx['description'][:70]}")
            print(f"  Database: {dtx['description'][:70]}")
            print()
        if len(amount_only_matches) > 20:
            print(f"... and {len(amount_only_matches) - 20} more")
    
    # Export detailed report
    report_path = r'L:\limo\reports\2012_cibc_audit_detailed.txt'
    print("\n" + "=" * 100)
    print(f"Writing detailed report to: {report_path}")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("2012 CIBC VERIFIED FILE vs DATABASE AUDIT - DETAILED REPORT\n")
        f.write("=" * 100 + "\n")
        f.write(f"Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"SUMMARY:\n")
        f.write(f"Total verified transactions:     {len(verified_txs)}\n")
        f.write(f"Total database transactions:     {len(db_txs)}\n")
        f.write(f"Matched:                         {len(matches)}\n")
        f.write(f"Missing from database:           {len(missing_from_db)}\n")
        f.write(f"Extra in database:               {len(extra_in_db)}\n")
        f.write(f"Match Rate:                      {match_rate:.1f}%\n\n")
        
        if missing_from_db:
            f.write("\n" + "=" * 100 + "\n")
            f.write(f"MISSING FROM DATABASE ({len(missing_from_db)} transactions)\n")
            f.write("=" * 100 + "\n")
            for tx in missing_from_db:
                tx_type = 'W' if tx['debit'] else 'D'
                amount = tx['debit'] or tx['credit']
                f.write(f"{tx['date']} | {tx_type} | ${amount:>10.2f} | {tx['description']}\n")
        
        if extra_in_db:
            f.write("\n" + "=" * 100 + "\n")
            f.write(f"EXTRA IN DATABASE ({len(extra_in_db)} transactions)\n")
            f.write("=" * 100 + "\n")
            for tx in extra_in_db:
                tx_type = 'W' if tx['debit'] else 'D'
                amount = tx['debit'] or tx['credit'] or 0
                f.write(f"ID {tx['id']} | {tx['date']} | {tx_type} | ${amount:>10.2f} | {tx['description']}\n")
    
    print(f"   [OK] Detailed report written")
    
    conn.close()
    
    print("\n" + "=" * 100)
    print("AUDIT COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    main()
