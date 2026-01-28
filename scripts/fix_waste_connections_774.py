#!/usr/bin/env python3
"""Fix Waste Connections $774 payment allocations.

Strategy:
  1. Find all Waste Connections charters with $774 due (their standard rate)
  2. Match orphaned $774 payments to proper charters by date proximity
  3. Reallocate payments from credit ledger sources to actual charters
  4. Update charter paid_amount and balance accordingly

This handles the uniform installment pattern where periodic $774 payments
were pooled on single reserves instead of allocated to individual runs.

Usage:
  python scripts/fix_waste_connections_774.py              # Dry-run
  python scripts/fix_waste_connections_774.py --write      # Execute
"""

import os
import psycopg2
from datetime import datetime, timedelta
from argparse import ArgumentParser
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def pg_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def find_waste_connections_client_id(cur):
    """Find Waste Connections client ID."""
    cur.execute("""
        SELECT client_id, client_name 
        FROM clients 
        WHERE LOWER(client_name) LIKE '%waste connection%'
        ORDER BY client_id
        LIMIT 1
    """)
    row = cur.fetchone()
    return row[0] if row else None


def find_credited_waste_774_reserves(cur, client_id):
    """Find reserves that had $774 uniform installments moved to credit."""
    cur.execute("""
        SELECT 
            cl.source_reserve_number,
            cl.source_charter_id,
            cl.credit_id,
            cl.credit_amount,
            cl.remaining_balance,
            ch.charter_date
        FROM charter_credit_ledger cl
        JOIN charters ch ON ch.charter_id = cl.source_charter_id
        WHERE cl.client_id = %s
        AND cl.credit_reason = 'UNIFORM_INSTALLMENT'
        ORDER BY cl.credit_amount DESC
    """, (client_id,))
    return cur.fetchall()


def find_774_payments_for_reserve(cur, reserve_number):
    """Get all $774 payments for a reserve."""
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key
        FROM payments
        WHERE reserve_number = %s
        AND ABS(amount - 774.00) < 0.01
        ORDER BY payment_date
    """, (reserve_number,))
    return cur.fetchall()


def find_unpaid_waste_774_charters(cur, client_id, start_date, end_date):
    """Find unpaid or underpaid Waste Connections charters with $774 due."""
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            total_amount_due,
            paid_amount,
            balance
        FROM charters
        WHERE client_id = %s
        AND ABS(total_amount_due - 774.00) < 0.01
        AND balance > 0
        AND charter_date BETWEEN %s AND %s
        ORDER BY charter_date
    """, (client_id, start_date, end_date))
    return cur.fetchall()


def match_payments_to_charters(payments, charters):
    """Match payments to charters by date proximity."""
    allocations = []
    used_payments = set()
    used_charters = set()
    
    for payment_id, amount, payment_date, payment_key in payments:
        if payment_id in used_payments:
            continue
        
        # Find closest charter within ±90 days
        best_match = None
        best_distance = None
        
        for charter_id, reserve, charter_date, due, paid, balance in charters:
            if charter_id in used_charters:
                continue
            if balance <= 0:
                continue
            
            days_diff = abs((charter_date - payment_date).days)
            if days_diff <= 90:
                if best_distance is None or days_diff < best_distance:
                    best_distance = days_diff
                    best_match = (charter_id, reserve, charter_date, due, paid, balance)
        
        if best_match:
            charter_id, reserve, charter_date, due, paid, balance = best_match
            allocations.append({
                'payment_id': payment_id,
                'payment_date': payment_date,
                'payment_key': payment_key,
                'amount': float(amount),
                'charter_id': charter_id,
                'reserve_number': reserve,
                'charter_date': charter_date,
                'old_paid': float(paid),
                'old_balance': float(balance),
                'new_paid': float(paid) + float(amount),
                'new_balance': float(balance) - float(amount),
                'days_diff': best_distance,
            })
            used_payments.add(payment_id)
            used_charters.add(charter_id)
    
    return allocations


