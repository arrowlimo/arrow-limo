"""
Search for transactions by amount only (no description filter).
Amounts: $550.00, $953.25, $525.00
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    amounts = [550.00, 953.25, 525.00]
    
    print("="*80)
    print("SEARCHING BANKING TRANSACTIONS BY AMOUNT")
    print("="*80)
    
    for amount in amounts:
        print(f"\n${amount:.2f} transactions:")
        
        cur.execute("""
            SELECT transaction_date, description, debit_amount, account_number, transaction_id
            FROM banking_transactions
            WHERE debit_amount = %s
            ORDER BY transaction_date DESC
        """, (amount,))
        
        results = cur.fetchall()
        if results:
            print(f"  Found {len(results)} transaction(s):")
            for row in results:
                account = 'CIBC' if row[3] == '0228362' else 'Scotia' if row[3] == '903990106011' else row[3]
                print(f"    {row[0]} | {row[1][:60]} | ${row[2]:,.2f} | {account} | ID:{row[4]}")
        else:
            print("  ❌ Not found")
    
    print("\n" + "="*80)
    print("SEARCHING RECEIPTS BY AMOUNT")
    print("="*80)
    
    for amount in amounts:
        print(f"\n${amount:.2f} receipts:")
        
        cur.execute("""
            SELECT receipt_date, vendor_name, gross_amount, description, receipt_id, category
            FROM receipts
            WHERE gross_amount = %s
            ORDER BY receipt_date DESC
        """, (amount,))
        
        results = cur.fetchall()
        if results:
            print(f"  Found {len(results)} receipt(s):")
            for row in results:
                desc = (row[3][:40] if row[3] else '').replace('\n', ' ')
                print(f"    {row[0]} | {row[1][:30]} | ${row[2]:,.2f} | {row[5]} | ID:{row[4]}")
                if desc:
                    print(f"      Desc: {desc}")
        else:
            print("  ❌ Not found")
    
    # Check date range coverage
    print("\n" + "="*80)
    print("DATABASE DATE COVERAGE")
    print("="*80)
    
    cur.execute("""
        SELECT 
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as total
        FROM banking_transactions
    """)
    row = cur.fetchone()
    print(f"\nBanking Transactions: {row[2]:,} records from {row[0]} to {row[1]}")
    
    cur.execute("""
        SELECT 
            MIN(receipt_date) as earliest,
            MAX(receipt_date) as latest,
            COUNT(*) as total
        FROM receipts
    """)
    row = cur.fetchone()
    print(f"Receipts: {row[2]:,} records from {row[0]} to {row[1]}")
    
    # Search for "106.7" and "The Drive" more broadly
    print("\n" + "="*80)
    print("SEARCHING FOR '106.7' AND 'THE DRIVE'")
    print("="*80)
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, account_number
        FROM banking_transactions
        WHERE description ILIKE '%106.7%'
        OR description ILIKE '%106 %'
        OR description ILIKE '%DRIVE%'
        ORDER BY transaction_date DESC
        LIMIT 30
    """)
    
    results = cur.fetchall()
    if results:
        print(f"\nFound {len(results)} banking transaction(s):")
        for row in results:
            account = 'CIBC' if row[3] == '0228362' else 'Scotia' if row[3] == '903990106011' else row[3]
            print(f"  {row[0]} | {row[1][:65]} | ${row[2]:,.2f} | {account}")
    else:
        print("\n❌ Not found in banking")
    
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE vendor_name ILIKE '%106.7%'
        OR vendor_name ILIKE '%106 %'
        OR vendor_name ILIKE '%DRIVE%'
        OR description ILIKE '%106.7%'
        OR description ILIKE '%DRIVE%'
        ORDER BY receipt_date DESC
        LIMIT 30
    """)
    
    results = cur.fetchall()
    if results:
        print(f"\nFound {len(results)} receipt(s):")
        for row in results:
            desc = (row[3][:40] if row[3] else '').replace('\n', ' ')
            print(f"  {row[0]} | {row[1][:35]} | ${row[2]:,.2f}")
            if desc:
                print(f"    Desc: {desc}")
    else:
        print("\n❌ Not found in receipts")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
