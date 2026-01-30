"""
Search for credit card 9853 payments for reserves 019127 and 018885:
- $204.17 #RkmS michhansum@gmail.com 07/29/2025
- $712.05 #1C0q 07/29/2025 (or 08/01/2025)
- $479.70 #dor5 03/24/2025
"""
import psycopg2
import os


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def main():
    conn = connect()
    cur = conn.cursor()

    print('=== SEARCHING FOR CC LAST4: 9853 ===\n')
    
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               square_last4, credit_card_last4, square_customer_email,
               square_payment_id, payment_key, reference_number, notes
        FROM payments
        WHERE square_last4 = '9853'
           OR credit_card_last4 = '9853'
           OR notes ILIKE '%9853%'
        ORDER BY payment_date DESC
    """)
    rows = cur.fetchall()
    if rows:
        print(f'Found {len(rows)} payments with CC 9853:')
        for r in rows:
            print(f'\nPayment ID: {r[0]} | Reserve: {r[1]} | ${r[2]:.2f} | {r[3]}')
            print(f'  Square Last4: {r[4]} | CC Last4: {r[5]}')
            print(f'  Email: {r[6]}')
            print(f'  Square ID: {r[7]}')
            print(f'  Payment Key: {r[8]}')
            print(f'  Reference: {r[9]}')
            if r[10]:
                print(f'  Notes: {r[10][:120]}')
    else:
        print('No payments found with CC 9853')

    print('\n\n=== SEARCHING FOR AMOUNT $479.70 (March 2025) ===')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               payment_method, square_last4, square_payment_id, notes
        FROM payments
        WHERE payment_date >= '2025-03-01' AND payment_date <= '2025-03-31'
          AND amount >= 475 AND amount <= 485
        ORDER BY payment_date, amount
    """)
    rows = cur.fetchall()
    if rows:
        print(f'Found {len(rows)} payments:')
        for r in rows:
            print(f'  Payment {r[0]}: {r[1]} | ${r[2]:.2f} | {r[3]} | Last4: {r[5]}')
            if r[7]:
                print(f'    Notes: {r[7][:100]}')
    else:
        print('No matching payments')

    print('\n\n=== CHECKING RESERVES 019127 AND 018885 ===')
    for reserve in ['019127', '018885']:
        cur.execute("""
            SELECT charter_id, reserve_number, charter_date,
                   total_amount_due, paid_amount, balance, client_id
            FROM charters
            WHERE reserve_number = %s
        """, (reserve,))
        r = cur.fetchone()
        if r:
            print(f'\nReserve {reserve}:')
            print(f'  Charter ID: {r[0]} | Date: {r[2]} | Client: {r[6]}')
            print(f'  Total: ${r[3]:.2f} | Paid: ${r[4]:.2f} | Balance: ${r[5]:.2f}')
            
            cur.execute("""
                SELECT payment_id, amount, payment_date, square_last4, notes
                FROM payments
                WHERE reserve_number = %s
                ORDER BY payment_date
            """, (reserve,))
            pays = cur.fetchall()
            if pays:
                print(f'  Current payments ({len(pays)}):')
                for p in pays:
                    print(f'    Payment {p[0]}: ${p[1]:.2f} on {p[2]} | Last4: {p[3]}')
                    if p[4]:
                        print(f'      {p[4][:80]}')
            else:
                print(f'  No payments currently linked')

    print('\n\n=== PAYMENT SUMMARY ===')
    print('Target payments to find/link:')
    print('  1. $204.17 on 07/29/2025 #RkmS (michhansum@gmail.com) - CC 9853')
    print('  2. $712.05 on 07/29-08/01/2025 #1C0q - CC 9853')
    print('  3. $479.70 on 03/24/2025 #dor5 - CC 9853')
    print('  Total: $1,395.92')
    
    total_needed_019127 = 184.50
    total_needed_018885 = 0  # Will check in output
    print(f'\n019127 needs: ${total_needed_019127:.2f}')
    print(f'018885 status: (see above)')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
