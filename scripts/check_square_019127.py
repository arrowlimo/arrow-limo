"""
Check Square payments for reserve 019127 and specific references.
Looking for:
- michhansum@gmail.com
- Amounts: $204.17, $712.05
- Reference codes: #RkmS, #1C0q
- Date: July 29, 2025
"""
import psycopg2
import os


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

    print('=== RESERVE 019127 CHARTER DETAILS ===')
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, 
               total_amount_due, paid_amount, balance,
               client_id, status, client_notes
        FROM charters 
        WHERE reserve_number = '019127'
    """)
    r = cur.fetchone()
    if r:
        print(f'Charter ID: {r[0]}')
        print(f'Reserve: {r[1]}')
        print(f'Date: {r[2]}')
        print(f'Total Due: ${r[3]:.2f}' if r[3] else 'Total Due: $0.00')
        print(f'Paid: ${r[4]:.2f}' if r[4] else 'Paid: $0.00')
        print(f'Balance: ${r[5]:.2f}' if r[5] else 'Balance: $0.00')
        print(f'Client ID: {r[6]}')
        print(f'Status: {r[7]}')
        print(f'Notes: {r[8][:200] if r[8] else "None"}')
    else:
        print('No charter found')

    print('\n=== CHARTER CHARGES FOR 019127 ===')
    cur.execute("""
        SELECT charge_id, description, amount
        FROM charter_charges
        WHERE reserve_number = '019127'
    """)
    charges = cur.fetchall()
    if charges:
        total = 0
        for c in charges:
            print(f'  Charge {c[0]}: {c[1]} - ${c[2]:.2f}')
            total += c[2] if c[2] else 0
        print(f'  Total charges: ${total:.2f}')
    else:
        print('No charges found')

    print('\n=== PAYMENTS LINKED TO 019127 ===')
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method,
               square_customer_email, square_last4, square_payment_id,
               payment_key, reference_number, notes
        FROM payments
        WHERE reserve_number = '019127'
        ORDER BY payment_date
    """)
    payments = cur.fetchall()
    if payments:
        total_paid = 0
        for p in payments:
            print(f'\nPayment ID: {p[0]} | ${p[1]:.2f} | {p[2]}')
            print(f'  Method: {p[3]}')
            print(f'  Email: {p[4]}')
            print(f'  Last4: {p[5]}')
            print(f'  Square ID: {p[6]}')
            print(f'  Payment Key: {p[7]}')
            print(f'  Reference: {p[8]}')
            if p[9]:
                print(f'  Notes: {p[9][:100]}')
            total_paid += p[1] if p[1] else 0
        print(f'\nTotal payments: ${total_paid:.2f}')
    else:
        print('No payments linked to 019127')

    print('\n=== SQUARE PAYMENTS WITH EMAIL michhansum@gmail.com ===')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               square_customer_email, square_last4, square_payment_id,
               square_status, notes
        FROM payments
        WHERE square_customer_email ILIKE '%michhansum%'
           OR notes ILIKE '%michhansum%'
        ORDER BY payment_date DESC
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f'\nPayment ID: {r[0]}')
            print(f'Reserve: {r[1]}')
            print(f'Amount: ${r[2]:.2f}' if r[2] else 'Amount: $0.00')
            print(f'Date: {r[3]}')
            print(f'Email: {r[4]}')
            print(f'Last4: {r[5]}')
            print(f'Square ID: {r[6]}')
            print(f'Status: {r[7]}')
            if r[8]:
                print(f'Notes: {r[8][:100]}')
    else:
        print('No payments found with that email')

    print('\n=== SQUARE PAYMENTS ~$204 OR ~$712 (July-August 2025) ===')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               square_customer_email, square_last4, square_payment_id,
               payment_method, notes
        FROM payments
        WHERE payment_date >= '2025-07-01' AND payment_date <= '2025-08-31'
          AND (
              (amount >= 200 AND amount <= 210)
              OR (amount >= 710 AND amount <= 720)
          )
        ORDER BY payment_date DESC, amount DESC
    """)
    rows = cur.fetchall()
    if rows:
        print(f'Found {len(rows)} payments:')
        for r in rows:
            print(f'\nPayment ID: {r[0]} | Reserve: {r[1]} | ${r[2]:.2f} | {r[3]}')
            print(f'  Email: {r[4]}')
            print(f'  Last4: {r[5]} | Square ID: {r[6]}')
            print(f'  Method: {r[7]}')
            if r[8]:
                print(f'  Notes: {r[8][:100]}')
    else:
        print('No matching payments in amount range')

    print('\n=== CHECKING SQUARE REFERENCE CODES #RkmS and #1C0q ===')
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date,
               square_payment_id, payment_key, reference_number,
               square_customer_email, notes
        FROM payments
        WHERE square_payment_id ILIKE '%RkmS%'
           OR square_payment_id ILIKE '%1C0q%'
           OR payment_key ILIKE '%RkmS%'
           OR payment_key ILIKE '%1C0q%'
           OR reference_number ILIKE '%RkmS%'
           OR reference_number ILIKE '%1C0q%'
           OR notes ILIKE '%RkmS%'
           OR notes ILIKE '%1C0q%'
    """)
    rows = cur.fetchall()
    if rows:
        print(f'Found {len(rows)} payments with reference codes:')
        for r in rows:
            print(f'\nPayment ID: {r[0]} | Reserve: {r[1]} | ${r[2]:.2f} | {r[3]}')
            print(f'  Square ID: {r[4]}')
            print(f'  Payment Key: {r[5]}')
            print(f'  Reference: {r[6]}')
            print(f'  Email: {r[7]}')
            if r[8]:
                print(f'  Notes: {r[8][:100]}')
    else:
        print('No payments found with those reference codes')

    print('\n=== CHECKING PAYMENT_IMPORTS FOR SQUARE DATA ===')
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'payment_imports'
    """)
    if cur.fetchone()[0] > 0:
        cur.execute("""
            SELECT payment_id, reserve_number, amount, payment_date,
                   payment_method, notes
            FROM payment_imports
            WHERE payment_date >= '2025-07-29' AND payment_date <= '2025-07-31'
              AND (amount >= 200 AND amount <= 210 OR amount >= 710 AND amount <= 720)
        """)
        rows = cur.fetchall()
        if rows:
            print(f'Found {len(rows)} matching imports:')
            for r in rows:
                print(f'  Import ID: {r[0]} | Reserve: {r[1]} | ${r[2]:.2f} | {r[3]} | {r[4]}')
        else:
            print('No matching records in payment_imports')
    else:
        print('payment_imports table does not exist')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
