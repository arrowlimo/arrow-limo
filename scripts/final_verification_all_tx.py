#!/usr/bin/env python3
"""Final verification - confirm all CHQ matches to banking TX"""

import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 80)
print("FINAL VERIFICATION - ALL CHQ MATCHES CONFIRMED")
print("=" * 80)

# Get all Scotia cheques (1-117)
cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER BETWEEN 1 AND 117
    ORDER BY cheque_number::INTEGER
""")

all_cheques = cur.fetchall()

# Analyze
total = 0
with_tx = 0
with_date = 0
void_checks = 0
nsf_checks = 0

print(f"\nScotia Bank Cheques (1-117) Summary:")
print("-" * 80)

for num, date, payee, amount, tx_id, status in all_cheques:
    total += 1
    num_int = int(num) if isinstance(num, str) else num
    
    if tx_id:
        with_tx += 1
    if date:
        with_date += 1
    if status == 'VOID':
        void_checks += 1
    if status == 'NSF':
        nsf_checks += 1

print(f"Total Scotia cheques: {total}")
print(f"With banking TX ID: {with_tx} ({with_tx/total*100:.1f}%)")
print(f"With cheque dates: {with_date} ({with_date/total*100:.1f}%)")
print(f"VOID cheques: {void_checks}")
print(f"NSF cheques: {nsf_checks}")

# Show problem cheques that don't have TX
print(f"\n\nCheques WITHOUT banking TX ID:")
print("-" * 80)

cur.execute("""
    SELECT cheque_number, payee, amount, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER BETWEEN 1 AND 117
      AND banking_transaction_id IS NULL
    ORDER BY cheque_number::INTEGER
""")

no_tx = cur.fetchall()
if no_tx:
    for num, payee, amount, status in no_tx:
        num_int = int(num) if isinstance(num, str) else num
        print(f"CHQ {num_int:3d}: {payee:30s} ${amount:10.2f} | {status}")
else:
    print("✓ ALL CHECKS HAVE BANKING TX IDs")

# Show key cheques we just fixed
print(f"\n\nKEY CHEQUES - VERIFICATION:")
print("-" * 80)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, banking_transaction_id, status
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER IN (22, 23, 93, 108, 117, 213)
    ORDER BY cheque_number::INTEGER
""")

key_cheques = cur.fetchall()
for num, date, payee, amount, tx_id, status in key_cheques:
    num_int = int(num) if isinstance(num, str) else num
    date_str = str(date) if date else "NULL"
    tx_str = f"TX {tx_id}" if tx_id else "NO TX"
    
    # Verify this TX exists in banking
    if tx_id:
        cur.execute("""
            SELECT description FROM banking_transactions
            WHERE transaction_id = %s
        """, (tx_id,))
        banking = cur.fetchone()
        banking_desc = banking[0][:50] if banking else "NOT FOUND"
    else:
        banking_desc = "N/A"
    
    check_mark = "✓" if tx_id else "✗"
    print(f"{check_mark} CHQ {num_int:3d}: {payee:25s} ${amount:10.2f} | {date_str:10s} | {tx_str:10s}")
    if tx_id:
        print(f"           Banking: {banking_desc}")

# Final summary table
print(f"\n\n" + "=" * 80)
print("FINAL SUMMARY TABLE")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_cheques,
        SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as linked_to_banking,
        SUM(CASE WHEN status = 'VOID' THEN 1 ELSE 0 END) as void_count,
        SUM(CASE WHEN status = 'NSF' THEN 1 ELSE 0 END) as nsf_count,
        SUM(CASE WHEN cheque_date IS NOT NULL THEN 1 ELSE 0 END) as with_dates
    FROM cheque_register
    WHERE cheque_number ~ '^[0-9]+$'
      AND cheque_number::INTEGER BETWEEN 1 AND 117
""")

stats = cur.fetchone()
total, linked, void, nsf, with_dates = stats

print(f"\nScotia Cheques 1-117 Statistics:")
print(f"  Total cheques: {total}")
print(f"  Linked to banking TX: {linked}/{total} ({linked/total*100:.1f}%)")
print(f"  With cheque dates: {with_dates}/{total} ({with_dates/total*100:.1f}%)")
print(f"  VOID cheques: {void}")
print(f"  NSF cheques: {nsf}")

print("\n" + "=" * 80)
if linked == total:
    print("✓✓✓ VERIFICATION COMPLETE - ALL CHEQUES HAVE BANKING MATCHES ✓✓✓")
else:
    print(f"⚠️  {total - linked} cheques still without banking TX ID")
print("=" * 80)

cur.close()
conn.close()
