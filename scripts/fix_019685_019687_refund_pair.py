"""
Fix reserves 019685 and 019687 - incorrect 'refund_pair' status.

These reserves have:
- No payments in LMS or PostgreSQL
- Positive balances (money owed, not overpaid)
- Status: NULL in LMS (authoritative)
- Status: 'refund_pair' in PostgreSQL (incorrect)

'refund_pair' status should only apply when there's an overpayment requiring refund.
These are simply unpaid bookings, so status should be NULL.
"""

import psycopg2

def fix_incorrect_refund_pair():
    conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***',
        host='localhost'
    )
    cur = conn.cursor()
    
    reserves = ['019685', '019687']
    
    print("BEFORE UPDATE:")
    print("=" * 80)
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE reserve_number IN %s
        ORDER BY reserve_number
    """, (tuple(reserves),))
    
    for row in cur.fetchall():
        print(f"{row[0]}  Total: ${row[1]:>8.2f}  Paid: ${row[2]:>8.2f}  Balance: ${row[3]:>8.2f}  Status: {row[4]}")
    
    # Update to NULL status (matching LMS)
    cur.execute("""
        UPDATE charters
        SET status = NULL
        WHERE reserve_number IN %s
        AND status = 'refund_pair'
    """, (tuple(reserves),))
    
    updated = cur.rowcount
    conn.commit()
    
    print(f"\n✓ Updated {updated} charter(s)")
    
    print("\nAFTER UPDATE:")
    print("=" * 80)
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE reserve_number IN %s
        ORDER BY reserve_number
    """, (tuple(reserves),))
    
    for row in cur.fetchall():
        print(f"{row[0]}  Total: ${row[1]:>8.2f}  Paid: ${row[2]:>8.2f}  Balance: ${row[3]:>8.2f}  Status: {row[4] or 'NULL'}")
    
    cur.close()
    conn.close()
    
    print("\nEXPLANATION:")
    print("-" * 80)
    print("'refund_pair' status is for overpayments requiring refund.")
    print("These reserves have $0.00 paid and positive balances = money OWED.")
    print("LMS shows Status: NULL for both reserves.")
    print("PostgreSQL now matches LMS: Status = NULL")

if __name__ == '__main__':
    fix_incorrect_refund_pair()
