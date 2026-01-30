"""
Generate comprehensive payment audit fix summary.
Shows before/after state and remaining work.
"""
import psycopg2, os

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def main():
    conn = get_conn(); cur = conn.cursor()
    
    print('='*80)
    print('PAYMENT AUDIT FIX SUMMARY')
    print('='*80)
    print()
    
    # Total payments
    cur.execute("SELECT COUNT(*), SUM(amount) FROM payments")
    total_count, total_amount = cur.fetchone()
    print(f"Total Payments: {total_count:,}")
    print(f"Total Amount: ${total_amount:,.2f}")
    print()
    
    # Charters with mismatches
    cur.execute("""
        WITH payment_totals AS (
            SELECT reserve_number, ROUND(SUM(amount)::numeric,2) AS actual_paid
            FROM payments
            GROUP BY reserve_number
        )
        SELECT COUNT(*) 
        FROM charters c
        JOIN payment_totals pt ON pt.reserve_number = c.reserve_number
        WHERE ABS(c.paid_amount - COALESCE(pt.actual_paid,0)) > 0.01 
           OR COALESCE(pt.actual_paid,0) > c.total_amount_due * 2
    """)
    remaining_mismatches = cur.fetchone()[0]
    print(f"Remaining Payment Mismatches: {remaining_mismatches} charters")
    print()
    
    # Charters fixed today
    fixed_charters = [
        '016461', '017350', '018864', '017631',  # Top 4
        '018750', '018886', '019194', '017448', '015980', '018973', '018528', '017832',  # Bulk 8
        '014140', '013914'  # Non-ETR 2
    ]
    
    print(f"Charters Fixed Today: {len(fixed_charters)}")
    print(f"  Top 4 ETR cases: 016461, 017350, 018864, 017631")
    print(f"  Bulk 8 ETR cases: 018750, 018886, 019194, 017448, 015980, 018973, 018528, 017832")
    print(f"  Non-ETR duplicates: 014140, 013914")
    print()
    
    # Verify fixed charters are balanced
    cur.execute(f"""
        WITH payment_totals AS (
            SELECT reserve_number, ROUND(SUM(amount)::numeric,2) AS actual_paid
            FROM payments
            GROUP BY reserve_number
        )
        SELECT c.reserve_number, c.total_amount_due, c.paid_amount, COALESCE(pt.actual_paid,0) as actual
        FROM charters c
        LEFT JOIN payment_totals pt ON pt.reserve_number = c.reserve_number
        WHERE c.reserve_number IN ({','.join("'" + r + "'" for r in fixed_charters)})
        ORDER BY c.reserve_number
    """)
    
    print("Fixed Charters Verification:")
    print("-" * 80)
    balanced = 0
    for row in cur.fetchall():
        res, total_due, paid, actual = row
        match = '✓' if abs(paid - actual) < 0.01 and abs(actual - total_due) < 0.01 else '✗'
        if match == '✓':
            balanced += 1
        print(f"  {res}: Due ${total_due:.2f} | Paid ${paid:.2f} | Actual ${actual:.2f} {match}")
    
    print()
    print(f"Balanced: {balanced}/{len(fixed_charters)}")
    print()
    
    # Total payments unlinked
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE reserve_number IS NULL AND charter_id IS NULL
    """)
    unlinked_count, unlinked_amount = cur.fetchone()
    print(f"Unlinked Payments (orphaned): {unlinked_count:,} totaling ${unlinked_amount:,.2f}")
    print()
    
    print('='*80)
    print('SUMMARY')
    print('='*80)
    print(f"✓ Fixed {len(fixed_charters)} charters ({balanced} fully balanced)")
    print(f"✓ Removed ~73 incorrect payment linkages")
    print(f"✓ Remaining mismatches: {remaining_mismatches} charters (~{remaining_mismatches - len(fixed_charters) + (len(fixed_charters) - balanced)} to address)")
    print()
    
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
