"""
Identify charters with H## (host) codes vs DR## (driver) codes.
Hosts are contracted/hired people, not regular employees.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Check for duplicate H codes in employees
cur.execute("""
    SELECT driver_code, COUNT(*), STRING_AGG(full_name, ', ')
    FROM employees
    WHERE driver_code LIKE 'H%'
    GROUP BY driver_code
    HAVING COUNT(*) > 1
""")

duplicates = cur.fetchall()
if duplicates:
    print("⚠️  DUPLICATE H CODES IN EMPLOYEES:")
    print("=" * 80)
    for code, count, names in duplicates:
        print(f"  {code}: {count} employees - {names}")
    print()

# List all H-code employees
cur.execute("""
    SELECT employee_id, driver_code, full_name, employee_category, employment_status
    FROM employees
    WHERE driver_code LIKE 'H%'
    ORDER BY driver_code
""")

h_employees = cur.fetchall()
print(f"HOST EMPLOYEES (H## codes): {len(h_employees)}")
print("=" * 80)
for emp_id, code, name, category, status in h_employees:
    print(f"  {code}: {name} ({category}, {status})")
print()

# Find charters with H-code drivers
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.client_display_name,
        e.driver_code,
        e.full_name as driver_name,
        c.total_amount_due
    FROM charters c
    JOIN employees e ON c.assigned_driver_id = e.employee_id
    WHERE e.driver_code LIKE 'H%'
    ORDER BY c.charter_date, c.reserve_number
""")

host_charters = cur.fetchall()
print(f"CHARTERS WITH HOST DRIVERS (H## codes): {len(host_charters)}")
print("=" * 80)

if host_charters:
    # Group by host
    by_host = {}
    total_revenue = 0
    for reserve, date, client, code, driver, amount in host_charters:
        if code not in by_host:
            by_host[code] = {'driver': driver, 'charters': [], 'total': 0}
        by_host[code]['charters'].append((reserve, date, client, amount))
        by_host[code]['total'] += float(amount) if amount else 0
        total_revenue += float(amount) if amount else 0
    
    for code in sorted(by_host.keys()):
        info = by_host[code]
        print(f"\n{code} - {info['driver']}: {len(info['charters'])} charters, ${info['total']:,.2f}")
        print("  Sample charters:")
        for reserve, date, client, amount in info['charters'][:5]:
            print(f"    {reserve} | {date} | {client} | ${amount:,.2f}")
        if len(info['charters']) > 5:
            print(f"    ... and {len(info['charters']) - 5} more")
    
    print()
    print("=" * 80)
    print(f"Total host charter revenue: ${total_revenue:,.2f}")
else:
    print("  No charters found with H## driver codes")
    print()

# Check LMS staging for H codes
cur.execute("""
    SELECT driver_code, COUNT(*)
    FROM lms2026_reserves
    WHERE driver_code LIKE 'H%'
    GROUP BY driver_code
    ORDER BY driver_code
""")

lms_h_codes = cur.fetchall()
print(f"\nLMS STAGING H## CODES: {len(lms_h_codes)} unique codes")
print("=" * 80)
for code, count in lms_h_codes:
    print(f"  {code}: {count} reservations")

cur.close()
conn.close()
