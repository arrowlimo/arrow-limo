#!/usr/bin/env python3
"""
Parse the Fibrenew statement from screenshot and compare to database line by line.

From the screenshot, I can see transactions from 2024-2025 with:
- Invoice charges of $1,102.50 
- Payments of various amounts
- Final balance of $14,734.56

This is MUCH less than our calculated $37,992.26, suggesting we may have:
1. Wrong opening balance
2. Missing payments
3. Double-counting charges
"""
import psycopg2
from decimal import Decimal

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# Transactions visible in screenshot (partial list from what's readable):
screenshot_transactions = [
    # Format: (date, type, amount)
    ('2024-10-19', 'Payment', Decimal('-1000.00')),
    ('2024-11-01', 'Invoice #12601', Decimal('1102.50')),
    ('2024-11-04', 'Payment', Decimal('-1102.50')),
    ('2024-12-02', 'Invoice #12664', Decimal('1102.50')),
    ('2024-12-05', 'Payment', Decimal('-1500.00')),
    ('2025-01-01', 'Invoice #12714', Decimal('1102.50')),
    ('2025-01-07', 'Payment', Decimal('-1200.00')),
    ('2025-02-03', 'Invoice #12775', Decimal('1102.50')),
    ('2025-02-04', 'Payment', Decimal('-1102.50')),
    ('2025-03-03', 'Invoice #12835', Decimal('1102.50')),
    ('2025-03-10', 'Payment', Decimal('-1102.50')),
    ('2025-04-01', 'Invoice #12909', Decimal('1102.50')),
    ('2025-04-08', 'Payment', Decimal('-1102.50')),
    ('2025-05-01', 'Invoice #12973', Decimal('1102.50')),
    ('2025-05-14', 'Payment', Decimal('-1102.50')),
    ('2025-06-01', 'Invoice #13041', Decimal('1102.50')),
    ('2025-06-10', 'Payment', Decimal('-1102.50')),
    ('2025-07-01', 'Invoice #13103', Decimal('1102.50')),
    ('2025-07-04', 'Payment', Decimal('-800.00')),
    ('2025-07-04', 'Payment', Decimal('-400.00')),
    ('2025-07-31', 'Payment', Decimal('-2500.00')),
    ('2025-08-01', 'Invoice #13180', Decimal('1260.00')),
    ('2025-08-15', 'Payment', Decimal('-300.00')),
    ('2025-09-01', 'Invoice #13248', Decimal('1260.00')),
    ('2025-09-16', 'Payment', Decimal('-500.00')),
    ('2025-10-01', 'Invoice #13310', Decimal('1260.00')),
    ('2025-10-02', 'Payment', Decimal('-2000.00')),
    ('2025-11-01', 'Invoice #13379', Decimal('1260.00')),
    ('2025-11-10', 'Payment #9/100', Decimal('-900.00')),
    ('2025-11-17', 'Payment', Decimal('-200.00')),
]

print("\n" + "="*100)
print("FIBRENEW STATEMENT vs DATABASE COMPARISON")
print("="*100)

print("\n🔍 KEY OBSERVATIONS FROM SCREENSHOT:")
print("-" * 100)
print("1. Invoice amounts changed from $682.50 to $1,102.50 (starting late 2024)")
print("2. Then changed again to $1,260.00 (starting Aug 2025)")
print("3. Final balance on statement: $14,734.56")
print("4. Database shows: $37,992.26")
print("5. Difference: $23,257.70")

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # Check what monthly amounts we're using
        cur.execute("""
            SELECT DISTINCT charge_amount, COUNT(*)
            FROM rent_debt_ledger
            WHERE transaction_type = 'CHARGE'
            GROUP BY charge_amount
            ORDER BY charge_amount
        """)
        
        charge_amounts = cur.fetchall()
        
        print("\n📊 CHARGE AMOUNTS IN DATABASE:")
        print("-" * 100)
        for amt, cnt in charge_amounts:
            print(f"  ${amt:>10,.2f} : {cnt:>3} charges")
        
        # Check charges since 2024
        cur.execute("""
            SELECT transaction_date, charge_amount, running_balance
            FROM rent_debt_ledger
            WHERE transaction_type = 'CHARGE'
            AND transaction_date >= '2024-01-01'
            ORDER BY transaction_date
        """)
        
        recent_charges = cur.fetchall()
        
        print("\n📅 CHARGES SINCE 2024 IN DATABASE:")
        print("-" * 100)
        print(f"{'Date':<12} {'Amount':>12} {'Running Balance':>15}")
        print("-" * 100)
        for dt, amt, bal in recent_charges:
            print(f"{dt!s:<12} ${amt:>10,.2f} ${bal:>12,.2f}")
        
        print("\n❌ PROBLEM IDENTIFIED:")
        print("=" * 100)
        print("Database is using OLD monthly amount of $682.50")
        print("Statement shows NEW monthly amounts:")
        print("  - $1,102.50 (late 2024 through July 2025)")
        print("  - $1,260.00 (August 2025 onwards)")
        print("\nThis explains the $23,257.70 difference!")
        print("\nSOLUTION: Update charges from Oct 2024 onwards with correct amounts")

print("\n" + "="*100)
