#!/usr/bin/env python3
"""
Investigate why charter-payment-banking matching keeps getting lost.
Check payments table schema and current matching status.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("PAYMENTS TABLE - SCHEMA AND MATCHING STATUS")
print("=" * 120)

# Get payments table schema
cur.execute("""
    SELECT column_name, data_type, character_maximum_length, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'payments'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()

print("\nPAYMENTS TABLE COLUMNS:")
print("-" * 120)
for col_name, data_type, max_length, nullable in columns:
    type_info = data_type
    if max_length:
        type_info += f"({max_length})"
    null_info = "NULL" if nullable == "YES" else "NOT NULL"
    print(f"  {col_name:40} {type_info:20} {null_info}")

# Check total payments
cur.execute("SELECT COUNT(*), SUM(amount) FROM payments")
total_payments, total_amount = cur.fetchone()

print("\n" + "=" * 120)
print("PAYMENTS TABLE SUMMARY")
print("=" * 120)
print(f"\nTotal payment records: {total_payments:,}")
print(f"Total payment amount: ${total_amount:,.2f}")

# Check banking linkage
cur.execute("""
    SELECT 
        COUNT(*) as payments_with_banking,
        SUM(amount) as amount_with_banking
    FROM payments
    WHERE banking_transaction_id IS NOT NULL
""")

payments_with_bank, amount_with_bank = cur.fetchone()

print(f"\nPayments WITH banking_transaction_id: {payments_with_bank:,} (${amount_with_bank:,.2f})")
print(f"Payments WITHOUT banking_transaction_id: {total_payments - payments_with_bank:,} (${total_amount - amount_with_bank:,.2f})")

if payments_with_bank:
    match_pct = (payments_with_bank / total_payments * 100)
    print(f"\nCurrent match rate: {match_pct:.1f}%")

# Check charter linkage (via reserve_number)
cur.execute("""
    SELECT 
        COUNT(*) as payments_with_charter,
        COUNT(DISTINCT p.reserve_number) as unique_charters
    FROM payments p
    INNER JOIN charters c ON c.reserve_number = p.reserve_number
""")

payments_with_charter, unique_charters = cur.fetchone()

print(f"\nPayments linked to charters: {payments_with_charter:,}")
print(f"Unique charters with payments: {unique_charters:,}")

# Check payment methods
print("\n" + "=" * 120)
print("PAYMENT METHODS BREAKDOWN")
print("=" * 120)

cur.execute("""
    SELECT 
        payment_method,
        COUNT(*) as count,
        SUM(amount) as total_amount,
        COUNT(banking_transaction_id) as with_banking
    FROM payments
    GROUP BY payment_method
    ORDER BY total_amount DESC
""")

payment_methods = cur.fetchall()

print(f"\n{'Payment Method':<30} {'Count':<12} {'Total Amount':<18} {'With Banking':<15}")
print("-" * 120)
for method, count, amount, with_bank in payment_methods:
    method_display = method or 'NULL/EMPTY'
    print(f"{method_display:<30} {count:<12} ${amount:>15,.2f}  {with_bank:<15}")

# Check for Square, e-transfer, cash, cheque specifically
print("\n" + "=" * 120)
print("KEY PAYMENT TYPES - BANKING MATCH STATUS")
print("=" * 120)

for payment_type in ['SQUARE', 'E-TRANSFER', 'CASH', 'CHEQUE', 'CHECK']:
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(amount) as total_amount,
            COUNT(banking_transaction_id) as with_banking,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN amount ELSE 0 END) as amount_with_banking
        FROM payments
        WHERE payment_method ILIKE %s
    """, (f'%{payment_type}%',))
    
    total, total_amt, with_bank, amt_with_bank = cur.fetchone()
    
    if total and total > 0:
        match_pct = (with_bank / total * 100) if total > 0 else 0
        print(f"\n{payment_type}:")
        print(f"  Total: {total:,} payments (${total_amt:,.2f})")
        print(f"  With banking: {with_bank:,} (${amt_with_bank:,.2f})")
        print(f"  Match rate: {match_pct:.1f}%")

# Check for recent changes to banking_transaction_id
print("\n" + "=" * 120)
print("RECENT BANKING_TRANSACTION_ID CHANGES CHECK")
print("=" * 120)

# Check if there's an updated_at or modified_date column
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'payments'
    AND (column_name LIKE '%updated%' OR column_name LIKE '%modified%' OR column_name LIKE '%changed%')
""")

timestamp_cols = cur.fetchall()

if timestamp_cols:
    print(f"\nFound timestamp columns: {[col[0] for col in timestamp_cols]}")
else:
    print("\n⚠️  No timestamp columns found to track changes")

# Check for NULL banking_transaction_id where payment_date matches banking
print("\n" + "=" * 120)
print("POTENTIAL LOST MATCHES (Payments without banking but dates match)")
print("=" * 120)

cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_date,
        p.payment_method,
        p.amount,
        p.reserve_number,
        COUNT(b.transaction_id) as matching_banking_txs
    FROM payments p
    LEFT JOIN banking_transactions b ON b.transaction_date = p.payment_date::date
        AND ABS(b.credit_amount - p.amount) < 0.01
    WHERE p.banking_transaction_id IS NULL
    AND p.payment_date IS NOT NULL
    GROUP BY p.payment_id, p.payment_date, p.payment_method, p.amount, p.reserve_number
    HAVING COUNT(b.transaction_id) > 0
    ORDER BY p.payment_date DESC
    LIMIT 20
""")

potential_matches = cur.fetchall()

if potential_matches:
    print(f"\nFound {len(potential_matches)} payments with potential banking matches:\n")
    for pay_id, date, method, amount, reserve, bank_count in potential_matches[:10]:
        print(f"Payment #{pay_id} | {date} | {method or 'N/A'} | ${amount:,.2f}")
        print(f"  Reserve: {reserve} | Found {bank_count} banking TX(s) with matching date/amount")
else:
    print("\n✅ No obvious lost matches found")

# Summary
print("\n" + "=" * 120)
print("DIAGNOSIS")
print("=" * 120)

if match_pct < 90:
    print(f"\n❌ CURRENT MATCH RATE: {match_pct:.1f}% (Should be 98%+)")
    print("\nPOSSIBLE CAUSES:")
    print("  1. Database restore from old backup (lost recent matching work)")
    print("  2. Script/migration that cleared banking_transaction_id")
    print("  3. Payments table recreated/rebuilt")
    print("  4. Banking transactions deleted/reimported")
    print("\nRECOMMENDATION:")
    print("  Re-run charter-payment-banking matching scripts")
else:
    print(f"\n✅ Match rate looks good: {match_pct:.1f}%")

cur.close()
conn.close()

print("\n" + "=" * 120)
