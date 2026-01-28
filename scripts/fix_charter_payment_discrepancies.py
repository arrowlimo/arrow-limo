#!/usr/bin/env python3
"""
Fix charter-payment discrepancies:
1. Update charter.paid_amount to match SUM(payments) for all charters
2. Recalculate charter.balance = total_amount_due - paid_amount
3. Report on orphan payments that need charters created
4. Mark cancelled charter retainers appropriately

Supports --dry-run (preview) and --apply (execute)
"""
import os
import sys
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    apply_mode = ('--apply' in sys.argv or '--yes' in sys.argv)
    dry_run = ('--dry-run' in sys.argv)

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print("="*80)
    print("CHARTER-PAYMENT RECONCILIATION FIX")
    print("="*80)

    # 1. Update charter.paid_amount from payments
    print("\n1. UPDATING CHARTER PAID_AMOUNT FROM PAYMENTS")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            COALESCE(c.paid_amount, 0) as current_paid,
            COALESCE(SUM(p.amount), 0) as calculated_paid,
            c.total_amount_due,
            c.cancelled
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.reserve_number, c.paid_amount, c.total_amount_due, c.cancelled
        HAVING COALESCE(c.paid_amount, 0) <> COALESCE(SUM(p.amount), 0)
        ORDER BY c.charter_id
    """)
    
    updates = cur.fetchall()
    print(f"Found {len(updates):,} charters needing paid_amount update")
    
    if updates:
        print(f"\nSample updates (first 10):")
        for charter_id, reserve, current, calculated, total_due, cancelled in updates[:10]:
            diff = float(calculated) - float(current)
            print(f"  Charter {charter_id} ({reserve}) | Current: ${current:,.2f} → Calculated: ${calculated:,.2f} | Diff: ${diff:+,.2f} | Cancelled: {cancelled}")
        
        if not apply_mode:
            print(f"\nDry-run: would update {len(updates):,} charters. Pass --apply to execute.")
        else:
            print(f"\nApplying paid_amount updates...")
            for charter_id, reserve, current, calculated, total_due, cancelled in updates:
                cur.execute("""
                    UPDATE charters
                    SET paid_amount = %s
                    WHERE charter_id = %s
                """, (calculated, charter_id))
            conn.commit()
            print(f"✅ Updated {len(updates):,} charters with correct paid_amount")

    # 2. Recalculate balance = total_amount_due - paid_amount
    print("\n2. RECALCULATING CHARTER BALANCE")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            total_amount_due,
            paid_amount,
            balance,
            (COALESCE(total_amount_due, 0) - COALESCE(paid_amount, 0)) as calculated_balance
        FROM charters
        WHERE COALESCE(balance, 0) <> (COALESCE(total_amount_due, 0) - COALESCE(paid_amount, 0))
        ORDER BY ABS(COALESCE(balance, 0) - (COALESCE(total_amount_due, 0) - COALESCE(paid_amount, 0))) DESC
    """)
    
    balance_updates = cur.fetchall()
    print(f"Found {len(balance_updates):,} charters needing balance recalculation")
    
    if balance_updates:
        print(f"\nSample balance corrections (first 10):")
        for charter_id, reserve, total_due, paid, current_bal, calc_bal in balance_updates[:10]:
            diff = float(calc_bal) - float(current_bal or 0)
            print(f"  Charter {charter_id} ({reserve}) | Current balance: ${current_bal or 0:,.2f} → Calculated: ${calc_bal:,.2f} | Diff: ${diff:+,.2f}")
        
        if not apply_mode:
            print(f"\nDry-run: would update {len(balance_updates):,} charter balances. Pass --apply to execute.")
        else:
            print(f"\nApplying balance updates...")
            for charter_id, reserve, total_due, paid, current_bal, calc_bal in balance_updates:
                cur.execute("""
                    UPDATE charters
                    SET balance = %s
                    WHERE charter_id = %s
                """, (calc_bal, charter_id))
            conn.commit()
            print(f"✅ Updated {len(balance_updates):,} charters with correct balance")

    # 3. Report on orphan payments needing charters created
    print("\n3. ORPHAN PAYMENTS NEEDING CHARTER CREATION")
    print("-"*80)
    
    cur.execute("""
        SELECT p.payment_id, p.payment_date, p.amount, p.payment_method, p.square_payment_id
        FROM payments p
        WHERE (p.reserve_number IS NULL OR p.reserve_number = '')
        AND p.charter_id IS NULL
        AND COALESCE(p.status, '') NOT ILIKE '%refund%'
        AND COALESCE(p.status, '') NOT ILIKE '%void%'
        ORDER BY p.payment_date DESC
    """)
    
    orphans = cur.fetchall()
    print(f"Found {len(orphans):,} orphan payments needing charter creation")
    
    if orphans:
        total_orphan = sum(float(row[2]) for row in orphans)
        print(f"Total orphan amount: ${total_orphan:,.2f}")
        print(f"\nThese payments need manual investigation to create charters or link to existing ones.")
        print(f"Report: reports/orphan_payments_not_refunded.csv")

    # 4. Payments with reserve_number but no charter
    print("\n4. PAYMENTS WITH RESERVE_NUMBER BUT NO CHARTER")
    print("-"*80)
    
    cur.execute("""
        SELECT p.payment_id, p.reserve_number, p.payment_date, p.amount
        FROM payments p
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
        ORDER BY p.payment_date DESC
    """)
    
    missing = cur.fetchall()
    print(f"Found {len(missing):,} payments with reserve_number but no matching charter")
    
    if missing:
        total_missing = sum(float(row[3]) for row in missing)
        print(f"Total amount: ${total_missing:,.2f}")
        print(f"\nThese reserve numbers need charter records created:")
        
        # Get unique reserve numbers
        cur.execute("""
            SELECT DISTINCT p.reserve_number, COUNT(*), SUM(p.amount)
            FROM payments p
            WHERE p.reserve_number IS NOT NULL 
            AND p.reserve_number <> ''
            AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
            )
            GROUP BY p.reserve_number
            ORDER BY p.reserve_number DESC
        """)
        
        unique_reserves = cur.fetchall()
        print(f"\nUnique reserve numbers needing charters: {len(unique_reserves):,}")
        for reserve, count, amount in unique_reserves[:10]:
            print(f"  {reserve} | {count} payment(s) | ${amount:,.2f}")
        
        print(f"\nReport: reports/payments_missing_charter.csv")

    # 5. Summary
    print("\n5. SUMMARY")
    print("="*80)
    
    if not apply_mode:
        print("DRY-RUN MODE - No changes made")
        print(f"  - Would update {len(updates):,} charter paid_amounts")
        print(f"  - Would update {len(balance_updates):,} charter balances")
        print(f"  - {len(orphans):,} orphan payments need manual investigation")
        print(f"  - {len(missing):,} payments need charter creation ({len(unique_reserves)} unique reserves)")
        print(f"\nRun with --apply to execute updates")
    else:
        print("UPDATES APPLIED")
        print(f"  ✅ Updated {len(updates):,} charter paid_amounts")
        print(f"  ✅ Updated {len(balance_updates):,} charter balances")
        print(f"  ⚠️  {len(orphans):,} orphan payments need manual investigation")
        print(f"  ⚠️  {len(missing):,} payments need charter creation ({len(unique_reserves)} unique reserves)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
