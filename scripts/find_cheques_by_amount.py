#!/usr/bin/env python
"""
Find cheques in register by amount to help match stub data.
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

# Cheque stub data
stubs_to_find = [
    {'stub_number': '0001', 'payee': 'Angel Escobar', 'amount': 1870.14},
    {'stub_number': '0002', 'payee': 'Julsy 10 L8 Inspection', 'amount': 489.20},
    {'stub_number': '0003', 'payee': 'Parrs Automotive', 'amount': 2000.00},
]

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=== FINDING CHEQUES BY AMOUNT ===\n")
    
    for stub in stubs_to_find:
        amount = stub['amount']
        payee = stub['payee']
        stub_num = stub['stub_number']
        
        print(f"Stub #{stub_num} - {payee} - ${amount:.2f}")
        
        # Find by exact amount
        cur.execute("""
            SELECT 
                id,
                cheque_number,
                cleared_date,
                amount,
                payee,
                memo
            FROM cheque_register
            WHERE ABS(amount - %s) < 0.01
            ORDER BY cleared_date
        """, (amount,))
        
        matches = cur.fetchall()
        
        if matches:
            print(f"  Found {len(matches)} match(es):")
            for chq_id, chq_num, cleared, amt, old_payee, memo in matches:
                old_display = old_payee if old_payee else "Unknown"
                print(f"    ID: {chq_id:5} | Cheque #{chq_num:12} | {cleared} | ${amt:10.2f} | {old_display}")
                if memo:
                    print(f"           Memo: {memo[:80]}")
        else:
            print(f"  [FAIL] No matches found")
        
        print()
    
    # Show all cheques in chronological order (first 20)
    print("\n" + "="*100)
    print("ALL CHEQUES IN REGISTER (first 20 by date)")
    print("="*100)
    
    cur.execute("""
        SELECT 
            id,
            cheque_number,
            cleared_date,
            amount,
            payee
        FROM cheque_register
        ORDER BY cleared_date, cheque_number
        LIMIT 20
    """)
    
    all_cheques = cur.fetchall()
    for chq_id, chq_num, cleared, amt, payee_name in all_cheques:
        payee_display = payee_name if payee_name else "Unknown"
        print(f"ID:{chq_id:5} | #{chq_num:12} | {cleared} | ${amt:10.2f} | {payee_display[:40]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
