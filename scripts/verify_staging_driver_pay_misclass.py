import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("STAGING_DRIVER_PAY - DATA MISCLASSIFICATION ANALYSIS")
print("=" * 80)

# The "driver_name" field contains account codes/names, not driver names!
print("\nDISCOVERY: staging_driver_pay contains QuickBooks GL data, NOT payroll data")
print("-" * 80)

cur.execute("""
    SELECT source_file, COUNT(*) as cnt
    FROM staging_driver_pay
    GROUP BY source_file
    ORDER BY cnt DESC
    LIMIT 20
""")

print("\nSource files (these are NOT payroll files):")
for source, cnt in cur.fetchall():
    print(f"  {source or 'NULL':<50} {cnt:>8,} rows")

# Check if any ACTUAL payroll-related data exists
print("\n" + "=" * 80)
print("SEARCHING FOR ACTUAL PAYROLL DATA")
print("=" * 80)

# Look for employee names in driver_name field
cur.execute("""
    SELECT e.full_name, COUNT(*) as matches
    FROM employees e
    JOIN staging_driver_pay s ON LOWER(TRIM(s.driver_name)) LIKE '%' || LOWER(TRIM(e.full_name)) || '%'
    GROUP BY e.full_name
    ORDER BY matches DESC
    LIMIT 20
""")

payroll_matches = cur.fetchall()
if payroll_matches:
    print("\nFound employee name matches in staging_driver_pay:")
    for name, cnt in payroll_matches:
        print(f"  {name}: {cnt:,} rows")
else:
    print("\nNO employee names found in staging_driver_pay")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
[FAIL] CRITICAL ERROR: staging_driver_pay is MISNAMED

The table contains:
- QuickBooks general ledger account data
- Account codes (2200, 1090, 6925, etc.)
- Account names (GST/HST Payable, Bank Shareholder, Fuel, etc.)
- NOT payroll/driver pay data

Actual contents:
- Source files: "Account History.xls", "ap aging summary.xlsx", etc.
- "driver_name" field: Contains QB account codes/names
- Zero amounts: GL data may not have been properly extracted

Recommendation:
1. This table should be RENAMED (e.g., staging_qb_accounts or staging_gl_misc)
2. The 262,884 rows are NOT employee pay records
3. Real driver payroll data is in driver_payroll table (18,517 records)
4. staging_driver_pay data quality issues are IRRELEVANT for payroll

Action: Mark staging_driver_pay as misclassified QB data, not payroll staging.
""")

cur.close()
conn.close()
