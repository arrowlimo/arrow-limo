#!/usr/bin/env python
"""
Populate missing total_amount_due from charter_charges sums.

For charters with $0 total_amount_due but with charter_charges entries,
set total_amount_due = SUM(charter_charges.amount).
"""
import argparse
from datetime import datetime
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def main():
    parser = argparse.ArgumentParser(description="Populate total_amount_due from charter_charges")
    parser.add_argument("--write", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    print("=" * 80)
    print("POPULATE TOTAL_AMOUNT_DUE FROM CHARTER_CHARGES")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    
    # Analyze what needs updating
    cur.execute("""
        WITH charge_sums AS (
            SELECT cc.charter_id, COALESCE(SUM(cc.amount), 0) AS charges_total
            FROM charter_charges cc
            GROUP BY cc.charter_id
        )
        SELECT COUNT(*),
               COALESCE(SUM(cs.charges_total), 0) AS total_charges,
               COALESCE(SUM(c.paid_amount), 0) AS total_paid
        FROM charters c
        JOIN charge_sums cs ON cs.charter_id = c.charter_id
        WHERE COALESCE(c.total_amount_due, 0) = 0
        AND cs.charges_total > 0
    """)
    count, charges_sum, paid_sum = cur.fetchone()
    
    print(f"\nCharters to update: {count:,}")
    print(f"Total charges to set: ${float(charges_sum):,.2f}")
    print(f"Total paid into these charters: ${float(paid_sum):,.2f}")
    print(f"Expected new balance: ${float(charges_sum - paid_sum):,.2f}")
    
    # Sample before
    print("\nSample (first 10):")
    cur.execute("""
        WITH charge_sums AS (
            SELECT cc.charter_id, COALESCE(SUM(cc.amount), 0) AS charges_total
            FROM charter_charges cc
            GROUP BY cc.charter_id
        )
        SELECT c.reserve_number, c.charter_date,
               c.total_amount_due AS current_total,
               cs.charges_total AS new_total,
               c.paid_amount,
               c.balance AS current_balance,
               ROUND(cs.charges_total - COALESCE(c.paid_amount, 0), 2) AS new_balance
        FROM charters c
        JOIN charge_sums cs ON cs.charter_id = c.charter_id
        WHERE COALESCE(c.total_amount_due, 0) = 0
        AND cs.charges_total > 0
        ORDER BY cs.charges_total DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        reserve, date, curr_total, new_total, paid, curr_bal, new_bal = row
        print(f"\n  {reserve} ({date})")
        print(f"    total_amount_due: ${float(curr_total or 0):,.2f} → ${float(new_total):,.2f}")
        print(f"    paid_amount: ${float(paid or 0):,.2f}")
        print(f"    balance: ${float(curr_bal or 0):,.2f} → ${float(new_bal):,.2f}")
    
    if args.write:
        print("\n" + "=" * 80)
        print("APPLYING UPDATE")
        print("=" * 80)
        
        # Update total_amount_due
        cur.execute("""
            WITH charge_sums AS (
                SELECT cc.charter_id, COALESCE(SUM(cc.amount), 0) AS charges_total
                FROM charter_charges cc
                GROUP BY cc.charter_id
            )
            UPDATE charters c
            SET total_amount_due = cs.charges_total
            FROM charge_sums cs
            WHERE cs.charter_id = c.charter_id
            AND COALESCE(c.total_amount_due, 0) = 0
            AND cs.charges_total > 0
        """)
        updated_total = cur.rowcount
        print(f"✓ Updated {updated_total:,} charters.total_amount_due")
        
        # Recalculate balances for these charters
        cur.execute("""
            UPDATE charters
            SET balance = ROUND(COALESCE(total_amount_due, 0) - COALESCE(paid_amount, 0), 2)
            WHERE charter_id IN (
                SELECT cc.charter_id
                FROM charter_charges cc
                GROUP BY cc.charter_id
                HAVING COALESCE(SUM(cc.amount), 0) > 0
            )
        """)
        updated_balance = cur.rowcount
        print(f"✓ Updated {updated_balance:,} charters.balance")
        
        conn.commit()
        
        # Verify results
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        
        cur.execute("""
            SELECT 
                COUNT(*) FILTER(WHERE balance > 0.01) AS positive,
                COUNT(*) FILTER(WHERE balance < -0.01) AS negative,
                COUNT(*) FILTER(WHERE ABS(balance) <= 0.01) AS zero,
                COALESCE(SUM(balance) FILTER(WHERE balance > 0.01), 0) AS positive_sum,
                COALESCE(SUM(balance) FILTER(WHERE balance < -0.01), 0) AS negative_sum
            FROM charters
            WHERE (cancelled IS NULL OR cancelled = FALSE)
        """)
        positive, negative, zero, pos_sum, neg_sum = cur.fetchone()
        
        print(f"\nNon-cancelled charter balance distribution:")
        print(f"  Positive (owed to you): {positive:,} (${float(pos_sum):,.2f})")
        print(f"  Negative (credits): {negative:,} (${float(neg_sum):,.2f})")
        print(f"  Zero: {zero:,}")
        
        print("\n✓ All changes committed")
    else:
        conn.rollback()
        print("\n" + "=" * 80)
        print("DRY RUN COMPLETE - No changes made")
        print("=" * 80)
        print("To apply fix, run with --write flag")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
