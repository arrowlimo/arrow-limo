#!/usr/bin/env python
"""
Re-check Charter 16187 with correct understanding: charter_payments is the source.
"""
import psycopg2

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
    
    charter_id = 16187
    
    print("=" * 100)
    print(f"RE-ANALYZING CHARTER {charter_id}")
    print("=" * 100)
    
    # Get charter details
    cur.execute("""
        SELECT charter_id, reserve_number, paid_amount, total_amount_due, balance
        FROM charters
        WHERE charter_id = %s
    """, (charter_id,))
    charter = cur.fetchone()
    
    if charter:
        cid, reserve, paid, total, bal = charter
        print(f"\nCharter {cid}:")
        print(f"  Reserve Number: {reserve}")
        print(f"  Paid Amount: ${paid:,.2f}")
        print(f"  Total Due: ${total:,.2f}")
        print(f"  Balance: ${bal:,.2f}")
        
        # Check charter_payments with reserve_number as charter_id (varchar)
        print(f"\nChecking charter_payments with charter_id='{reserve}':")
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_method
            FROM charter_payments
            WHERE charter_id = %s
            ORDER BY payment_date
        """, (reserve,))
        
        cp_records = cur.fetchall()
        print(f"  Found {len(cp_records)} records")
        if cp_records:
            total_cp = sum(row[1] for row in cp_records)
            print(f"  Total amount: ${total_cp:,.2f}")
            print("\n  Details:")
            for payment_id, amount, date, method in cp_records:
                print(f"    Payment {payment_id}: ${amount:,.2f} on {date} via {method or 'NULL'}")
            
            # Compare to charter.paid_amount
            print(f"\n  Comparison:")
            print(f"    charter_payments SUM: ${total_cp:,.2f}")
            print(f"    charter.paid_amount:  ${paid:,.2f}")
            print(f"    Difference:           ${total_cp - paid:,.2f}")
            
            if abs(total_cp - paid) > 0.01:
                print(f"\n  ⚠ DISCREPANCY: charter.paid_amount should be ${total_cp:,.2f}")
            else:
                print(f"\n  ✓ MATCH: paid_amount is correct")
        else:
            print(f"  ⚠ NO charter_payments records found but paid_amount = ${paid:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
