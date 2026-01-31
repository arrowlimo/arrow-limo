#!/usr/bin/env python3
"""
Check the 7 overages that still have balances to see if they need correction.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("OVERAGES WITH BALANCES")
print("="*80)

# Get overages with balance > 0
cur.execute("""
    WITH charge_sums AS (
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            COALESCE(SUM(cc.amount), 0) as charge_sum
        FROM charters c
        LEFT JOIN charter_charges cc ON c.reserve_number = cc.reserve_number
        WHERE c.total_amount_due > 0
        GROUP BY c.reserve_number, c.charter_date, c.total_amount_due, 
                 c.paid_amount, c.balance, c.status
    )
    SELECT 
        reserve_number,
        charter_date,
        total_amount_due,
        charge_sum,
        (charge_sum - total_amount_due) as overage,
        paid_amount,
        balance,
        status
    FROM charge_sums
    WHERE charge_sum > total_amount_due
    AND balance != 0
    ORDER BY balance DESC
""")

overages_with_balance = cur.fetchall()

print(f"\nFound {len(overages_with_balance)} charters with overages AND balances")
print("="*80)

for row in overages_with_balance:
    reserve, date, total, charges, overage, paid, balance, status = row
    
    print(f"\nReserve: {reserve}")
    print(f"  Charter date: {date}")
    print(f"  Status: {status or 'N/A'}")
    print(f"  Total due:    ${total:>10,.2f}")
    print(f"  Charge sum:   ${charges:>10,.2f}")
    print(f"  Overage:      ${overage:>10,.2f}")
    print(f"  Paid:         ${paid:>10,.2f}")
    print(f"  Balance:      ${balance:>10,.2f}")
    
    # Get charges
    cur.execute("""
        SELECT charge_type, amount, created_at
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY created_at
    """, (reserve,))
    
    charges_list = cur.fetchall()
    print(f"  Charges ({len(charges_list)}):")
    for charge_type, amount, created in charges_list:
        created_date = created.date() if created else 'unknown'
        print(f"    ${amount:>9,.2f} - {charge_type:<30} (created {created_date})")
    
    # Get payments
    cur.execute("""
        SELECT payment_date, amount, payment_method
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve,))
    
    payments = cur.fetchall()
    if payments:
        print(f"  Payments ({len(payments)}):")
        for pmt_date, amount, method in payments:
            print(f"    ${amount:>9,.2f} - {method or 'unknown':<20} on {pmt_date}")
    else:
        print(f"  Payments: None")
    
    # Analysis
    correct_balance_by_charges = charges - paid
    correct_balance_by_total = total - paid
    
    print(f"\n  Analysis:")
    print(f"    If total = charges ({charges:.2f}): balance should be ${correct_balance_by_charges:,.2f}")
    print(f"    If total = current ({total:.2f}): balance should be ${correct_balance_by_total:,.2f}")
    print(f"    Actual balance: ${balance:,.2f}")
    
    if abs(balance - correct_balance_by_charges) < 0.01:
        print(f"    ✅ Balance matches charges - total_amount_due should be updated to ${charges:,.2f}")
    elif abs(balance - correct_balance_by_total) < 0.01:
        print(f"    ✅ Balance matches current total - overage charges may be extra/tips")
    else:
        print(f"    ⚠️  Balance mismatch - needs manual review")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

# Count how many need total_amount_due update
needs_update = 0
for row in overages_with_balance:
    reserve, date, total, charges, overage, paid, balance, status = row
    correct_balance_by_charges = charges - paid
    if abs(balance - correct_balance_by_charges) < 0.01:
        needs_update += 1

print(f"\nCharters where total_amount_due should = charge_sum: {needs_update}")
print(f"This would eliminate the overage by updating the invoice total.")

cur.close()
conn.close()
