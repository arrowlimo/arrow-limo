#!/usr/bin/env python3
"""Quick verification of LMS import results."""
import os
import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# Check overall stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN is_chauffeur THEN 1 END) as chauffeurs,
        COUNT(CASE WHEN employment_status = 'inactive' THEN 1 END) as inactive,
        COUNT(CASE WHEN employment_status = 'active' THEN 1 END) as active,
        COUNT(CASE WHEN employee_number LIKE 'DR%' THEN 1 END) as dr_codes,
        COUNT(CASE WHEN employee_number LIKE 'H%' THEN 1 END) as h_codes,
        COUNT(CASE WHEN employee_number LIKE 'OF%' THEN 1 END) as of_codes,
        COUNT(CASE WHEN driver_license_number IS NOT NULL THEN 1 END) as has_license,
        COUNT(CASE WHEN chauffeur_permit_expiry IS NOT NULL THEN 1 END) as has_permit,
        COUNT(CASE WHEN email IS NOT NULL THEN 1 END) as has_email,
        COUNT(CASE WHEN t4_sin IS NOT NULL THEN 1 END) as has_sin
    FROM employees
""")
stats = cur.fetchone()
print("=== EMPLOYEE TABLE STATISTICS ===")
print(f"Total employees: {stats['total']}")
print(f"Chauffeurs: {stats['chauffeurs']}")
print(f"Active: {stats['active']}, Inactive: {stats['inactive']}")
print(f"\nEmployee codes:")
print(f"  DR (Drivers): {stats['dr_codes']}")
print(f"  H (Helpers/Office): {stats['h_codes']}")
print(f"  OF (Office): {stats['of_codes']}")
print(f"\nData completeness:")
print(f"  Has driver license: {stats['has_license']}")
print(f"  Has chauffeur permit: {stats['has_permit']}")
print(f"  Has email: {stats['has_email']}")
print(f"  Has SIN: {stats['has_sin']}")

# Sample records
print("\n=== SAMPLE LMS-IMPORTED RECORDS ===")
cur.execute("""
    SELECT employee_number, full_name, employment_status, 
           driver_license_number, 
           TO_CHAR(chauffeur_permit_expiry, 'YYYY-MM-DD') as permit_exp,
           email, phone, cell_phone, t4_sin
    FROM employees 
    WHERE employee_number IN ('DR113', 'DR101', 'H04', 'OF04')
    ORDER BY employee_number
""")
for r in cur.fetchall():
    print(f"\n{r['employee_number']} - {r['full_name']}")
    print(f"  Status: {r['employment_status']}")
    print(f"  License: {r['driver_license_number'] or 'N/A'}")
    print(f"  Permit Expiry: {r['permit_exp'] or 'N/A'}")
    print(f"  Email: {r['email'] or 'N/A'}")
    print(f"  Phone: {r['phone'] or 'N/A'} / Cell: {r['cell_phone'] or 'N/A'}")
    print(f"  SIN: {r['t4_sin'] or 'N/A'}")

cur.close()
conn.close()
