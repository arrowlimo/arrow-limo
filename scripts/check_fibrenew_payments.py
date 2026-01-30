#!/usr/bin/env python3
"""
Re-analyze: If database uses $682.50 but statement shows $1,102.50-$1,260.00,
then database UNDERESTIMATED the charges.

But statement shows LOWER balance ($14,734.56) than database ($37,992.26).

This means either:
1. Database has wrong OPENING balance (too high)
2. Database is MISSING payments
3. Statement includes credits/write-offs not in database

Let me check payments since Oct 2024.
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Get opening balance
        cur.execute("""
            SELECT running_balance
            FROM rent_debt_ledger
            WHERE transaction_type = 'OPENING'
        """)
        opening = cur.fetchone()
        if opening:
            print(f"Database opening balance: ${opening[0]:,.2f}")
        
        # Check charges vs payments since Oct 2024
        cur.execute("""
            SELECT 
                SUM(CASE WHEN transaction_type = 'CHARGE' THEN charge_amount ELSE 0 END) as total_charges,
                SUM(CASE WHEN transaction_type = 'PAYMENT' THEN payment_amount ELSE 0 END) as total_payments
            FROM rent_debt_ledger
            WHERE transaction_date >= '2024-10-01'
        """)
        
        charges, payments = cur.fetchone()
        print(f"\nSince Oct 2024:")
        print(f"  Charges: ${charges:,.2f}")
        print(f"  Payments: ${payments:,.2f}")
        
        # List all payments since Oct 2024
        cur.execute("""
            SELECT transaction_date, payment_amount, running_balance
            FROM rent_debt_ledger
            WHERE transaction_type = 'PAYMENT'
            AND transaction_date >= '2024-10-01'
            ORDER BY transaction_date
        """)
        
        print(f"\nPayments since Oct 2024:")
        print(f"{'Date':<12} {'Payment':>12} {'Balance After':>15}")
        print("-" * 45)
        for dt, amt, bal in cur.fetchall():
            print(f"{dt!s:<12} ${amt:>10,.2f} ${bal:>12,.2f}")
        
        # From screenshot, I can see these payments:
        screenshot_payments = [
            ('2024-10-19', Decimal('1000.00')),
            ('2024-11-04', Decimal('1102.50')),
            ('2024-12-05', Decimal('1500.00')),
            ('2025-01-07', Decimal('1200.00')),
            ('2025-02-04', Decimal('1102.50')),
            ('2025-03-10', Decimal('1102.50')),
            ('2025-04-08', Decimal('1102.50')),
            ('2025-05-14', Decimal('1102.50')),
            ('2025-06-10', Decimal('1102.50')),
            ('2025-07-04', Decimal('800.00')),
            ('2025-07-04', Decimal('400.00')),  # Same day, two payments
            ('2025-07-31', Decimal('2500.00')),
            ('2025-08-15', Decimal('300.00')),
            ('2025-09-16', Decimal('500.00')),
            ('2025-10-02', Decimal('2000.00')),
            ('2025-11-10', Decimal('900.00')),
            ('2025-11-17', Decimal('200.00')),
        ]
        
        screenshot_total = sum(amt for dt, amt in screenshot_payments)
        
        print(f"\n" + "="*60)
        print("COMPARISON:")
        print(f"  Statement shows payments: ${screenshot_total:,.2f}")
        print(f"  Database has payments: ${payments:,.2f}")
        print(f"  Missing: ${screenshot_total - payments:,.2f}")
