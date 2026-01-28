#!/usr/bin/env python3
"""
Summarize 25 charters not yet fixed in LMS (both systems still show balance).
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

UNFIXED_RESERVES = [
    ('015940', '2021-08-27', 'cancelled'),
    ('014189', '2019-03-21', 'cancelled'),
    ('017887', '2023-08-18', 'UNCLOSED'),
    ('001764', '2008-02-06', 'Closed'),
    ('015978', '2021-08-28', 'Closed'),
    ('014640', '2020-08-29', 'Closed'),
    ('005711', '2011-12-21', 'Closed'),
    ('015211', '2020-02-24', 'Closed'),
    ('015195', '2020-02-04', 'Closed'),
    ('015049', '2019-11-28', 'Closed'),
    ('017765', '2023-07-04', ''),
    ('018013', '2023-10-09', ''),
    ('015315', '2020-03-22', 'Closed'),
    ('015288', '2020-03-24', 'cancelled'),
    ('015244', '2020-03-05', 'cancelled'),
    ('015144', '2020-02-11', 'Closed'),
    ('017301', '2022-12-31', 'Closed'),
    ('017891', '2023-08-23', ''),
    ('013874', '2018-06-06', 'Closed'),
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("25 Unfixed Receivables (balance in both LMS and almsdata)")
print("=" * 90)
print(f"{'Reserve':<12} {'Date':<12} {'Status':<15} {'Charges':<15} {'Payments':<15} {'Balance':<15}")
print("-" * 90)

total_balance = 0.0
cancelled_count = 0
closed_count = 0
other_count = 0

for reserve, date, status in UNFIXED_RESERVES:
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments,
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) - 
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as balance
    """, (reserve, reserve, reserve, reserve))
    
    charges, payments, balance = cur.fetchone()
    charges, payments, balance = float(charges), float(payments), float(balance)
    
    print(f"{reserve:<12} {date:<12} {status:<15} ${charges:>13.2f} ${payments:>13.2f} ${balance:>13.2f}")
    
    total_balance += balance
    if 'cancel' in status.lower():
        cancelled_count += 1
    elif 'closed' in status.lower():
        closed_count += 1
    else:
        other_count += 1

print("-" * 90)
print(f"Total balance owed: ${total_balance:,.2f}")
print()
print("Status breakdown:")
print(f"  Cancelled: {cancelled_count} (3 reserves)")
print(f"  Closed: {closed_count}")
print(f"  Other/Blank: {other_count}")
print()
print("OPTIONS:")
print("  1. Write down all 25 (remove charges, zero balance)")
print("  2. Write down only Cancelled ones (3 reserves)")
print("  3. Write down only Closed ones")
print("  4. Keep investigating (case-by-case)")

cur.close()
conn.close()
