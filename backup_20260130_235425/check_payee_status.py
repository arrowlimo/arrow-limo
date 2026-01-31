#!/usr/bin/env python
"""Check cheque register payee status after QB updates"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Overall stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN payee IS NOT NULL AND payee != 'Unknown' THEN 1 END) as with_payee
    FROM cheque_register
""")
total, with_payee = cur.fetchone()
missing = total - with_payee

print("=" * 60)
print("CHEQUE REGISTER PAYEE STATUS")
print("=" * 60)
print(f"Total cheques: {total}")
print(f"With payee: {with_payee} ({100*with_payee/total:.1f}%)")
print(f"Missing payee: {missing} ({100*missing/total:.1f}%)")

# Show sample of updated cheques
print("\n" + "=" * 60)
print("SAMPLE OF UPDATED PAYEES")
print("=" * 60)

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount
    FROM cheque_register
    WHERE payee IS NOT NULL AND payee != 'Unknown'
    ORDER BY cheque_date
    LIMIT 20
""")

for row in cur.fetchall():
    cheque_num, date, payee, amount = row
    print(f"Cheque #{cheque_num} | {date} | {payee[:35]:35s} | ${amount:>10,.2f}")

# Show still missing
print("\n" + "=" * 60)
print(f"STILL MISSING PAYEE ({missing} cheques)")
print("=" * 60)

cur.execute("""
    SELECT cheque_number, cheque_date, amount
    FROM cheque_register
    WHERE payee IS NULL OR payee = 'Unknown'
    ORDER BY cheque_date
    LIMIT 20
""")

for row in cur.fetchall():
    cheque_num, date, amount = row
    print(f"Cheque #{cheque_num} | {date} | ${amount:>10,.2f}")

cur.close()
conn.close()
