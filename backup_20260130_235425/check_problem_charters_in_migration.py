#!/usr/bin/env python
"""
Verify that problem charters (16187, 17555, 16948) are included in migration candidates.
"""
import psycopg2
import sys
import os

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    problem_charters = [16187, 17555, 16948]
    
    print("=" * 100)
    print("CHECKING PROBLEM CHARTERS IN MIGRATION CANDIDATES")
    print("=" * 100)
    
    for charter_id in problem_charters:
        print(f"\n{'='*100}")
        print(f"CHARTER {charter_id}")
        print(f"{'='*100}")
        
        # Check current charter_payments
        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM charter_payments
            WHERE charter_id = %s
        """, (str(charter_id),))
        cp_count, cp_sum = cur.fetchone()
        print(f"\nCurrent charter_payments: {cp_count} records, ${cp_sum:,.2f}")
        
        # Check charter.paid_amount
        cur.execute("""
            SELECT paid_amount, total_amount_due, balance
            FROM charters
            WHERE charter_id = %s
        """, (charter_id,))
        row = cur.fetchone()
        if row:
            paid, total, balance = row
            print(f"Charter.paid_amount: ${paid:,.2f}")
            print(f"Charter.total_amount_due: ${total:,.2f}")
            print(f"Charter.balance: ${balance:,.2f}")
        
        # Check migration candidates from payments table
        cur.execute("""
            SELECT p.payment_id, p.payment_amount, p.payment_date, p.payment_method
            FROM payments p
            WHERE p.charter_id = %s
            AND p.payment_amount > 0
            AND NOT EXISTS (
                SELECT 1 FROM charter_payments cp
                WHERE cp.payment_id = p.payment_id
            )
            ORDER BY p.payment_date
        """, (charter_id,))
        
        candidates = cur.fetchall()
        print(f"\nMigration candidates: {len(candidates)} records")
        if candidates:
            total_migration = sum(row[1] for row in candidates)
            print(f"Total to migrate: ${total_migration:,.2f}")
            print("\nCandidate details:")
            for payment_id, amount, date, method in candidates:
                print(f"  Payment {payment_id}: ${amount:,.2f} on {date} via {method or 'NULL'}")
        
        # Show expected final state
        if candidates:
            expected_final = cp_sum + sum(row[1] for row in candidates)
            print(f"\nExpected charter_payments sum after migration: ${expected_final:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*100)
    print("VERIFICATION COMPLETE")
    print("="*100)

if __name__ == '__main__':
    main()
