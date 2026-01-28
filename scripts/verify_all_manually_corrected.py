#!/usr/bin/env python3
"""
Verify ALL manually corrected reserves are now fixed in almsdata.
List of reserves user corrected in LMS + our corresponding fixes.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

# All reserves manually corrected in LMS (from our conversation)
MANUALLY_CORRECTED = [
    ('017991', 'marked cancelled'),
    ('017887', 'marked cancelled, 0 payments'),
    ('017765', 'marked cancelled, no charges'),
    ('018013', 'marked cancelled, no charges'),
    ('015940', 'zero balanced by GST=discount'),
    ('014189', 'cancelled, charges deleted'),
    ('015288', 'cancelled'),
    ('015244', 'cancelled (NRD)'),
    ('001764', 'full payment recovered'),
    ('005711', 'full payment recovered'),
    ('015978', "driver's own run"),
    ('014640', 'verified balanced'),
    ('013874', 'fixed in LMS'),
    ('015049', 'added cash payment'),
    ('015315', 'cancelled, no charges'),
    ('017891', 'fixed (we corrected earlier)'),
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("VERIFICATION: All Manually Corrected Reserves in almsdata")
print("=" * 100)
print()

fixed = []
still_active = []

for reserve, lms_action in MANUALLY_CORRECTED:
    cur.execute("""
        SELECT 
            c.status,
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments
        FROM charters c
        WHERE c.reserve_number = %s
    """, (reserve, reserve, reserve))
    
    row = cur.fetchone()
    if not row:
        print(f"✗ {reserve}: NOT FOUND IN ALMSDATA")
        continue
    
    status, charges, payments = row
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    
    # Check if fixed (balance ~0) or cancelled
    if abs(balance) < 1.0 or (status and 'cancel' in status.lower()):
        fixed.append((reserve, status, balance, lms_action))
        print(f"✓ {reserve:<10} | Status: {status or 'BLANK':<12} | Balance: ${balance:>8.2f} | {lms_action}")
    else:
        still_active.append((reserve, status, balance, lms_action))
        print(f"⚠ {reserve:<10} | Status: {status or 'BLANK':<12} | Balance: ${balance:>8.2f} | {lms_action}")

print()
print("=" * 100)
print(f"SUMMARY:")
print(f"  ✓ FIXED: {len(fixed)} reserves")
print(f"  ⚠ STILL ACTIVE: {len(still_active)} reserves")
print(f"  TOTAL: {len(MANUALLY_CORRECTED)}")
print("=" * 100)

if still_active:
    print()
    print("Still active (may need further review):")
    for reserve, status, balance, action in still_active:
        print(f"  - {reserve} (${balance:.2f}) - {action}")

cur.close()
conn.close()