def apply_reallocations(cur, source_credit_id, source_reserve, allocations):
    """Apply payment reallocations to charters and update credit ledger."""
    total_allocated = sum(a['amount'] for a in allocations)
    
    for alloc in allocations:
        # Update payment reserve_number to point to correct charter
        cur.execute("""
            UPDATE payments
            SET reserve_number = %s
            WHERE payment_id = %s
        """, (alloc['reserve_number'], alloc['payment_id']))
        
        # Update charter paid_amount and balance
        cur.execute("""
            UPDATE charters
            SET paid_amount = %s, balance = %s
            WHERE charter_id = %s
        """, (alloc['new_paid'], alloc['new_balance'], alloc['charter_id']))
    
    # Update credit ledger remaining_balance
    cur.execute("""
        UPDATE charter_credit_ledger
        SET remaining_balance = remaining_balance - %s,
            notes = notes || ' | Reallocated ' || %s || ' payments totaling $' || %s::text
        WHERE credit_id = %s
    """, (total_allocated, len(allocations), f"{total_allocated:.2f}", source_credit_id))
    
    return len(allocations), total_allocated


def analyze_and_fix(dry_run=True):
    conn = pg_conn()
    cur = conn.cursor()
    
    try:
        # Find Waste Connections client
        client_id = find_waste_connections_client_id(cur)
        if not client_id:
            print("ERROR: Waste Connections client not found")
            return
        
        cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (client_id,))
        client_name = cur.fetchone()[0]
        print(f"Found client: {client_name} (ID: {client_id})")
        print()
        
        # Find credited reserves with uniform installments
        credited_reserves = find_credited_waste_774_reserves(cur, client_id)
        print(f"Found {len(credited_reserves)} credited reserves with UNIFORM_INSTALLMENT pattern")
        print()
        
        all_reallocations = []
        total_amount_reallocated = 0
        
        for source_reserve, source_charter_id, credit_id, credit_amount, remaining, charter_date in credited_reserves:
            print(f"Processing reserve {source_reserve} (credit ${credit_amount:.2f})...")
            
            # Get $774 payments for this reserve
            payments = find_774_payments_for_reserve(cur, source_reserve)
            print(f"  Found {len(payments)} $774 payments")
            
            if not payments:
                continue
            
            # Find unpaid charters in timeframe
            first_payment_date = min(p[2] for p in payments)
            last_payment_date = max(p[2] for p in payments)
            search_start = first_payment_date - timedelta(days=90)
            search_end = last_payment_date + timedelta(days=90)
            
            unpaid_charters = find_unpaid_waste_774_charters(cur, client_id, search_start, search_end)
            print(f"  Found {len(unpaid_charters)} unpaid $774 charters in date range")
            
            if not unpaid_charters:
                continue
            
            # Match payments to charters
            allocations = match_payments_to_charters(payments, unpaid_charters)
            print(f"  Matched {len(allocations)} payments to charters")
            
            if allocations:
                for alloc in allocations:
                    print(f"    Payment {alloc['payment_date']} → Charter {alloc['reserve_number']} "
                          f"({alloc['charter_date']}, {alloc['days_diff']} days)")
                
                all_reallocations.extend(allocations)
                
                if not dry_run:
                    count, amount = apply_reallocations(cur, credit_id, source_reserve, allocations)
                    total_amount_reallocated += amount
                    print(f"  ✓ Applied {count} reallocations (${amount:.2f})")
            
            print()
        
        if all_reallocations:
            print("=" * 70)
            print(f"Summary: {len(all_reallocations)} payments reallocated")
            print(f"Total amount: ${sum(a['amount'] for a in all_reallocations):,.2f}")
            
            if dry_run:
                print("\n=== DRY-RUN MODE ===")
                print("Run with --write to apply changes")
            else:
                conn.commit()
                print("\n✓ Changes committed to database")
        else:
            print("No reallocations needed")
    
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = ArgumentParser(description='Fix Waste Connections $774 payment allocations')
    parser.add_argument('--write', action='store_true', help='Execute changes (default is dry-run)')
    args = parser.parse_args()
    
    analyze_and_fix(dry_run=not args.write)


if __name__ == '__main__':
    main()
