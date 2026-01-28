#!/usr/bin/env python3
"""
Check if Square banking deposits are matched to charters via payments table.
Square = customer revenue, should link to charters, NOT receipts (which are expenses).
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("SQUARE DEPOSITS - CHARTER MATCHING ANALYSIS")
print("=" * 120)

# Find all Square deposits in banking
cur.execute("""
    SELECT 
        b.transaction_id,
        b.transaction_date,
        b.description,
        b.credit_amount,
        b.balance
    FROM banking_transactions b
    WHERE b.description ILIKE '%square%'
    AND b.credit_amount > 0
    ORDER BY b.transaction_date DESC
""")

square_deposits = cur.fetchall()

print(f"\nTotal Square deposits in banking: {len(square_deposits)}")
total_square_amount = sum(tx[3] for tx in square_deposits)
print(f"Total Square revenue: ${total_square_amount:,.2f}\n")

# Check how many are matched to payments
cur.execute("""
    SELECT 
        COUNT(*) as square_with_payments,
        SUM(b.credit_amount) as matched_amount
    FROM banking_transactions b
    INNER JOIN payments p ON p.banking_transaction_id = b.transaction_id
    WHERE b.description ILIKE '%square%'
    AND b.credit_amount > 0
""")

matched_count, matched_amount = cur.fetchone()

matched_amount = matched_amount or 0

print("=" * 120)
print("MATCHING STATUS")
print("=" * 120)
print(f"\nSquare deposits WITH payment records: {matched_count:,} (${matched_amount:,.2f})")
print(f"Square deposits WITHOUT payment records: {len(square_deposits) - matched_count:,} (${total_square_amount - matched_amount:,.2f})")

if matched_count:
    pct = (matched_count / len(square_deposits) * 100)
    print(f"\nMatch rate: {pct:.1f}%")

# Show payment linkage details
print("\n" + "=" * 120)
print("SQUARE -> PAYMENT -> CHARTER LINKAGE")
print("=" * 120)

cur.execute("""
    SELECT 
        p.payment_method,
        COUNT(*) as payment_count,
        SUM(p.amount) as total_amount,
        COUNT(DISTINCT p.reserve_number) as unique_charters
    FROM banking_transactions b
    INNER JOIN payments p ON p.banking_transaction_id = b.transaction_id
    WHERE b.description ILIKE '%square%'
    AND b.credit_amount > 0
    GROUP BY p.payment_method
    ORDER BY total_amount DESC
""")

payment_methods = cur.fetchall()

if payment_methods:
    print(f"\n{'Payment Method':<30} {'Count':<10} {'Total Amount':<18} {'Charters':<12}")
    print("-" * 120)
    for method, count, amount, charters in payment_methods:
        print(f"{method or 'NULL':<30} {count:<10} ${amount:>15,.2f}  {charters:<12}")
else:
    print("\n⚠️  NO payment records found for Square deposits")

# Check for charters with Square payments
print("\n" + "=" * 120)
print("CHARTER PAYMENT ANALYSIS (Square)")
print("=" * 120)

cur.execute("""
    SELECT 
        COUNT(DISTINCT c.charter_id) as charters_with_square,
        COUNT(DISTINCT p.payment_id) as square_payments,
        SUM(p.amount) as total_revenue
    FROM payments p
    INNER JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.payment_method ILIKE '%square%'
""")

charters_count, payments_count, revenue = cur.fetchone()

if charters_count:
    print(f"\nCharters with Square payments: {charters_count:,}")
    print(f"Total Square payment records: {payments_count:,}")
    print(f"Total revenue recorded: ${revenue:,.2f}")
else:
    print("\n⚠️  NO charters found with Square payment method")

# Sample Square deposits WITH payments
print("\n" + "=" * 120)
print("SAMPLE MATCHED SQUARE DEPOSITS (First 10)")
print("=" * 120)

cur.execute("""
    SELECT 
        b.transaction_date,
        b.credit_amount as bank_amount,
        p.payment_id,
        p.amount as payment_amount,
        p.reserve_number,
        p.payment_method,
        c.pickup_time,
        c.client_name
    FROM banking_transactions b
    INNER JOIN payments p ON p.banking_transaction_id = b.transaction_id
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE b.description ILIKE '%square%'
    AND b.credit_amount > 0
    ORDER BY b.transaction_date DESC
    LIMIT 10
""")

matched_samples = cur.fetchall()

if matched_samples:
    for bank_date, bank_amt, pay_id, pay_amt, reserve, method, pickup, client in matched_samples:
        print(f"\n{bank_date} | Bank: ${bank_amt:,.2f} | Payment: ${pay_amt:,.2f}")
        print(f"  Payment #{pay_id} | Reserve: {reserve} | Method: {method}")
        if client:
            print(f"  Charter: {client} ({pickup})")
else:
    print("\nNo matched samples found")

# Sample Square deposits WITHOUT payments
print("\n" + "=" * 120)
print("SAMPLE UNMATCHED SQUARE DEPOSITS (First 10)")
print("=" * 120)

cur.execute("""
    SELECT 
        b.transaction_id,
        b.transaction_date,
        b.credit_amount,
        b.description
    FROM banking_transactions b
    LEFT JOIN payments p ON p.banking_transaction_id = b.transaction_id
    WHERE b.description ILIKE '%square%'
    AND b.credit_amount > 0
    AND p.payment_id IS NULL
    ORDER BY b.credit_amount DESC
    LIMIT 10
""")

unmatched_samples = cur.fetchall()

if unmatched_samples:
    print(f"\nFound {len(unmatched_samples)} large unmatched Square deposits:\n")
    for tx_id, date, amount, desc in unmatched_samples:
        print(f"{date} | ${amount:>10,.2f} | TX #{tx_id}")
        print(f"  {desc[:100]}")
        print()
else:
    print("\n✅ All Square deposits are matched to payments!")

# Final summary
print("=" * 120)
print("SUMMARY")
print("=" * 120)

if matched_count == len(square_deposits):
    print(f"\n✅ PERFECT: All {len(square_deposits):,} Square deposits matched to payments")
    print(f"   Total Square revenue recorded: ${total_square_amount:,.2f}")
elif matched_count > 0:
    print(f"\n⚠️  PARTIAL MATCHING:")
    print(f"   Matched: {matched_count:,} Square deposits (${matched_amount:,.2f})")
    print(f"   Unmatched: {len(square_deposits) - matched_count:,} deposits (${total_square_amount - matched_amount:,.2f})")
    print(f"   Match rate: {matched_count / len(square_deposits) * 100:.1f}%")
else:
    print(f"\n❌ NO MATCHING:")
    print(f"   {len(square_deposits):,} Square deposits (${total_square_amount:,.2f}) NOT linked to payments")
    print("   Revenue is NOT recorded in charter system!")

cur.close()
conn.close()

print("\n" + "=" * 120)
