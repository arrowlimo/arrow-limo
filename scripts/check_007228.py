#!/usr/bin/env python3
"""Check reserve 007228 payments and charter details."""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("="*80)
print("RESERVE 007228 ANALYSIS")
print("="*80)

# Charter details
cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance, status, payment_status
    FROM charters
    WHERE reserve_number = '007228'
""")
charter = cur.fetchone()
if charter:
    print("\nCHARTER:")
    print(f"  Reserve: {charter[0]}")
    print(f"  Date: {charter[1]}")
    print(f"  Total Due: ${charter[2]:.2f}")
    print(f"  Paid Amount: ${charter[3]:.2f}")
    print(f"  Balance: ${charter[4]:.2f}")
    print(f"  Status: {charter[5]}")
    print(f"  Payment Status: {charter[6]}")
else:
    print("\n[ERROR] Charter 007228 not found!")

# Payments
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes, payment_key
    FROM payments
    WHERE reserve_number = '007228'
    ORDER BY payment_date
""")
payments = cur.fetchall()
print(f"\nPAYMENTS ({len(payments)} rows):")
for p in payments:
    print(f"  {p[0]:6d} | {p[1]} | ${p[2]:9.2f} | {p[3]:15s} | Key: {p[5]} | {p[4] or ''}")

# Total payments
total_paid = sum(p[2] for p in payments)
print(f"\nTotal payments: ${total_paid:.2f}")

# Charter charges
cur.execute("""
    SELECT charge_id, description, amount
    FROM charter_charges
    WHERE reserve_number = '007228'
""")
charges = cur.fetchall()
print(f"\nCHARGES ({len(charges)} rows):")
for c in charges:
    print(f"  {c[0]:6d} | {c[1]:40s} | ${c[2]:.2f}")

total_charges = sum(c[2] for c in charges)
print(f"\nTotal charges: ${total_charges:.2f}")

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)
print(f"Expected paid_amount: ${total_paid:.2f}")
print(f"Expected balance: ${total_charges - total_paid:.2f}")
print(f"Actual paid_amount: ${charter[3]:.2f}" if charter else "N/A")
print(f"Actual balance: ${charter[4]:.2f}" if charter else "N/A")

if charter:
    if abs(charter[3] - total_paid) > 0.01:
        print("\n[ISSUE] paid_amount mismatch!")
    if abs(charter[4] - (total_charges - total_paid)) > 0.01:
        print("[ISSUE] balance mismatch!")
    if charter[4] < -1.00:
        print("[ISSUE] Negative balance indicates refund or overpayment")

cur.close()
conn.close()
