#!/usr/bin/env python
"""
Update cheque register with payee information from physical cheque stubs.
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
cheque_stubs = [
    {'cheque_number': '0001', 'payee': 'Angel Escobar', 'amount': 1870.14},
    {'cheque_number': '0002', 'payee': 'Julsy 10 L8 Inspection', 'amount': 489.20},
    {'cheque_number': '0003', 'payee': 'Parrs Automotive', 'amount': 2000.00},
]

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=== UPDATING CHEQUE REGISTER FROM STUBS ===\n")
    
    updated_count = 0
    not_found_count = 0
    
    for stub in cheque_stubs:
        chq_num = stub['cheque_number']
        payee = stub['payee']
        amount = stub['amount']
        
        # Try to find matching cheque by number and amount
        cur.execute("""
            SELECT id, cheque_number, cleared_date, amount, payee
            FROM cheque_register
            WHERE cheque_number = %s
            AND ABS(amount - %s) < 0.01
        """, (chq_num, amount))
        
        match = cur.fetchone()
        
        if match:
            chq_id, chq_num_db, cleared_date, amt_db, old_payee = match
            
            # Update payee
            cur.execute("""
                UPDATE cheque_register
                SET payee = %s
                WHERE id = %s
            """, (payee, chq_id))
            
            updated_count += 1
            old_display = old_payee if old_payee else "Unknown"
            print(f"[OK] Cheque #{chq_num:6} | {cleared_date} | ${amt_db:10.2f} | {old_display:30} → {payee}")
        else:
            # Try with leading zeros stripped
            stripped_num = chq_num.lstrip('0')
            cur.execute("""
                SELECT id, cheque_number, cleared_date, amount, payee
                FROM cheque_register
                WHERE cheque_number = %s
                AND ABS(amount - %s) < 0.01
            """, (stripped_num, amount))
            
            match = cur.fetchone()
            
            if match:
                chq_id, chq_num_db, cleared_date, amt_db, old_payee = match
                
                cur.execute("""
                    UPDATE cheque_register
                    SET payee = %s
                    WHERE id = %s
                """, (payee, chq_id))
                
                updated_count += 1
                old_display = old_payee if old_payee else "Unknown"
                print(f"[OK] Cheque #{chq_num:6} (#{chq_num_db}) | {cleared_date} | ${amt_db:10.2f} | {old_display:30} → {payee}")
            else:
                # Try by amount only (within same year)
                cur.execute("""
                    SELECT id, cheque_number, cleared_date, amount, payee
                    FROM cheque_register
                    WHERE ABS(amount - %s) < 0.01
                    AND cleared_date >= '2012-01-01'
                    AND cleared_date <= '2012-12-31'
                    ORDER BY cleared_date
                    LIMIT 5
                """, (amount,))
                
                amount_matches = cur.fetchall()
                
                if amount_matches:
                    print(f"\n[WARN]  Cheque #{chq_num} for ${amount:.2f} to {payee} - NOT FOUND by number")
                    print(f"   Possible matches by amount:")
                    for mid, mnum, mdate, mamt, mpayee in amount_matches:
                        mpayee_display = mpayee if mpayee else "Unknown"
                        print(f"     #{mnum:10} | {mdate} | ${mamt:10.2f} | {mpayee_display}")
                    not_found_count += 1
                else:
                    print(f"[FAIL] Cheque #{chq_num} for ${amount:.2f} to {payee} - NO MATCH FOUND")
                    not_found_count += 1
    
    conn.commit()
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Cheques updated: {updated_count}")
    print(f"Cheques not found: {not_found_count}")
    
    if updated_count > 0:
        print(f"\n[OK] Successfully updated {updated_count} cheque(s) with payee information")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
