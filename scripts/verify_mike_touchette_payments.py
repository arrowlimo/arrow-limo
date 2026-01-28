"""
Verify and allocate Square payments for Mike Touchette reservations 018885 and 019127.

Per reservation documents:
- 018885: Total $1,183.87, Deposit $500.00, Balance $683.87
- 019127: Total $184.50, Deposit $184.50, Balance $0.00

Payments found (currently linked to 018885):
- Payment 78672: $204.17 on 07/29/2025 (LMS 25122)
- Payment 78690: $712.05 on 08/01/2025 (LMS 25140)
- Total: $916.22

Need to allocate:
- 019127 needs: $184.50 (full payment)
- 018885 needs: $683.87 (balance after $500 deposit)
- Plus need to find the original $500 deposit for 018885
"""
import psycopg2
import os
from datetime import datetime


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )


def main():
    conn = connect()
    cur = conn.cursor()

    print('=== CURRENT STATUS ===\n')
    
    for reserve in ['018885', '019127']:
        cur.execute("""
            SELECT charter_id, reserve_number, charter_date,
                   total_amount_due, paid_amount, balance, client_id
            FROM charters
            WHERE reserve_number = %s
        """, (reserve,))
        r = cur.fetchone()
        if r:
            print(f'Reserve {reserve}:')
            print(f'  Charter ID: {r[0]} | Date: {r[2]} | Client: {r[6]}')
            print(f'  Total Due: ${r[3]:.2f}' if r[3] else 'Total Due: $0.00')
            print(f'  Paid: ${r[4]:.2f}' if r[4] else 'Paid: $0.00')
            print(f'  Balance: ${r[5]:.2f}' if r[5] else 'Balance: $0.00')
            
            cur.execute("""
                SELECT SUM(amount) FROM charter_charges
                WHERE reserve_number = %s
            """, (reserve,))
            charges_sum = cur.fetchone()[0] or 0
            print(f'  Charges Sum: ${charges_sum:.2f}')
            
            cur.execute("""
                SELECT payment_id, amount, payment_date, notes
                FROM payments
                WHERE reserve_number = %s
                ORDER BY payment_date
            """, (reserve,))
            pays = cur.fetchall()
            if pays:
                total_paid = sum(p[1] for p in pays if p[1])
                print(f'  Payments ({len(pays)}, total ${total_paid:.2f}):')
                for p in pays:
                    print(f'    Payment {p[0]}: ${p[1]:.2f} on {p[2]}')
                    if p[3]:
                        print(f'      {p[3][:80]}')
            else:
                print(f'  No payments linked')
            print()

    print('\n=== EXPECTED VS ACTUAL ===')
    print('Reserve 018885 (per document):')
    print('  Expected Total: $1,183.87')
    print('  Expected Deposit: $500.00')
    print('  Expected Balance: $683.87')
    
    print('\nReserve 019127 (per document):')
    print('  Expected Total: $184.50')
    print('  Expected Deposit: $184.50')
    print('  Expected Balance: $0.00')
    
    print('\n\n=== SEARCHING FOR $500 DEPOSIT (before 07/29/2025) ===')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
        FROM payments
        WHERE payment_date < '2025-07-29'
          AND amount = 500.00
          AND (reserve_number IN ('018885', '019127') OR reserve_number IS NULL)
        ORDER BY payment_date DESC
        LIMIT 10
    """)
    deposits = cur.fetchall()
    if deposits:
        print(f'Found {len(deposits)} $500 payments:')
        for d in deposits:
            print(f'  Payment {d[0]}: Reserve {d[1]} | ${d[2]:.2f} | {d[3]} | {d[4]}')
            if d[5]:
                print(f'    {d[5][:100]}')
    else:
        print('No $500 deposits found')

    print('\n\n=== PAYMENT ALLOCATION PLAN ===')
    print('Current situation:')
    print('  - Payment 78672 ($204.17) → currently on 018885')
    print('  - Payment 78690 ($712.05) → currently on 018885')
    print('  - Total: $916.22')
    
    print('\nProposed allocation:')
    print('  1. Find/verify $500 deposit for 018885')
    print('  2. Allocate $184.50 from payment 78672 ($204.17) to 019127')
    print('  3. Create split: $184.50 to 019127, remaining $19.67 to 018885')
    print('  4. Keep payment 78690 ($712.05) on 018885')
    print('  5. Final 018885: $500 + $19.67 + $712.05 = $1,231.72')
    print('     (covers $1,183.87 total + $47.85 overpayment)')
    
    print('\nAlternative allocation:')
    print('  1. Payment 78690 ($712.05) - $683.87 balance = $28.18 credit')
    print('  2. Payment 78672 ($204.17) - $184.50 = $19.67 credit')
    print('  3. Total credit: $47.85 (matches overpayment if $500 deposit exists)')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
