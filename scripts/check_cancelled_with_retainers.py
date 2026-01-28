#!/usr/bin/env python3
"""
Check for cancelled charters that have retainers recorded.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def check_cancelled_with_retainers():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("CANCELLED CHARTERS WITH RETAINERS")
    print("=" * 80)
    
    # Check count and total
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(COALESCE(retainer_amount, 0)) as total_retainer_amount,
            SUM(COALESCE(retainer, 0)) as total_retainer_old
        FROM charters
        WHERE cancelled = true
        AND (retainer_received = true 
             OR retainer_amount > 0 
             OR retainer > 0)
    """)
    
    summary = cur.fetchone()
    
    print(f"\n📊 SUMMARY:")
    print(f"   Cancelled charters with retainers: {summary['count']}")
    print(f"   Total retainer_amount: ${summary['total_retainer_amount']:,.2f}")
    print(f"   Total retainer (old field): ${summary['total_retainer_old']:,.2f}")
    
    if summary['count'] > 0:
        # Get details
        cur.execute("""
            SELECT 
                charter_id,
                reserve_number,
                charter_date,
                retainer_received,
                retainer_amount,
                retainer,
                total_amount_due,
                paid_amount,
                balance,
                client_notes,
                booking_notes
            FROM charters
            WHERE cancelled = true
            AND (retainer_received = true 
                 OR retainer_amount > 0 
                 OR retainer > 0)
            ORDER BY charter_date DESC
        """)
        
        charters = cur.fetchall()
        
        print(f"\n📋 DETAILS ({len(charters)} charters):")
        print("-" * 80)
        
        for charter in charters:
            print(f"\n   Charter: {charter['reserve_number']}")
            print(f"   Date: {charter['charter_date']}")
            print(f"   Retainer received: {charter['retainer_received']}")
            print(f"   Retainer amount: ${charter['retainer_amount'] or 0:.2f}")
            print(f"   Retainer (old): ${charter['retainer'] or 0:.2f}")
            print(f"   Total due: ${charter['total_amount_due'] or 0:.2f}")
            print(f"   Paid: ${charter['paid_amount'] or 0:.2f}")
            print(f"   Balance: ${charter['balance'] or 0:.2f}")
            
            if charter['client_notes']:
                print(f"   Client notes: {charter['client_notes'][:100]}")
            if charter['booking_notes']:
                print(f"   Booking notes: {charter['booking_notes'][:100]}")
    
    # Check if any have payments
    cur.execute("""
        SELECT COUNT(DISTINCT p.charter_id) as charters_with_payments,
               SUM(p.amount) as total_payment_amount
        FROM payments p
        JOIN charters c ON c.charter_id = p.charter_id
        WHERE c.cancelled = true
        AND (c.retainer_received = true 
             OR c.retainer_amount > 0 
             OR c.retainer > 0)
    """)
    
    payment_summary = cur.fetchone()
    
    if payment_summary['charters_with_payments']:
        print(f"\n[WARN] PAYMENTS ON CANCELLED CHARTERS WITH RETAINERS:")
        print(f"   Charters with payments: {payment_summary['charters_with_payments']}")
        print(f"   Total payment amount: ${payment_summary['total_payment_amount']:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_cancelled_with_retainers()
    
    print("\n" + "=" * 80)
    print("✓ Check complete")
    print("=" * 80)
