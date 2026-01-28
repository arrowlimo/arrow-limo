#!/usr/bin/env python3
"""Check for receipts created from e-transfer data."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 100)
print("E-TRANSFER RECEIPTS ANALYSIS")
print("=" * 100)

# 1. Count e-transfer receipts
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as banking_linked,
        COUNT(*) FILTER (WHERE created_from_banking = true) as auto_created,
        SUM(CASE WHEN revenue > 0 THEN revenue ELSE 0 END) as total_revenue,
        SUM(CASE WHEN expense > 0 THEN expense ELSE 0 END) as total_expense
    FROM receipts
    WHERE description ILIKE '%e-transfer%' 
       OR description ILIKE '%email transfer%'
       OR vendor_name ILIKE '%e-transfer%'
       OR vendor_name ILIKE '%email transfer%'
""")

total, banking_linked, auto_created, revenue, expense = cur.fetchone()

print(f"\n1️⃣  E-TRANSFER RECEIPT COUNTS")
print("-" * 100)
print(f"Total e-transfer receipts: {total:,}")
print(f"Linked to banking: {banking_linked:,}")
print(f"Auto-created from banking: {auto_created:,}")
print(f"Total revenue: ${revenue:,.2f}" if revenue else "Total revenue: $0.00")
print(f"Total expense: ${expense:,.2f}" if expense else "Total expense: $0.00")

# 2. Breakdown by vendor
print(f"\n2️⃣  E-TRANSFER RECEIPTS BY VENDOR")
print("-" * 100)

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount,
        COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as banking_linked
    FROM receipts
    WHERE description ILIKE '%e-transfer%' 
       OR description ILIKE '%email transfer%'
       OR vendor_name ILIKE '%e-transfer%'
       OR vendor_name ILIKE '%email transfer%'
    GROUP BY vendor_name
    ORDER BY count DESC
    LIMIT 20
""")

print(f"\n{'Vendor':<40s} | {'Count':>6s} | {'Total Amount':>15s} | Banking")
print("-" * 90)
for vendor, count, amount, banking in cur.fetchall():
    vendor_display = (vendor[:40] if vendor else "Unknown")
    print(f"{vendor_display:40s} | {count:>6,d} | ${amount:>14,.2f} | {banking:>7,d}")

# 3. Sample e-transfer receipts
print(f"\n3️⃣  SAMPLE E-TRANSFER RECEIPTS (Latest 15)")
print("-" * 100)

cur.execute("""
    SELECT 
        receipt_date,
        vendor_name,
        gross_amount,
        revenue,
        expense,
        banking_transaction_id,
        description
    FROM receipts
    WHERE description ILIKE '%e-transfer%' 
       OR description ILIKE '%email transfer%'
       OR vendor_name ILIKE '%e-transfer%'
       OR vendor_name ILIKE '%email transfer%'
    ORDER BY receipt_date DESC
    LIMIT 15
""")

print(f"\n{'Date':<12s} | {'Vendor':<25s} | {'Amount':>10s} | Type   | Bank ID | Description")
print("-" * 100)
for date, vendor, amount, revenue, expense, bank_id, desc in cur.fetchall():
    vendor_display = (vendor[:25] if vendor else "Unknown")
    txn_type = "Revenue" if revenue and revenue > 0 else ("Expense" if expense and expense > 0 else "Neither")
    bank_str = str(bank_id) if bank_id else "None"
    desc_short = (desc[:30] if desc else "")
    print(f"{str(date):12s} | {vendor_display:25s} | ${amount:>9.2f} | {txn_type:6s} | {bank_str:>7s} | {desc_short}")

# 4. Check for e-transfers by year
print(f"\n4️⃣  E-TRANSFER RECEIPTS BY YEAR")
print("-" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE description ILIKE '%e-transfer%' 
       OR description ILIKE '%email transfer%'
       OR vendor_name ILIKE '%e-transfer%'
       OR vendor_name ILIKE '%email transfer%'
    GROUP BY year
    ORDER BY year DESC
""")

print(f"\n{'Year':<6s} | {'Count':>8s} | {'Total Amount':>15s}")
print("-" * 40)
for year, count, amount in cur.fetchall():
    print(f"{int(year) if year else 0:<6d} | {count:>8,d} | ${amount:>14,.2f}")

print("\n" + "=" * 100)

cur.close()
conn.close()
