"""
Calculate if payment reallocations result in zero balances for all three reserves.

Current situation:
- 018885: Total $1,183.87, Paid $1,895.92 (has payments: $500 + $479.70 + $204.17 + $712.05)
- 019127: Total $184.50, Paid $0.00
- 019238: Total $0.00, Paid $0.00, Charges $0.00

Proposed:
- Move $479.70 from 018885 to 019238
- Move $184.50 from 018885 to 019127
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

    reserves = ['018885', '019127', '019238']
    
    print('=== CURRENT STATUS ===\n')
    current = {}
    for reserve in reserves:
        cur.execute("""
            SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance
            FROM charters WHERE reserve_number = %s
        """, (reserve,))
        r = cur.fetchone()
        if r:
            cur.execute("""
                SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s
            """, (reserve,))
            charges = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT payment_id, amount, payment_date
                FROM payments WHERE reserve_number = %s
                ORDER BY payment_date
            """, (reserve,))
            payments = cur.fetchall()
            
            current[reserve] = {
                'total_due': r[2] or 0,
                'paid': r[3] or 0,
                'balance': r[4] or 0,
                'charges': charges,
                'payments': payments
            }
            
            print(f'{reserve}:')
            print(f'  Total Due: ${current[reserve]["total_due"]:.2f}')
            print(f'  Charges Sum: ${current[reserve]["charges"]:.2f}')
            print(f'  Paid: ${current[reserve]["paid"]:.2f}')
            print(f'  Balance: ${current[reserve]["balance"]:.2f}')
            if payments:
                print(f'  Payments ({len(payments)}):')
                for p in payments:
                    print(f'    {p[0]}: ${p[1]:.2f} on {p[2]}')
            print()

    print('\n=== PAYMENT REALLOCATION SCENARIOS ===\n')
    
    # Scenario 1: Just move $479.70 to 019238
    print('Scenario 1: Move $479.70 (payment 78348) to 019238')
    print('  018885: $1,895.92 - $479.70 = $1,416.22 paid vs $1,183.87 due → Balance: -$232.35 (overpaid)')
    print('  019238: $0.00 + $479.70 = $479.70 paid vs $0.00 due → Balance: -$479.70 (overpaid)')
    print('  019127: $0.00 paid vs $184.50 due → Balance: $184.50 (underpaid)')
    print('  [FAIL] Does NOT balance to zero\n')
    
    # Scenario 2: Move $479.70 to 019238 AND move $184.50 to 019127
    print('Scenario 2: Move $479.70 to 019238 AND $184.50 to 019127')
    print('  Need to split one of the 018885 payments:')
    print('  Option A: Split payment 78672 ($204.17)')
    print('    - $184.50 → 019127')
    print('    - $19.67 → stays on 018885')
    print('  Option B: Split payment 78690 ($712.05)')
    print('    - $184.50 → 019127')
    print('    - $527.55 → stays on 018885\n')
    
    print('  Result with Option A (split 78672):')
    print('    018885: $500 + $479.70 - $479.70 + $19.67 + $712.05 = $1,232.02 paid vs $1,183.87 due')
    print('           Wait, recalc: $500 + $19.67 + $712.05 = $1,231.72 paid')
    print('           Balance: -$47.85 (overpaid)')
    print('    019238: $479.70 paid vs $0.00 due → Balance: -$479.70 (overpaid)')
    print('    019127: $184.50 paid vs $184.50 due → Balance: $0.00 ✓')
    print('    [FAIL] Does NOT balance to zero (019238 has no charges!)\n')

    print('=== KEY ISSUE ===')
    print('019238 has $0.00 in charter_charges!')
    print('If we move $479.70 to 019238, it will show as overpaid.')
    print('\nTwo possibilities:')
    print('1. 019238 is missing charges (need to import from LMS or reservation doc)')
    print('2. Payment 78348 ($479.70) was incorrectly allocated and belongs elsewhere')
    
    print('\n=== CHECKING 019238 IN DETAIL ===')
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, client_id,
               pickup_address, dropoff_address, vehicle, status
        FROM charters WHERE reserve_number = '019238'
    """)
    r = cur.fetchone()
    if r:
        print(f'Charter {r[0]} | Reserve {r[1]} | Date {r[2]}')
        print(f'Client: {r[3]}')
        print(f'Pickup: {r[4]}')
        print(f'Dropoff: {r[5]}')
        print(f'Vehicle: {r[6]}')
        print(f'Status: {r[7]}')
    
    print('\n=== RECOMMENDATION ===')
    print('Before reallocating payment 78348 to 019238:')
    print('1. Check if 019238 has charges in LMS that need to be imported')
    print('2. Verify the reservation document for 019238 shows $479.70 total')
    print('3. If 019238 should have $479.70 in charges, import them first')
    print('4. Then reallocate the payment')
    
    print('\nFor 019127:')
    print('Need to split payment 78672 ($204.17) or 78690 ($712.05)')
    print('to allocate $184.50 to 019127')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
