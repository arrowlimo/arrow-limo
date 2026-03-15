#!/usr/bin/env python3
"""Analyze AUDIT system entries to understand their purpose before removal"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 70)
print("AUDIT ENTRY ANALYSIS")
print("=" * 70)

# Find all AUDIT entries
cur.execute("""
    SELECT COUNT(*) as total
    FROM charters
    WHERE reserve_number LIKE 'AUDIT%'
""")
total = cur.fetchone()['total']

print(f"\n📊 Total AUDIT entries: {total:,}")

# Get details
cur.execute("""
    SELECT reserve_number, charter_id, charter_date, 
           client_id, account_number, rate, balance, 
           total_amount_due, paid_amount, cancelled,
           created_at, updated_at, notes
    FROM charters
    WHERE reserve_number LIKE 'AUDIT%'
    ORDER BY reserve_number
""")

entries = cur.fetchall()

print(f"\n📋 AUDIT ENTRY DETAILS:")
for row in entries:
    print(f"\n   {row['reserve_number']} (ID: {row['charter_id']})")
    print(f"      Date: {row['charter_date']}")
    print(f"      Client: {row['client_id']} | Account: {row['account_number']}")
    print(f"      Rate: ${row['rate'] or 0:.2f} | Balance: ${row['balance'] or 0:.2f}")
    print(f"      Total due: ${row['total_amount_due'] or 0:.2f} | Paid: ${row['paid_amount'] or 0:.2f}")
    print(f"      Cancelled: {row['cancelled']}")
    print(f"      Created: {row['created_at']}")
    if row['notes']:
        print(f"      Notes: {row['notes'][:100]}")

# Check for related records
print(f"\n🔍 CHECKING RELATED RECORDS:")

for entry in entries:
    charter_id = entry['charter_id']
    reserve = entry['reserve_number']
    
    # Check payments
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM payments
        WHERE charter_id = %s OR reserve_number = %s
    """, (charter_id, reserve))
    
    payments = cur.fetchone()
    
    # Check charges
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(amount) as total
        FROM charter_charges
        WHERE charter_id = %s
    """, (charter_id,))
    
    charges = cur.fetchone()
    
    # Check payroll
    cur.execute("""
        SELECT COUNT(*) as cnt, SUM(gross_pay) as total
        FROM driver_payroll
        WHERE charter_id::integer = %s OR reserve_number = %s
    """, (charter_id, reserve))
    
    payroll = cur.fetchone()
    
    print(f"\n   {reserve}:")
    print(f"      Payments: {payments['cnt']} (${payments['total'] or 0:.2f})")
    print(f"      Charges: {charges['cnt']} (${charges['total'] or 0:.2f})")
    print(f"      Payroll: {payroll['cnt']} (${payroll['total'] or 0:.2f})")

# Check income_ledger
print(f"\n📊 INCOME LEDGER ENTRIES:")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM income_ledger
    WHERE reserve_number LIKE 'AUDIT%'
""")
ledger_count = cur.fetchone()['cnt']
print(f"   Income ledger entries: {ledger_count:,}")

if ledger_count > 0:
    cur.execute("""
        SELECT reserve_number, entry_date, entry_type, amount
        FROM income_ledger
        WHERE reserve_number LIKE 'AUDIT%'
        ORDER BY entry_date
    """)
    
    for row in cur.fetchall():
        print(f"   {row['reserve_number']}: {row['entry_type']} ${row['amount']:.2f} on {row['entry_date']}")

conn.close()
