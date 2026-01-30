"""
Search for payment of $465.73 on 03/24/2025 with reference #dor5
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

    print('=== SEARCHING FOR PAYMENT $465.73 ON 03/24/2025 #dor5 ===\n')

    print('Exact amount match on 03/24/2025:')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               payment_method, square_payment_id, payment_key, 
               reference_number, square_customer_email, notes
        FROM payments
        WHERE payment_date = '2025-03-24'
          AND amount = 465.73
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f'\nPayment ID: {r[0]}')
            print(f'Reserve: {r[1]}')
            print(f'Amount: ${r[2]:.2f}')
            print(f'Date: {r[3]}')
            print(f'Method: {r[4]}')
            print(f'Square ID: {r[5]}')
            print(f'Payment Key: {r[6]}')
            print(f'Reference: {r[7]}')
            print(f'Email: {r[8]}')
            if r[9]:
                print(f'Notes: {r[9][:150]}')
    else:
        print('No exact match found')

    print('\n\nNear amount ($460-$470) on 03/24/2025:')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               payment_method, square_payment_id, notes
        FROM payments
        WHERE payment_date = '2025-03-24'
          AND amount >= 460 AND amount <= 470
        ORDER BY amount DESC
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f'  Payment {r[0]}: Reserve {r[1]} | ${r[2]:.2f} | {r[4]} | Square: {r[5]}')
            if r[6]:
                print(f'    Notes: {r[6][:100]}')
    else:
        print('No near matches')

    print('\n\nSearching for reference #dor5:')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               square_payment_id, payment_key, reference_number, notes
        FROM payments
        WHERE square_payment_id ILIKE '%dor5%'
           OR payment_key ILIKE '%dor5%'
           OR reference_number ILIKE '%dor5%'
           OR notes ILIKE '%dor5%'
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f'\nPayment ID: {r[0]} | Reserve: {r[1]} | ${r[2]:.2f} | {r[3]}')
            print(f'  Square ID: {r[4]}')
            print(f'  Payment Key: {r[5]}')
            print(f'  Reference: {r[6]}')
            if r[7]:
                print(f'  Notes: {r[7][:100]}')
    else:
        print('No payments found with reference dor5')

    print('\n\nAll payments on 03/24/2025 (showing first 30):')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_method, notes
        FROM payments
        WHERE payment_date = '2025-03-24'
        ORDER BY amount DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    if rows:
        print(f'Found {len(rows)} payments on 03/24/2025:')
        for r in rows:
            print(f'  Payment {r[0]}: {r[1]} | ${r[2]:.2f} | {r[3]}')
            if r[4]:
                print(f'    {r[4][:80]}')

    print('\n\n=== RESERVE 019238 DETAILS (03/24/2025) ===')
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date,
               total_amount_due, paid_amount, balance, client_id
        FROM charters
        WHERE reserve_number = '019238'
    """)
    r = cur.fetchone()
    if r:
        print(f'Charter ID: {r[0]} | Date: {r[2]} | Client: {r[6]}')
        print(f'Total Due: ${r[3]:.2f}' if r[3] else 'Total Due: $0.00')
        print(f'Paid: ${r[4]:.2f}' if r[4] else 'Paid: $0.00')
        print(f'Balance: ${r[5]:.2f}' if r[5] else 'Balance: $0.00')
        
        cur.execute("""
            SELECT description, amount FROM charter_charges
            WHERE reserve_number = '019238'
        """)
        charges = cur.fetchall()
        if charges:
            print('Charges:')
            for c in charges:
                print(f'  {c[0]}: ${c[1]:.2f}')
        
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_method
            FROM payments WHERE reserve_number = '019238'
            ORDER BY payment_date
        """)
        pays = cur.fetchall()
        if pays:
            print('Payments:')
            for p in pays:
                print(f'  Payment {p[0]}: ${p[1]:.2f} on {p[2]} ({p[3]})')
        else:
            print('No payments linked')
    else:
        print('Reserve 019238 not found')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
