#!/usr/bin/env python3
"""
Find and analyze payment mismatching issues:
1. Payments linked to cancelled charters
2. Payments dated before charter date
3. Payments linked to wrong charter_id
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import timedelta

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def find_payments_on_cancelled_charters():
    """Find payments incorrectly linked to cancelled charters"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("1. PAYMENTS ON CANCELLED CHARTERS")
    print("=" * 80)
    
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.cancelled,
               COUNT(p.payment_id) as payment_count,
               SUM(p.amount) as total_payments,
               MIN(p.payment_date) as first_payment,
               MAX(p.payment_date) as last_payment,
               ARRAY_AGG(p.payment_id ORDER BY p.payment_date) as payment_ids,
               ARRAY_AGG(p.amount ORDER BY p.payment_date) as amounts,
               ARRAY_AGG(p.payment_date ORDER BY p.payment_date) as dates
        FROM charters c
        JOIN payments p ON p.charter_id = c.charter_id
        WHERE c.cancelled = true
        GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.cancelled
        ORDER BY SUM(p.amount) DESC
    """)
    
    cancelled_with_payments = cur.fetchall()
    
    print(f"\n📊 Found {len(cancelled_with_payments)} cancelled charters with payments")
    
    if cancelled_with_payments:
        total_mismatched = sum(row['total_payments'] for row in cancelled_with_payments)
        print(f"   Total mismatched payments: ${total_mismatched:,.2f}")
        
        print(f"\n📋 TOP 10 CANCELLED CHARTERS WITH PAYMENTS:")
        for row in cancelled_with_payments[:10]:
            print(f"\n   Charter {row['reserve_number']} ({row['charter_date']}):")
            print(f"      {row['payment_count']} payments totaling ${row['total_payments']:.2f}")
            print(f"      Payment dates: {row['first_payment']} to {row['last_payment']}")
            for pid, amt, date in zip(row['payment_ids'], row['amounts'], row['dates']):
                print(f"         Payment {pid}: ${amt:.2f} on {date}")
    
    cur.close()
    conn.close()
    
    return cancelled_with_payments

def find_payments_before_charter_date():
    """Find payments dated significantly before charter date"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("2. PAYMENTS DATED BEFORE CHARTER DATE")
    print("=" * 80)
    
    # Payments more than 30 days before charter
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.cancelled,
               p.payment_id, p.payment_date, p.amount,
               (c.charter_date - p.payment_date) as days_early,
               c.total_amount_due, c.balance
        FROM charters c
        JOIN payments p ON p.charter_id = c.charter_id
        WHERE c.charter_date IS NOT NULL
        AND p.payment_date IS NOT NULL
        AND p.payment_date < c.charter_date - INTERVAL '30 days'
        ORDER BY (c.charter_date - p.payment_date) DESC
        LIMIT 50
    """)
    
    early_payments = cur.fetchall()
    
    print(f"\n📊 Found {len(early_payments)} payments dated 30+ days before charter")
    
    if early_payments:
        print(f"\n📋 TOP 20 SUSPICIOUSLY EARLY PAYMENTS:")
        for row in early_payments[:20]:
            status = "CANCELLED" if row['cancelled'] else "Active"
            days_early = row['days_early']
            total_due = row['total_amount_due'] or 0
            balance = row['balance'] or 0
            print(f"\n   Charter {row['reserve_number']} ({row['charter_date']}) - {status}:")
            print(f"      Payment {row['payment_id']}: ${row['amount']:.2f} on {row['payment_date']}")
            print(f"      {days_early} days before charter date")
            print(f"      Charter: ${total_due:.2f} due, ${balance:.2f} balance")
    
    cur.close()
    conn.close()
    
    return early_payments

def find_payments_with_wrong_reserve_number():
    """Find payments where reserve_number doesn't match charter"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("3. PAYMENTS WITH MISMATCHED RESERVE NUMBERS")
    print("=" * 80)
    
    cur.execute("""
        SELECT p.payment_id, p.reserve_number as payment_reserve,
               p.charter_id, c.reserve_number as charter_reserve,
               p.amount, p.payment_date,
               c.charter_date, c.cancelled
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        WHERE p.reserve_number IS NOT NULL
        AND c.reserve_number IS NOT NULL
        AND p.reserve_number != c.reserve_number
        ORDER BY p.payment_date DESC
        LIMIT 50
    """)
    
    mismatched = cur.fetchall()
    
    print(f"\n📊 Found {len(mismatched)} payments with mismatched reserve numbers")
    
    if mismatched:
        print(f"\n📋 SAMPLE MISMATCHED PAYMENTS:")
        for row in mismatched[:15]:
            status = "CANCELLED" if row['cancelled'] else "Active"
            print(f"\n   Payment {row['payment_id']}: ${row['amount']:.2f} on {row['payment_date']}")
            print(f"      Payment says: {row['payment_reserve']}")
            print(f"      Charter says: {row['charter_reserve']} ({status})")
    
    cur.close()
    conn.close()
    
    return mismatched

