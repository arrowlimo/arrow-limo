#!/usr/bin/env python3
"""Delete ONLY true orphan error receipts (no banking references)."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("DELETE TRUE ORPHAN ERROR RECEIPTS (No Banking References)")
print("=" * 100)

# Only delete receipts that are NOT referenced in banking_transactions
deletion_queries = [
    ("OPENING BALANCE (no banking link)", 
     "vendor_name = 'OPENING BALANCE' AND receipt_id NOT IN (SELECT receipt_id FROM banking_transactions WHERE receipt_id IS NOT NULL)"),
    ("TELUS [DUPLICATE - IGNORE] (marked obsolete)", 
     "vendor_name LIKE '%TELUS%DUP%' AND receipt_id NOT IN (SELECT receipt_id FROM banking_transactions WHERE receipt_id IS NOT NULL)"),
]

# Report what will be deleted
total_delete_count = 0
total_delete_amount = 0
delete_details = []

print("\nDELETION PREVIEW:")
for category, where_clause in deletion_queries:
    cur.execute(f"""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) as total_amount
        FROM receipts
        WHERE {where_clause}
    """)
    count, amount = cur.fetchone()
    if count > 0:
        total_delete_count += count
        total_delete_amount += amount if amount else 0
        print(f"  • {category}: {count} receipts, ${amount:,.2f}")
        delete_details.append((category, where_clause, count, amount))

if total_delete_count == 0:
    print("  • No true orphan errors found for deletion")
    cur.close()
    conn.close()
    exit(0)

print(f"\nTOTAL TO DELETE: {total_delete_count} receipts, ${total_delete_amount:,.2f}")
print("\n⚠️  WARNING: These receipts will be PERMANENTLY DELETED.")
print("Proceed with deletion? [YES/NO]:")

response = input().strip().upper()
if response != "YES":
    print("❌ Deletion cancelled by user.")
    cur.close()
    conn.close()
    exit(1)

print("\n" + "=" * 100)
print("EXECUTING DELETIONS...")
print("=" * 100)

# Execute deletions
for category, where_clause, count, amount in delete_details:
    try:
        cur.execute(f"DELETE FROM receipts WHERE {where_clause}")
        affected = cur.rowcount
        conn.commit()
        print(f"✅ {category}: Deleted {affected} receipts")
    except Exception as e:
        conn.rollback()
        print(f"❌ {category}: Failed - {e}")

print("\n" + "=" * 100)
print("DELETION COMPLETE")
print("=" * 100)

# Verify final count
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
final_count, final_amount = cur.fetchone()
print(f"\nFinal receipts: {final_count} records, ${final_amount:,.2f}")
print(f"Deleted: {total_delete_count} records, ${total_delete_amount:,.2f}")

cur.close()
conn.close()
