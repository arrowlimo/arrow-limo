#!/usr/bin/env python
"""
Flexible cheque stub import - updates cheque register with payee information.
Finds cheques by amount (allows small variance) and updates payee.

Usage:
    Edit the CHEQUE_STUBS list below with your stub data, then run this script.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# =============================================================================
# ADD YOUR CHEQUE STUB DATA HERE
# Format: {'stub': 'stub number', 'amount': 0.00, 'payee': 'Vendor Name'}
# =============================================================================

CHEQUE_STUBS = [
    # Example entries (already processed):
    # {'stub': '0001', 'amount': 1870.14, 'payee': 'Angel Escobar'},
    # {'stub': '0002', 'amount': 489.20, 'payee': 'Julsy 10 L8 Inspection'},
    # {'stub': '0003', 'amount': 2000.00, 'payee': 'Parrs Automotive'},  # [OK] Updated
    
    # Add more cheque stubs below:
]

# =============================================================================

def main():
    if not CHEQUE_STUBS:
        print("[WARN]  No cheque stubs to process. Add entries to CHEQUE_STUBS list in the script.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=== CHEQUE STUB IMPORT ===\n")
    print(f"Processing {len(CHEQUE_STUBS)} cheque stub(s)...\n")
    
    updated_count = 0
    not_found_count = 0
    already_set_count = 0
    
    for stub in CHEQUE_STUBS:
        stub_num = stub.get('stub', 'N/A')
        amount = stub['amount']
        payee = stub['payee']
        
        print(f"Stub #{stub_num} - {payee} - ${amount:.2f}")
        
        # Find by amount (allow $0.01 variance for rounding)
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
            AND cleared_date >= '2012-01-01'
            AND cleared_date <= '2012-12-31'
            ORDER BY cleared_date
        """, (amount,))
        
        matches = cur.fetchall()
        
        if len(matches) == 1:
            # Exact match - update it
            chq_id, chq_num, cleared, amt, old_payee, memo = matches[0]
            
            if old_payee and old_payee.strip() and old_payee != 'Unknown':
                print(f"  ℹ️  Already has payee: #{chq_num} | {cleared} | ${amt:.2f} | {old_payee}")
                already_set_count += 1
            else:
                cur.execute("""
                    UPDATE cheque_register
                    SET payee = %s
                    WHERE id = %s
                """, (payee, chq_id))
                
                print(f"  [OK] Updated: #{chq_num} | {cleared} | ${amt:.2f}")
                updated_count += 1
                
        elif len(matches) > 1:
            # Multiple matches - show options
            print(f"  [WARN]  Multiple matches found:")
            for i, (chq_id, chq_num, cleared, amt, old_payee, memo) in enumerate(matches, 1):
                old_display = old_payee if old_payee else "Unknown"
                print(f"     {i}. ID:{chq_id} | #{chq_num} | {cleared} | ${amt:.2f} | {old_display}")
            print(f"     Manual update required - specify cheque ID")
            not_found_count += 1
            
        else:
            # No matches
            print(f"  [FAIL] No match found in 2012")
            not_found_count += 1
        
        print()
    
    conn.commit()
    
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Updated: {updated_count}")
    print(f"Already had payee: {already_set_count}")
    print(f"Not found / Multiple matches: {not_found_count}")
    
    if updated_count > 0:
        print(f"\n[OK] Successfully updated {updated_count} cheque(s)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
