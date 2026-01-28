#!/usr/bin/env python3
"""
Analyze 56 charters with overages (charge_sum > total_amount_due).
Determine if these are legitimate or data errors.
"""

import os
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*80)
print("CHARTER OVERAGES ANALYSIS")
print("="*80)

# Get all overages
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
    ORDER BY (charge_sum - total_amount_due) DESC
""")

overages = cur.fetchall()

print(f"\nTotal overages: {len(overages)}")
print("-"*80)

# Categorize overages
penny_rounding = []  # <= $1.00
small = []  # $1.01 - $10.00
medium = []  # $10.01 - $100.00
large = []  # > $100.00

for row in overages:
    overage = row[4]
    if overage <= 1.00:
        penny_rounding.append(row)
    elif overage <= 10.00:
        small.append(row)
    elif overage <= 100.00:
        medium.append(row)
    else:
        large.append(row)

print(f"\nOverage categories:")
print(f"  Penny rounding (≤$1.00):  {len(penny_rounding):>3}")
print(f"  Small ($1.01-$10.00):      {len(small):>3}")
print(f"  Medium ($10.01-$100.00):   {len(medium):>3}")
print(f"  Large (>$100.00):          {len(large):>3}")

# Check payment status
paid_in_full = sum(1 for row in overages if row[6] == 0)  # balance = 0
has_balance = len(overages) - paid_in_full

print(f"\nPayment status:")
print(f"  Paid in full (balance=0):  {paid_in_full:>3}")
print(f"  Has balance:               {has_balance:>3}")

# Show large overages in detail
if large:
    print(f"\n" + "="*80)
    print(f"LARGE OVERAGES (>{Decimal('100.00')})")
    print("="*80)
    
    for row in large:
        reserve, date, total, charges, overage, paid, balance, status = row
        print(f"\nReserve: {reserve}")
        print(f"  Date: {date}")
        print(f"  Total due: ${total:,.2f}")
        print(f"  Charges:   ${charges:,.2f}")
        print(f"  Overage:   ${overage:,.2f}")
        print(f"  Paid:      ${paid:,.2f}")
        print(f"  Balance:   ${balance:,.2f}")
        print(f"  Status:    {status or 'N/A'}")
        
        # Get charge breakdown
        cur.execute("""
            SELECT charge_type, amount, created_at
            FROM charter_charges
            WHERE reserve_number = %s
            ORDER BY created_at
        """, (reserve,))
        
        charges_detail = cur.fetchall()
        print(f"  Charges ({len(charges_detail)}):")
        for charge_type, amount, created in charges_detail:
            print(f"    ${amount:>9,.2f} - {charge_type} (created {created.date() if created else 'unknown'})")

# Show medium overages summary
if medium:
    print(f"\n" + "="*80)
    print(f"MEDIUM OVERAGES ($10.01-$100.00) - Summary")
    print("="*80)
    print(f"\n{'Reserve':<12} {'Date':<12} {'Total':<12} {'Charges':<12} {'Overage':<12} {'Balance':<12}")
    print("-"*80)
    
    for row in medium[:20]:  # Show first 20
        reserve, date, total, charges, overage, paid, balance, status = row
        print(f"{reserve:<12} {date} ${total:>9,.2f} ${charges:>9,.2f} ${overage:>9,.2f} ${balance:>9,.2f}")
    
    if len(medium) > 20:
        print(f"\n... and {len(medium) - 20} more")

# Show penny rounding
if penny_rounding:
    print(f"\n" + "="*80)
    print(f"PENNY ROUNDING (≤$1.00)")
    print("="*80)
    print(f"\n{'Reserve':<12} {'Date':<12} {'Total':<12} {'Charges':<12} {'Overage':<12}")
    print("-"*80)
    
    for row in penny_rounding:
        reserve, date, total, charges, overage, paid, balance, status = row
        print(f"{reserve:<12} {date} ${total:>9,.2f} ${charges:>9,.2f} ${overage:>9,.2f}")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if len(large) == 0 and len(medium) == 0 and len(small) <= 5:
    print("\n✅ Most overages are penny rounding (<$1)")
    print("   These are acceptable and likely due to GST calculation differences")
    if paid_in_full == len(overages):
        print("   All charters are paid in full - no financial impact")
elif paid_in_full == len(overages):
    print("\n⚠️  All overages are paid in full")
    print("   No financial impact, but may indicate:")
    print("   - Extra charges added after initial quote")
    print("   - Tips/gratuities added separately")
    print("   - Manual adjustments")
else:
    print(f"\n⚠️  {has_balance} charters with overages still have balances")
    print("   Review to determine if total_amount_due should be increased")

cur.close()
conn.close()
