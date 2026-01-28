"""
Check reserves 019685 and 019687 for payment/refund status.
User reports these have no payments but show refund pair - investigate.
"""

import psycopg2
import sys

def check_reserves():
    conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***',
        host='localhost'
    )
    cur = conn.cursor()
    
    reserves = ['019685', '019687']
    
    print("=" * 100)
    print("CHARTER DETAILS")
    print("=" * 100)
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.cancelled,
            c.notes
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number IN %s
        ORDER BY c.reserve_number
    """, (tuple(reserves),))
    
    for row in cur.fetchall():
        print(f"\nReserve: {row[0]}")
        print(f"  Date: {row[1]}")
        print(f"  Client: {row[2]}")
        print(f"  Total Due: ${row[3]:,.2f}")
        print(f"  Paid Amount: ${row[4]:,.2f}")
        print(f"  Balance: ${row[5]:,.2f}")
        print(f"  Status: {row[6] or 'NULL'}")
        print(f"  Cancelled: {row[7]}")
        print(f"  Notes: {row[8] or 'None'}")
    
    print("\n" + "=" * 100)
    print("PAYMENTS FOR THESE RESERVES")
    print("=" * 100)
    cur.execute("""
        SELECT 
            reserve_number,
            payment_id,
            amount,
            payment_date,
            payment_method,
            notes,
            payment_key
        FROM payments
        WHERE reserve_number IN %s
        ORDER BY reserve_number, payment_date
    """, (tuple(reserves),))
    
    payments = cur.fetchall()
    if payments:
        for p in payments:
            print(f"\n{p[0]} - Payment #{p[1]}")
            print(f"  Amount: ${p[2]:,.2f}")
            print(f"  Date: {p[3]}")
            print(f"  Method: {p[4] or 'NULL'}")
            print(f"  Key: {p[6] or 'NULL'}")
            print(f"  Notes: {p[5] or 'None'}")
    else:
        print("\nNO PAYMENTS FOUND for these reserves")
    
    print("\n" + "=" * 100)
    print("CHARTER CHARGES FOR THESE RESERVES")
    print("=" * 100)
    cur.execute("""
        SELECT 
            reserve_number,
            description,
            amount,
            charge_type
        FROM charter_charges
        WHERE reserve_number IN %s
        ORDER BY reserve_number
    """, (tuple(reserves),))
    
    charges = cur.fetchall()
    if charges:
        for c in charges:
            print(f"\n{c[0]}: {c[1]}")
            print(f"  Amount: ${c[2]:,.2f}")
            print(f"  Type: {c[3] or 'NULL'}")
    else:
        print("\nNO CHARGES FOUND for these reserves")
    
    print("\n" + "=" * 100)
    print("CHECK FOR REFUND REFERENCES IN NOTES/DESCRIPTIONS")
    print("=" * 100)
    
    # Check if 'refund' or 'pair' appears anywhere
    cur.execute("""
        SELECT 'charter.notes' as source, reserve_number, notes
        FROM charters
        WHERE reserve_number IN %s
        AND notes ILIKE '%%refund%%'
        
        UNION ALL
        
        SELECT 'payment.notes' as source, reserve_number, notes
        FROM payments
        WHERE reserve_number IN %s
        AND notes ILIKE '%%refund%%'
        
        UNION ALL
        
        SELECT 'charge.description' as source, reserve_number, description
        FROM charter_charges
        WHERE reserve_number IN %s
        AND description ILIKE '%%refund%%'
    """, (tuple(reserves), tuple(reserves), tuple(reserves)))
    
    refund_mentions = cur.fetchall()
    if refund_mentions:
        for r in refund_mentions:
            print(f"\n{r[0]}: {r[1]}")
            print(f"  Text: {r[2]}")
    else:
        print("\nNO 'refund' mentions found in notes/descriptions")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_reserves()
