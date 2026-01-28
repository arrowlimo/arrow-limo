#!/usr/bin/env python3
"""Mark all 89 restored cheque_register entries as unmatched."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("MARK CHEQUE_REGISTER ENTRIES AS UNMATCHED")
print("=" * 100 + "\n")

# First, check current status values
cur.execute("""
    SELECT DISTINCT status FROM cheque_register
    WHERE account_number = '0228362'
    ORDER BY status
""")

statuses = cur.fetchall()
print("Current status values:\n")
for (status,) in statuses:
    print(f"  • {status}")

# Update to mark as unmatched
print("\nUpdating status to 'unmatched'...\n")

cur.execute("""
    UPDATE cheque_register
    SET status = 'unmatched', banking_transaction_id = NULL
    WHERE account_number = '0228362'
""")

updated = cur.rowcount
conn.commit()

print(f"✅ Updated {updated} cheque_register entries to 'unmatched'")

# Verify
cur.execute("""
    SELECT COUNT(*), status FROM cheque_register
    WHERE account_number = '0228362'
    GROUP BY status
""")

print("\nVerification:\n")
for count, status in cur.fetchall():
    print(f"  {status}: {count} cheques")

cur.close()
conn.close()

print("\n✅ All cheques marked as unmatched (ready for re-matching against PDF statements)")
