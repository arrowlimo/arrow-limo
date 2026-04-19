#!/usr/bin/env python3
"""
Query 2012 charters with payments made and calculate total revenue.
"""

import psycopg2
from datetime import datetime

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # First, check the schema of charters table
    schema_query = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'charters'
    ORDER BY ordinal_position;
    """
    cur.execute(schema_query)
    cols = cur.fetchall()
    print("Charters table schema:")
    for col_name, data_type in cols:
        print(f"  {col_name}: {data_type}")
    print()
    
    # Get all 2012 charters with payments
    query = """
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        COALESCE(c.grand_total, c.total_amount_due, 0) as charter_revenue,
        COUNT(DISTINCT cp.id) as payment_count,
        COALESCE(SUM(cp.amount), 0) as total_paid
    FROM charters c
    LEFT JOIN charter_payments cp ON c.charter_id::text = cp.charter_id::text
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.grand_total, c.total_amount_due
    ORDER BY c.charter_date;
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    print(f"\n{'Charter ID':<12} {'Reserve':<12} {'Date':<12} {'Revenue':<12} {'Payments':<10} {'Total Paid':<12}")
    print("-" * 80)
    
    total_revenue = 0
    total_paid = 0
    charter_count = 0
    paid_charter_count = 0
    
    for charter_id, reserve, charter_date, charter_revenue, payment_count, total_paid_amt in rows:
        if charter_revenue is None:
            charter_revenue = 0
        if total_paid_amt is None:
            total_paid_amt = 0
            
        # Only count charters that have payments (payment_count > 0)
        if payment_count > 0:
            paid_charter_count += 1
            total_revenue += charter_revenue
            total_paid += total_paid_amt
        
        charter_count += 1
        print(f"{charter_id:<12} {str(reserve):<12} {str(charter_date):<12} ${charter_revenue:>10.2f} {payment_count:>9} ${total_paid_amt:>10.2f}")
    
    print("-" * 80)
    print(f"\nTotal 2012 charters: {charter_count}")
    print(f"Charters with payments: {paid_charter_count}")
    print(f"\n** TOTAL REVENUE (charters with payments made): ${total_revenue:,.2f} **")
    print(f"** TOTAL AMOUNT PAID: ${total_paid:,.2f} **")
    
    # Also get summary by query without filtering by payment status for comparison
    summary_query = """
    SELECT 
        COUNT(*) as total_charters,
        SUM(CASE WHEN COALESCE(grand_total, total_amount_due, 0) > 0 THEN 1 ELSE 0 END) as charters_with_revenue,
        COALESCE(SUM(COALESCE(grand_total, total_amount_due, 0)), 0) as total_revenue_booked
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012;
    """
    
    cur.execute(summary_query)
    total, with_revenue, total_booked = cur.fetchone()
    
    print(f"\n--- All 2012 charters (regardless of payment status) ---")
    print(f"Total charters in 2012: {total}")
    print(f"Charters with revenue: {with_revenue}")
    print(f"Total revenue booked: ${total_booked:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
