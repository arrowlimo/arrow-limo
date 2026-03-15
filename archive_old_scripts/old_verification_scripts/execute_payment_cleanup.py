#!/usr/bin/env python3
"""Execute the payment cleanup - delete duplicates and QB contamination."""
import os
import psycopg2
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()

# Load the cleanup plan
with open('payment_cleanup_plan_20260205_153322.json', 'r') as f:
    cleanup_plan = json.load(f)

deletion_candidates = set(cleanup_plan['deletion_candidates'])

print("="*80)
print("EXECUTING PAYMENT CLEANUP")
print("="*80)
print(f"Total payments to delete: {len(deletion_candidates):,}")
print()

# Connect to local database
conn = psycopg2.connect(
    host='localhost',
    database=os.getenv('LOCAL_DB_NAME'),
    user=os.getenv('LOCAL_DB_USER'),
    password=os.getenv('LOCAL_DB_PASSWORD')
)

# Verify before deletion
cur = conn.cursor()
cur.execute("""
    SELECT COUNT(*) 
    FROM payments 
    WHERE payment_id = ANY(%s)
""", (list(deletion_candidates),))
count = cur.fetchone()[0]

print(f"✅ Verified {count:,} payments exist in database")

if count != len(deletion_candidates):
    print(f"⚠️  WARNING: Expected {len(deletion_candidates):,} but found {count:,}")
    response = input("\nContinue anyway? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Deletion cancelled")
        exit(0)

print("\n🔴 Ready to delete payments:")
print(f"   - Duplicates: {sum(len(g['delete_others']) for g in cleanup_plan['duplicate_groups'])}")
print(f"   - QB Contamination: {sum(item['contaminated_count'] for item in cleanup_plan['qb_contamination'])}")

response = input("\nProceed with deletion? (yes/no): ")
if response.lower() != 'yes':
    print("❌ Deletion cancelled")
    conn.close()
    exit(0)

# Execute deletion
print("\n⏳ Deleting payments...")
cur.execute("""
    DELETE FROM payments
    WHERE payment_id = ANY(%s)
""", (list(deletion_candidates),))

deleted_count = cur.rowcount
print(f"✅ Deleted {deleted_count:,} payments")

# Commit
conn.commit()
print("✅ Changes committed")

# Verify final count
cur.execute("SELECT COUNT(*) FROM payments")
final_count = cur.fetchone()[0]
print(f"\n📊 Final payment count: {final_count:,}")

cur.close()
conn.close()

print("\n✅ Cleanup complete")
print("\nNext step: Run forensic audit again to verify cleanup")