def analyze_orphaned_payment_patterns():
    """Analyze patterns in payments that may be mislinked"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("4. PAYMENT LINKING PATTERNS")
    print("=" * 80)
    
    # Payments linked to cancelled vs active
    cur.execute("""
        SELECT 
            c.cancelled,
            COUNT(p.payment_id) as payment_count,
            SUM(p.amount) as total_amount,
            COUNT(DISTINCT c.charter_id) as charter_count
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        GROUP BY c.cancelled
    """)
    
    patterns = cur.fetchall()
    
    print(f"\n📊 PAYMENT DISTRIBUTION:")
    for row in patterns:
        status = "Cancelled" if row['cancelled'] else "Active"
        print(f"   {status} charters: {row['payment_count']:,} payments (${row['total_amount']:,.2f}) across {row['charter_count']:,} charters")
    
    # Payments with no charter link
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE charter_id IS NULL
    """)
    
    orphaned = cur.fetchone()
    
    if orphaned['count'] > 0:
        print(f"\n[WARN] ORPHANED PAYMENTS (no charter link):")
        print(f"   Count: {orphaned['count']:,}")
        print(f"   Total: ${orphaned['total']:,.2f}")
    
    # Check if payments have reserve_number but wrong charter_id
    cur.execute("""
        SELECT COUNT(*) as potentially_fixable
        FROM payments p
        WHERE p.charter_id IN (
            SELECT charter_id FROM charters WHERE cancelled = true
        )
        AND p.reserve_number IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM charters c2 
            WHERE c2.reserve_number = p.reserve_number 
            AND c2.cancelled = false
        )
    """)
    
    fixable = cur.fetchone()
    
    if fixable['potentially_fixable'] > 0:
        print(f"\n[OK] POTENTIALLY FIXABLE:")
        print(f"   {fixable['potentially_fixable']:,} payments linked to cancelled charters")
        print(f"   but have reserve_number matching an active charter")
    
    cur.close()
    conn.close()

def generate_fix_recommendations():
    """Generate recommendations for fixing payment mismatches"""
    
    print("\n" + "=" * 80)
    print("RECOMMENDED FIXES")
    print("=" * 80)
    
    print("""
ISSUE 1: Payments on Cancelled Charters
  Fix: Unlink payments from cancelled charters (set charter_id = NULL)
       Keep reserve_number for potential re-matching to correct charter
       
ISSUE 2: Early Payments (30+ days before charter)
  Fix: Review if payment belongs to different charter with same reserve number
       Check if charter date is wrong, or payment date is wrong
       
ISSUE 3: Mismatched Reserve Numbers
  Fix: Update payment.charter_id to match charter with correct reserve_number
       Or update payment.reserve_number to match charter
       
ISSUE 4: Orphaned Payments
  Fix: Match by reserve_number to active charters
       Match by amount+date to charters with similar timing

APPROACH:
  1. Unlink ALL payments from cancelled charters
  2. Re-match payments by reserve_number to active charters only
  3. For remaining orphaned payments, attempt fuzzy matching by amount/date
    """)

def main():
    print("=" * 80)
    print("COMPREHENSIVE PAYMENT MISMATCH ANALYSIS")
    print("=" * 80)
    print("\nIdentifying all payment linking errors across the system")
    print("=" * 80)
    
    cancelled_payments = find_payments_on_cancelled_charters()
    early_payments = find_payments_before_charter_date()
    mismatched_reserves = find_payments_with_wrong_reserve_number()
    analyze_orphaned_payment_patterns()
    generate_fix_recommendations()
    
    print("\n" + "=" * 80)
    print("✓ ANALYSIS COMPLETE")
    print("=" * 80)
    
    print(f"\nSUMMARY:")
    print(f"  Payments on cancelled charters: {len(cancelled_payments)}")
    print(f"  Payments dated 30+ days early: {len(early_payments)}")
    print(f"  Payments with wrong reserve#: {len(mismatched_reserves)}")
    
    print(f"\nNext step: Create fix script to unlink and rematch payments")

if __name__ == '__main__':
    main()
