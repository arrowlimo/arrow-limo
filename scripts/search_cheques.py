"""
Search for specific cheques in banking and receipts.
Cheques: 197 ($550), 209 ($550), 242 ($953.25), 252 ($525)
Also searching for "The Drive" advertising related.
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
    
    cheques = [
        ('197', 550.00),
        ('209', 550.00),
        ('242', 953.25),
        ('252', 525.00)
    ]
    
    print("="*80)
    print("SEARCHING FOR CHEQUES IN BANKING TRANSACTIONS")
    print("="*80)
    
    for chq_num, amount in cheques:
        print(f"\nCheque #{chq_num} - ${amount:.2f}:")
        
        # Search by cheque number
        cur.execute("""
            SELECT transaction_date, description, debit_amount, account_number
            FROM banking_transactions
            WHERE (description ILIKE %s OR description ILIKE %s)
            ORDER BY transaction_date
        """, (f'%CHEQUE%{chq_num}%', f'%CHQ%{chq_num}%'))
        
        results = cur.fetchall()
        if results:
            for row in results:
                account = 'CIBC' if row[3] == '0228362' else 'Scotia' if row[3] == '903990106011' else row[3]
                print(f"  {row[0]} | {row[1][:70]} | ${row[2]:,.2f} | {account}")
        else:
            # Try searching by amount
            cur.execute("""
                SELECT transaction_date, description, debit_amount, account_number
                FROM banking_transactions
                WHERE debit_amount = %s
                AND (description ILIKE '%CHEQUE%' OR description ILIKE '%CHQ%')
                ORDER BY transaction_date
            """, (amount,))
            
            amt_results = cur.fetchall()
            if amt_results:
                print(f"  Found by amount only:")
                for row in amt_results:
                    account = 'CIBC' if row[3] == '0228362' else 'Scotia' if row[3] == '903990106011' else row[3]
                    print(f"    {row[0]} | {row[1][:70]} | ${row[2]:,.2f} | {account}")
            else:
                print("  ❌ Not found in banking_transactions")
    
    print("\n" + "="*80)
    print("SEARCHING FOR CHEQUES IN RECEIPTS")
    print("="*80)
    
    for chq_num, amount in cheques:
        print(f"\nCheque #{chq_num} - ${amount:.2f}:")
        
        # Search in receipts
        cur.execute("""
            SELECT receipt_date, vendor_name, gross_amount, description
            FROM receipts
            WHERE (description ILIKE %s OR description ILIKE %s OR vendor_name ILIKE %s)
            ORDER BY receipt_date
        """, (f'%CHEQUE%{chq_num}%', f'%CHQ%{chq_num}%', f'%CHEQUE%{chq_num}%'))
        
        results = cur.fetchall()
        if results:
            for row in results:
                desc = row[3][:50] if row[3] else ''
                print(f"  {row[0]} | {row[1]} | ${row[2]:,.2f} | {desc}")
        else:
            # Try by amount
            cur.execute("""
                SELECT receipt_date, vendor_name, gross_amount, description
                FROM receipts
                WHERE gross_amount = %s
                AND (description ILIKE '%CHEQUE%' OR vendor_name ILIKE '%CHEQUE%')
                ORDER BY receipt_date
            """, (amount,))
            
            amt_results = cur.fetchall()
            if amt_results:
                print(f"  Found by amount only:")
                for row in amt_results:
                    desc = row[3][:50] if row[3] else ''
                    print(f"    {row[0]} | {row[1]} | ${row[2]:,.2f} | {desc}")
            else:
                print("  ❌ Not found in receipts")
    
    # Search for "The Drive" advertising
    print("\n" + "="*80)
    print("SEARCHING FOR 'THE DRIVE' ADVERTISING")
    print("="*80)
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, account_number
        FROM banking_transactions
        WHERE description ILIKE '%DRIVE%'
        OR description ILIKE '%ADVERTISING%'
        ORDER BY transaction_date
        LIMIT 20
    """)
    
    results = cur.fetchall()
    if results:
        print("\nFound in banking_transactions:")
        for row in results:
            account = 'CIBC' if row[3] == '0228362' else 'Scotia' if row[3] == '903990106011' else row[3]
            print(f"  {row[0]} | {row[1][:70]} | ${row[2]:,.2f} | {account}")
    else:
        print("\n❌ Not found in banking_transactions")
    
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE vendor_name ILIKE '%DRIVE%'
        OR vendor_name ILIKE '%ADVERTISING%'
        OR description ILIKE '%DRIVE%'
        OR description ILIKE '%ADVERTISING%'
        ORDER BY receipt_date
        LIMIT 20
    """)
    
    results = cur.fetchall()
    if results:
        print("\nFound in receipts:")
        for row in results:
            desc = row[3][:50] if row[3] else ''
            print(f"  {row[0]} | {row[1]} | ${row[2]:,.2f} | {desc}")
    else:
        print("\n❌ Not found in receipts")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
