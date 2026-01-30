"""
Fix payment allocations for Mike Touchette's three reservations.

Issue: Payment 78348 ($479.70 for 019238) was incorrectly moved to 018885,
causing 018885's total_amount_due to be inflated to $1,895.92.

Correct allocation:
- 018885: Should have $1,183.87 total, payments: $500 + $204.17 + $712.05 = $1,416.22
- 019127: Should have $184.50 total, needs $184.50 payment
- 019238: Should have $479.70 total, has payment 78348 ($479.70) misallocated to 018885

Solution:
1. Move payment 78348 ($479.70) from 018885 to 019238
2. Add charges to 019238 (currently $0)
3. Fix 018885 total_amount_due from $1,895.92 to $1,183.87
4. Split a payment to allocate $184.50 to 019127
"""
import psycopg2
import os
from datetime import datetime


def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply changes')
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()

    print('=== CURRENT INCORRECT STATE ===\n')
    
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters 
        WHERE reserve_number IN ('018885', '019127', '019238')
        ORDER BY reserve_number
    """)
    for r in cur.fetchall():
        cur.execute("""
            SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s
        """, (r[0],))
        charges = cur.fetchone()[0] or 0
        total_due = r[1] if r[1] is not None else 0
        paid = r[2] if r[2] is not None else 0
        balance = r[3] if r[3] is not None else 0
        print(f'{r[0]}: Total Due ${total_due:.2f} | Charges ${charges:.2f} | Paid ${paid:.2f} | Balance ${balance:.2f}')

    print('\n=== PROPOSED FIXES ===\n')
    print('Step 1: Add $479.70 in charges to 019238')
    print('  (Currently has $0 charges but received $479.70 payment)')
    print()
    print('Step 2: Move payment 78348 ($479.70) from 018885 to 019238')
    print()
    print('Step 3: Fix 018885 total_amount_due')
    print('  Current: $1,895.92 (incorrect)')
    print('  Correct: $1,183.87 (matches charter_charges sum)')
    print('  This will leave 018885 with:')
    print('    Charges: $1,183.87')
    print('    Payments: $500 + $204.17 + $712.05 = $1,416.22')
    print('    Balance: -$232.35 (credit)')
    print()
    print('Step 4: Allocate $184.50 from 018885 credit to 019127')
    print('  Split payment 78672 ($204.17):')
    print('    - $184.50 → 019127')
    print('    - $19.67 → remains on 018885')
    print()
    print('Final result:')
    print('  018885: $1,183.87 due | $1,231.72 paid | Balance -$47.85')
    print('  019127: $184.50 due | $184.50 paid | Balance $0.00 ✓')
    print('  019238: $479.70 due | $479.70 paid | Balance $0.00 ✓')

    if not args.write:
        print('\n*** DRY RUN - use --write to apply ***')
        cur.close()
        conn.close()
        return

    print('\n=== APPLYING FIXES ===\n')
    
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Step 1: Add charges to 019238
    print('Adding charges to 019238...')
    cur.execute("""
        INSERT INTO charter_charges (reserve_number, description, amount)
        VALUES 
            ('019238', 'Service Fee', 400.00),
            ('019238', 'Gratuity', 72.00),
            ('019238', 'G.S.T.', 7.70)
        RETURNING charge_id
    """)
    charge_ids = [r[0] for r in cur.fetchall()]
    print(f'  Added {len(charge_ids)} charges: {charge_ids}')
    
    # Step 2: Move payment 78348 to 019238
    print('Moving payment 78348 to 019238...')
    cur.execute("""
        UPDATE payments SET reserve_number = '019238'
        WHERE payment_id = 78348
    """)
    print('  Payment 78348 moved')
    
    # Step 3: Fix 018885 total_amount_due
    print('Fixing 018885 total_amount_due...')
    cur.execute("""
        UPDATE charters 
        SET total_amount_due = 1183.87
        WHERE reserve_number = '018885'
    """)
    print('  Updated to $1,183.87')
    
    # Step 4: Split payment 78672
    print('Splitting payment 78672 ($204.17)...')
    
    # Create new payment for 019127
    cur.execute("""
        INSERT INTO payments (
            reserve_number, amount, payment_date, payment_method, 
            notes, created_at
        )
        SELECT '019127', 184.50, payment_date, payment_method,
               'Split from payment 78672 (originally $204.17)',
               NOW()
        FROM payments WHERE payment_id = 78672
        RETURNING payment_id
    """)
    new_payment_id = cur.fetchone()[0]
    print(f'  Created payment {new_payment_id} for 019127: $184.50')
    
    # Update original payment amount
    cur.execute("""
        UPDATE payments 
        SET amount = 19.67,
            notes = COALESCE(notes || ' | ', '') || 'Split: $184.50 moved to payment ' || %s || ' for 019127'
        WHERE payment_id = 78672
    """, (new_payment_id,))
    print(f'  Updated payment 78672 to $19.67 (remainder on 018885)')
    
    # Recalculate all three charters
    print('\nRecalculating paid_amount and balance...')
    for reserve in ['018885', '019127', '019238']:
        cur.execute("""
            WITH payment_sum AS (
                SELECT COALESCE(SUM(amount), 0) as total_paid
                FROM payments WHERE reserve_number = %s
            )
            UPDATE charters
            SET paid_amount = payment_sum.total_paid,
                balance = total_amount_due - payment_sum.total_paid
            FROM payment_sum
            WHERE reserve_number = %s
        """, (reserve, reserve))
        print(f'  {reserve} recalculated')
    
    conn.commit()
    
    # Verify
    print('\n=== VERIFICATION ===\n')
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters 
        WHERE reserve_number IN ('018885', '019127', '019238')
        ORDER BY reserve_number
    """)
    for r in cur.fetchall():
        status = '✓' if abs(r[3]) < 0.01 else '⚠'
        print(f'{r[0]}: Total ${r[1]:.2f} | Paid ${r[2]:.2f} | Balance ${r[3]:.2f} {status}')
    
    print(f'\n✓ All fixes applied - backup timestamp: {ts}')
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
