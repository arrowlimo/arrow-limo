#!/usr/bin/env python
"""
Investigate why Charter 16187 payments are not being found by migration query.
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    charter_id = 16187
    
    print("=" * 100)
    print(f"INVESTIGATING CHARTER {charter_id} PAYMENTS")
    print("=" * 100)
    
    # Check ALL payments table entries for this charter (any charter_id or reserve_number match)
    print("\n1. Checking payments table for charter_id match:")
    cur.execute("""
        SELECT payment_id, charter_id, reserve_number, payment_amount, payment_date, payment_method
        FROM payments
        WHERE charter_id = %s
        ORDER BY payment_date
    """, (charter_id,))
    
    charter_id_matches = cur.fetchall()
    print(f"   Found {len(charter_id_matches)} records with charter_id={charter_id}")
    for row in charter_id_matches:
        print(f"   Payment {row[0]}: charter_id={row[1]}, reserve={row[2]}, amount=${row[3]}, date={row[4]}, method={row[5]}")
    
    # Check reserve_number
    cur.execute("""
        SELECT reserve_number FROM charters WHERE charter_id = %s
    """, (charter_id,))
    reserve_row = cur.fetchone()
    reserve_number = reserve_row[0] if reserve_row else None
    
    print(f"\n2. Charter {charter_id} has reserve_number: {reserve_number}")
    
    if reserve_number:
        print(f"\n3. Checking payments table for reserve_number={reserve_number}:")
        cur.execute("""
            SELECT payment_id, charter_id, reserve_number, payment_amount, payment_date, payment_method
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date
        """, (reserve_number,))
        
        reserve_matches = cur.fetchall()
        print(f"   Found {len(reserve_matches)} records with reserve_number={reserve_number}")
        for row in reserve_matches:
            print(f"   Payment {row[0]}: charter_id={row[1]}, reserve={row[2]}, amount=${row[3]}, date={row[4]}, method={row[5]}")
    
    # Check if ANY of these payments are already in charter_payments
    all_payment_ids = set()
    for row in charter_id_matches + (reserve_matches if reserve_number else []):
        all_payment_ids.add(row[0])
    
    if all_payment_ids:
        print(f"\n4. Checking if these payment_ids are already in charter_payments:")
        cur.execute("""
            SELECT payment_id, charter_id, amount
            FROM charter_payments
            WHERE payment_id = ANY(%s)
        """, (list(all_payment_ids),))
        
        existing = cur.fetchall()
        print(f"   Found {len(existing)} payment_ids already in charter_payments")
        for row in existing:
            print(f"   Payment {row[0]}: charter_id={row[1]}, amount=${row[2]}")
        
        not_in_charter_payments = all_payment_ids - set(row[0] for row in existing)
        print(f"\n5. Payment IDs NOT in charter_payments: {len(not_in_charter_payments)}")
        if not_in_charter_payments:
            print(f"   Missing payment_ids: {sorted(not_in_charter_payments)}")
    
    # Check payment_amount values (maybe they're negative or zero?)
    print(f"\n6. Checking payment amounts for charter {charter_id}:")
    all_payments = charter_id_matches + (reserve_matches if reserve_number else [])
    positive_count = sum(1 for row in all_payments if row[3] and row[3] > 0)
    zero_count = sum(1 for row in all_payments if row[3] == 0)
    negative_count = sum(1 for row in all_payments if row[3] and row[3] < 0)
    null_count = sum(1 for row in all_payments if row[3] is None)
    
    print(f"   Positive amounts: {positive_count}")
    print(f"   Zero amounts: {zero_count}")
    print(f"   Negative amounts: {negative_count}")
    print(f"   NULL amounts: {null_count}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*100)
    print("INVESTIGATION COMPLETE")
    print("="*100)

if __name__ == '__main__':
    main()
