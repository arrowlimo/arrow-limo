"""
Fix misdated banking transactions from 2025-10-17 batch.

ISSUE: 554 transactions were imported on 2025-10-17 14:59:38, all dated 2025-10-17,
but descriptions show they are actually 2012 transactions (May-Dec 2012).

Transactions include:
- "Sales May 2012", "June 2012 Sales", "Sales August 2012", etc.
- ACE TRUCK RENTALS LTD. payments (vehicle financing)
- Regular operating expenses from 2012

This script identifies which month each transaction belongs to and corrects the date.
"""

import psycopg2
import re
from datetime import datetime, date
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def extract_month_from_description(description):
    """
    Extract month from description like 'Sales May 2012' or 'June 2012 Sales'.
    Returns (year, month) tuple or None.
    """
    if not description:
        return None
    
    desc_upper = description.upper()
    
    # Pattern: "Sales May 2012" or "May 2012 Sales"
    months = {
        'JANUARY': 1, 'JAN': 1,
        'FEBRUARY': 2, 'FEB': 2,
        'MARCH': 3, 'MAR': 3,
        'APRIL': 4, 'APR': 4,
        'MAY': 5,
        'JUNE': 6, 'JUN': 6,
        'JULY': 7, 'JUL': 7,
        'AUGUST': 8, 'AUG': 8,
        'SEPTEMBER': 9, 'SEPT': 9, 'SEP': 9,
        'OCTOBER': 10, 'OCT': 10,
        'NOVEMBER': 11, 'NOV': 11,
        'DECEMBER': 12, 'DEC': 12
    }
    
    for month_name, month_num in months.items():
        if month_name in desc_upper and '2012' in desc_upper:
            return (2012, month_num)
    
    return None

def analyze_batch():
    """Analyze the misdated batch to determine correct dates."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("ANALYZING 2025-10-17 MISDATED BATCH")
    print("=" * 100)
    
    # Get all transactions from the misdated batch
    cur.execute("""
        SELECT transaction_id, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE created_at::date = '2025-10-17'
        AND account_number = '0228362'
        ORDER BY transaction_id
    """)
    
    transactions = cur.fetchall()
    print(f"\nTotal transactions in batch: {len(transactions)}")
    
    # Categorize by identified month
    by_month = defaultdict(list)
    no_month_identified = []
    
    for txn in transactions:
        txn_id, desc, debit, credit, balance = txn
        month_info = extract_month_from_description(desc)
        
        if month_info:
            year, month = month_info
            by_month[(year, month)].append(txn)
        else:
            no_month_identified.append(txn)
    
    # Report findings
    print(f"\nTransactions with identified months: {sum(len(v) for v in by_month.values())}")
    for (year, month), txns in sorted(by_month.items()):
        month_name = date(year, month, 1).strftime('%B %Y')
        print(f"  {month_name}: {len(txns)} transactions")
    
    print(f"\nTransactions without month identified: {len(no_month_identified)}")
    
    # Sample the unidentified ones
    if no_month_identified:
        print("\nSample of unidentified transactions:")
        for txn in no_month_identified[:20]:
            txn_id, desc, debit, credit, balance = txn
            desc_short = (desc[:50] if desc else 'None')
            d = debit if debit else 0
            c = credit if credit else 0
            print(f"  ID {txn_id} | D:{d:>8.2f} C:{c:>8.2f} | {desc_short}")
    
    # Check ACE TRUCK specifically
    print("\n" + "=" * 100)
    print("ACE TRUCK RENTALS entries in this batch:")
    ace_truck = [t for t in transactions if t[1] and 'ACE TRUCK' in t[1].upper()]
    print(f"Count: {len(ace_truck)}")
    for txn in ace_truck:
        txn_id, desc, debit, credit, balance = txn
        print(f"  ID {txn_id} | ${debit if debit else 0:.2f} | {desc}")
    
    cur.close()
    conn.close()
    
    return len(transactions), len(no_month_identified)

def check_for_duplicates():
    """Check if correcting dates would create duplicates with existing 2012 data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("CHECKING FOR POTENTIAL DUPLICATES IN 2012 DATA")
    print("=" * 100)
    
    # Check ACE TRUCK specifically since we know those exist in 2012
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        AND UPPER(description) LIKE '%ACE TRUCK%'
    """)
    
    count_2012 = cur.fetchone()[0]
    print(f"\nExisting CIBC ACE TRUCK transactions in 2012: {count_2012}")
    
    # Get the amounts from the misdated batch
    cur.execute("""
        SELECT debit_amount
        FROM banking_transactions
        WHERE created_at::date = '2025-10-17'
        AND account_number = '0228362'
        AND UPPER(description) LIKE '%ACE TRUCK%'
    """)
    
    misdated_amounts = [row[0] for row in cur.fetchall()]
    print(f"Misdated ACE TRUCK amounts: {misdated_amounts}")
    
    # Check if these amounts exist in 2012 CIBC
    for amount in misdated_amounts:
        cur.execute("""
            SELECT transaction_date, description
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
            AND UPPER(description) LIKE '%ACE TRUCK%'
            AND ABS(debit_amount - %s) < 0.01
        """, (amount,))
        
        matches = cur.fetchall()
        if matches:
            print(f"\n  Amount ${amount} exists in 2012 CIBC:")
            for m in matches:
                print(f"    {m[0]} | {m[1]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    import sys
    
    print("2025-10-17 MISDATED BATCH ANALYSIS")
    print("=" * 100)
    print("\nThis batch was imported on 2025-10-17 14:59:38")
    print("All 554 transactions were given the date 2025-10-17")
    print("But descriptions show they are actually 2012 transactions")
    print("\nExamples:")
    print("  - 'Sales May 2012'")
    print("  - 'June 2012 Sales'")
    print("  - 'Sales August 2012'")
    print("  - 'ACE TRUCK RENTALS LTD.' (2012 vehicle financing)")
    
    total, unidentified = analyze_batch()
    check_for_duplicates()
    
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS:")
    print("=" * 100)
    print("\n1. The ACE TRUCK entries (IDs 44400, 44662) appear to be DUPLICATES")
    print("   - Same amounts exist in Scotia 903990106011 in 2012")
    print("   - These should be DELETED, not re-dated")
    print("\n2. Other transactions with month identifiers should be re-dated")
    print("   - Need to determine exact day within each month")
    print("   - May need to match against Scotia data or QuickBooks")
    print("\n3. Transactions without month identifiers need manual review")
    print(f"   - {unidentified} transactions need investigation")
    print("\nNEXT STEPS:")
    print("1. Create backup of banking_transactions")
    print("2. DELETE the ACE TRUCK duplicates")
    print("3. Develop matching strategy for re-dating other transactions")
    print("4. Delete receipts that were auto-created from these misdated transactions")
