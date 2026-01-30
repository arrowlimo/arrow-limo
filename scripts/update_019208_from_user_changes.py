"""
Update reserve 019208 in PostgreSQL based on user's LMS adjustments.
User adjusted charges and gratuity to balance out to match payments.
From screenshot: 5 payments totaling $2,410.00
"""

import psycopg2

def update_019208():
    conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***',
        host='localhost'
    )
    cur = conn.cursor()
    
    reserve = '019208'
    
    print("=" * 100)
    print("BEFORE UPDATE")
    print("=" * 100)
    
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    row = cur.fetchone()
    print(f"Reserve: {row[0]}")
    print(f"  Total Due: ${row[1]:,.2f}")
    print(f"  Paid: ${row[2]:,.2f}")
    print(f"  Balance: ${row[3]:,.2f}")
    
    cur.execute("""
        SELECT description, amount
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY description
    """, (reserve,))
    
    charges = cur.fetchall()
    print(f"\nCharges:")
    total = 0
    for c in charges:
        print(f"  {c[0]}: ${c[1]:,.2f}")
        total += c[1]
    print(f"  TOTAL: ${total:,.2f}")
    
    # Check payments
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM payments
        WHERE reserve_number = %s
    """, (reserve,))
    
    pay_row = cur.fetchone()
    print(f"\nPayments: {pay_row[0]} payments totaling ${pay_row[1] or 0:,.2f}")
    
    print(f"\n{'=' * 100}")
    print("RECALCULATING BALANCE FROM PAYMENTS")
    print("=" * 100)
    
    # Recalculate paid_amount from actual payments
    cur.execute("""
        WITH payment_sum AS (
            SELECT 
                reserve_number,
                SUM(amount) as total_paid
            FROM payments
            WHERE reserve_number = %s
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.total_paid,
            balance = c.total_amount_due - ps.total_paid
        FROM payment_sum ps
        WHERE c.reserve_number = ps.reserve_number
        RETURNING c.reserve_number, c.total_amount_due, c.paid_amount, c.balance
    """, (reserve,))
    
    updated = cur.fetchone()
    if updated:
        print(f"✓ Updated balance calculation:")
        print(f"  Total Due: ${updated[1]:,.2f}")
        print(f"  Paid: ${updated[2]:,.2f}")
        print(f"  Balance: ${updated[3]:,.2f}")
    
    conn.commit()
    
    print(f"\n{'=' * 100}")
    print("AFTER UPDATE")
    print("=" * 100)
    
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    final = cur.fetchone()
    print(f"Reserve: {final[0]}")
    print(f"  Total Due: ${final[1]:,.2f}")
    print(f"  Paid: ${final[2]:,.2f}")
    print(f"  Balance: ${final[3]:,.2f}")
    
    if abs(final[3]) < 0.01:
        print(f"\n✓ SUCCESS: Balance is $0.00")
    else:
        print(f"\n⚠️  Balance is ${final[3]:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    update_019208()
