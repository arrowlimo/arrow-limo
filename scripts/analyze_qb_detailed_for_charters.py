"""
Analyze QuickBooks detailed transactions for charter/reserve number references.

The QB detailed reconciliation might have memo/name fields that reference
reserve numbers, which we can use to match unmatched payments.
"""

import psycopg2
import csv
import re
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def extract_reserve_numbers(text):
    """Extract potential reserve numbers from text"""
    if not text:
        return []
    
    # Patterns for reserve numbers
    patterns = [
        r'\b(\d{6})\b',           # 6-digit number (e.g., 007938)
        r'\bRES[#:\s]*(\d{6})\b', # RES 007938
        r'\bREF[#:\s]*(\d{6})\b', # REF 007938
        r'\b#(\d{6})\b',          # #007938
    ]
    
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    
    return list(set(found))  # Remove duplicates

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all reserve numbers from charters for validation
    cur.execute("SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    valid_reserves = {row[0] for row in cur.fetchall()}
    print(f"Valid reserve numbers in database: {len(valid_reserves):,}")
    
    # Read QB transactions CSV
    qb_file = r'l:\limo\staging\2012_quickbooks\qb_transactions_2012.csv'
    
    print(f"\n{'='*80}")
    print(f"ANALYZING QUICKBOOKS DETAILED TRANSACTIONS")
    print(f"{'='*80}\n")
    
    with open(qb_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Show available columns
        print("Available columns in QB transactions:")
        for i, col in enumerate(reader.fieldnames, 1):
            print(f"  {i}. {col}")
        
        f.seek(0)
        next(reader)  # Skip header
        
        # Analyze transactions
        total_transactions = 0
        transactions_with_numbers = []
        reserve_matches = defaultdict(list)
        
        for row in reader:
            total_transactions += 1
            
            # Search all text fields for potential reserve numbers
            all_text = ' '.join([
                str(row.get('name', '')),
                str(row.get('num', '')),
                str(row.get('memo', '')),
                str(row.get('description', '')),
                str(row.get('type', ''))
            ])
            
            potential_reserves = extract_reserve_numbers(all_text)
            
            if potential_reserves:
                # Check if any match valid reserve numbers
                valid_matches = [r for r in potential_reserves if r in valid_reserves]
                
                if valid_matches:
                    transactions_with_numbers.append({
                        'date': row.get('date'),
                        'type': row.get('type'),
                        'num': row.get('num'),
                        'name': row.get('name'),
                        'amount': row.get('amount'),
                        'cleared': row.get('cleared'),
                        'reserve_numbers': valid_matches,
                        'all_text': all_text[:100]
                    })
                    
                    for reserve in valid_matches:
                        reserve_matches[reserve].append(row)
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS RESULTS")
    print(f"{'='*80}\n")
    print(f"Total QB transactions: {total_transactions:,}")
    print(f"Transactions with valid reserve numbers: {len(transactions_with_numbers):,}")
    print(f"Unique reserve numbers found: {len(reserve_matches):,}")
    
    # Show sample transactions with reserve numbers
    if transactions_with_numbers:
        print(f"\n{'='*80}")
        print(f"SAMPLE TRANSACTIONS WITH RESERVE NUMBERS")
        print(f"{'='*80}\n")
        
        for i, txn in enumerate(transactions_with_numbers[:20], 1):
            print(f"{i}. Date: {txn['date']} | Type: {txn['type']} | Amount: {txn['amount']}")
            print(f"   Name: {txn['name']}")
            print(f"   Reserve Numbers: {', '.join(txn['reserve_numbers'])}")
            print(f"   Text: {txn['all_text']}")
            print()
    
    # Check if these reserves have unmatched payments
    if reserve_matches:
        print(f"\n{'='*80}")
        print(f"CHECKING FOR UNMATCHED PAYMENTS")
        print(f"{'='*80}\n")
        
        reserve_list = ','.join([f"'{r}'" for r in reserve_matches.keys()])
        
        cur.execute(f"""
            SELECT 
                c.reserve_number,
                c.charter_id,
                c.account_number,
                c.charter_date,
                c.total_amount_due,
                c.balance,
                COALESCE(
                    (SELECT COUNT(*) FROM payments WHERE charter_id = c.charter_id),
                    0
                ) as payment_count,
                COALESCE(
                    (SELECT SUM(amount) FROM payments WHERE charter_id = c.charter_id),
                    0
                ) as total_paid,
                COALESCE(
                    (SELECT COUNT(*) FROM payments WHERE reserve_number = c.reserve_number AND charter_id IS NULL),
                    0
                ) as unmatched_payment_count
            FROM charters c
            WHERE c.reserve_number IN ({reserve_list})
            ORDER BY c.charter_date
        """)
        
        charters_with_qb_refs = cur.fetchall()
        
        print(f"Charters referenced in QB transactions: {len(charters_with_qb_refs):,}\n")
        
        for i, (reserve, charter_id, account, charter_date, total_due, balance, 
                payment_count, total_paid, unmatched_count) in enumerate(charters_with_qb_refs[:20], 1):
            print(f"{i}. Reserve: {reserve} | Charter: {charter_id} | Date: {charter_date}")
            print(f"   Total Due: ${total_due:,.2f} | Balance: ${balance:,.2f}")
            print(f"   Payments: {payment_count} (${total_paid:,.2f})")
            if unmatched_count > 0:
                print(f"   [WARN]  UNMATCHED payments with this reserve: {unmatched_count}")
            print(f"   QB transactions: {len(reserve_matches[reserve])}")
            print()
        
        if len(charters_with_qb_refs) > 20:
            print(f"   ... and {len(charters_with_qb_refs) - 20} more\n")
    
    # Summary statistics
    if reserve_matches:
        print(f"\n{'='*80}")
        print(f"LINKAGE POTENTIAL")
        print(f"{'='*80}\n")
        
        # Check how many unmatched payments have reserve numbers that appear in QB
        cur.execute(f"""
            SELECT COUNT(*), SUM(amount)
            FROM payments
            WHERE reserve_number IS NULL
              AND reserve_number IN ({reserve_list})
              AND amount > 0
        """)
        
        unmatched_with_qb_ref = cur.fetchone()
        
        if unmatched_with_qb_ref[0]:
            print(f"Unmatched payments with reserve numbers found in QB:")
            print(f"  Count: {unmatched_with_qb_ref[0]:,}")
            print(f"  Amount: ${unmatched_with_qb_ref[1]:,.2f}")
            print(f"\n[OK] These can potentially be matched using reserve_number!")
    else:
        print(f"\n[FAIL] No reserve number references found in QuickBooks transactions")
        print(f"   QB transactions use different identifiers (check, num, name fields)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
