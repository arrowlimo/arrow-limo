#!/usr/bin/env python3
"""
Verify payment duplicates are legitimate by checking charter balance.
If charter balance = $0, all payments are legitimate (multiple payments to cover charges).
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))

print("=" * 80)
print("PAYMENT DUPLICATE VALIDATION - CHARTER BALANCE CHECK")
print("=" * 80)
print()

# Find all "duplicate" payment patterns
with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                reserve_number,
                payment_date,
                amount,
                COUNT(*) as payment_count,
                ARRAY_AGG(payment_id ORDER BY payment_id) as payment_ids
            FROM payments
            WHERE reserve_number IS NOT NULL 
            AND payment_date IS NOT NULL
            AND amount IS NOT NULL
            GROUP BY reserve_number, payment_date, amount
            HAVING COUNT(*) > 1
        )
        SELECT * FROM duplicates
        ORDER BY payment_count DESC, reserve_number
    """)
    
    duplicate_patterns = cur.fetchall()

print(f"Found {len(duplicate_patterns)} duplicate payment patterns")
print()

# Check each pattern against charter balance
print("=" * 80)
print("VALIDATING AGAINST CHARTER BALANCES")
print("=" * 80)
print()

true_duplicates = []
legitimate_multiples = []

for pattern in duplicate_patterns:
    reserve = pattern['reserve_number']
    
    # Get charter details
    with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                charter_id,
                reserve_number,
                COALESCE(total_amount_due, 0) as total_amount_due,
                COALESCE(payment_totals, 0) as payment_totals,
                COALESCE(balance, 0) as balance
            FROM charters
            WHERE reserve_number = %s
        """, (reserve,))
        
        charter = cur.fetchone()
        
        if not charter:
            print(f"⚠️  {reserve}: No charter found")
            continue
        
        # Use columns from Neon charter table
        total_due = charter['total_amount_due']
        paid = charter['payment_totals']
        balance = charter['balance']
        
        # Get all payments for this charter
        cur.execute("""
            SELECT 
                payment_id,
                payment_date,
                amount,
                payment_method
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date, payment_id
        """, (reserve,))
        
        all_payments = cur.fetchall()
        total_payments = sum(p['amount'] for p in all_payments)
        
        # Check if "duplicates" are legitimate
        is_balanced = abs(balance) < 0.01  # $0.00 balance
        
        print(f"\n{reserve}:")
        print(f"  Charter total_due: ${total_due:>10,.2f}")
        print(f"  Paid amount:       ${paid:>10,.2f}")
        print(f"  Balance:           ${balance:>10,.2f}")
        print(f"  Payment count:     {len(all_payments):>10}")
        print(f"  Payment total:     ${total_payments:>10,.2f}")
        print(f"  Duplicate pattern: {pattern['payment_count']} x ${pattern['amount']:.2f} on {pattern['payment_date']}")
        
        if is_balanced:
            print(f"  ✅ LEGITIMATE - Balance is $0, all payments needed")
            legitimate_multiples.append(pattern)
        else:
            print(f"  ❌ TRUE DUPLICATE - Balance not zero, likely duplicates")
            true_duplicates.append(pattern)

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Legitimate multiple payments: {len(legitimate_multiples):>6}")
print(f"True duplicates to delete:    {len(true_duplicates):>6}")

if true_duplicates:
    print()
    print("=" * 80)
    print("TRUE DUPLICATES (TO DELETE)")
    print("=" * 80)
    
    total_to_delete = 0
    for dup in true_duplicates:
        # Keep first payment, delete rest
        to_delete_count = dup['payment_count'] - 1
        total_to_delete += to_delete_count
        print(f"\n{dup['reserve_number']}: Delete {to_delete_count} of {dup['payment_count']} payments")
        print(f"  Date: {dup['payment_date']}, Amount: ${dup['amount']:.2f}")
        print(f"  Keep: {dup['payment_ids'][0]}")
        print(f"  Delete: {dup['payment_ids'][1:]}")
    
    print()
    print(f"Total payments to delete: {total_to_delete}")

print()
print("=" * 80)
print("✅ Validation complete")
print("=" * 80)

neon_conn.close()
