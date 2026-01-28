#!/usr/bin/env python3
"""Generate summary report of extracted PDF data"""
import psycopg2
import os
import json

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

conn = psycopg2.connect(**DSN)
cur = conn.cursor()

print("\n" + "="*70)
print("PDF EXTRACTION REPORT")
print("="*70)

# Overall status
cur.execute("""
    SELECT status, COUNT(*), 
           SUM(file_size)/1024/1024 AS size_mb
    FROM pdf_staging 
    GROUP BY status
    ORDER BY COUNT(*) DESC
""")

print("\n📊 Overall Status:")
print(f"{'Status':<15} {'Count':>8} {'Size (MB)':>12}")
print("-"*40)
for row in cur.fetchall():
    print(f"{row[0]:<15} {row[1]:>8} {float(row[2] or 0):>12.1f}")

# By category
cur.execute("""
    SELECT category, 
           COUNT(*) as total,
           SUM(CASE WHEN status='processed' THEN 1 ELSE 0 END) as processed,
           SUM(CASE WHEN extracted_data IS NOT NULL THEN 1 ELSE 0 END) as has_data
    FROM pdf_staging 
    GROUP BY category
    ORDER BY total DESC
""")

print(f"\n📋 By Category:")
print(f"{'Category':<15} {'Total':>8} {'Processed':>10} {'Has Data':>10}")
print("-"*50)
for row in cur.fetchall():
    print(f"{row[0]:<15} {row[1]:>8} {row[2]:>10} {row[3]:>10}")

# Sample extracted data for each category
print(f"\n🔍 Sample Extracted Data:")

categories = ['receipt', 'payroll', 'insurance', 'banking', 'vehicle']
for category in categories:
    cur.execute("""
        SELECT file_name, extracted_data
        FROM pdf_staging
        WHERE category = %s 
          AND extracted_data IS NOT NULL
          AND extracted_data::text != '{}'
        LIMIT 1
    """, (category,))
    
    result = cur.fetchone()
    if result:
        file_name, data = result
        print(f"\n  📄 {category.upper()}: {file_name[:50]}")
        # Data is already a dict from psycopg2's JSON type
        data_dict = data if isinstance(data, dict) else (json.loads(data) if data else {})
        for key, value in list(data_dict.items())[:5]:  # Show first 5 fields
            if isinstance(value, list):
                print(f"     {key}: {len(value)} items")
            else:
                str_val = str(value)[:60]
                print(f"     {key}: {str_val}")

# Useful extracted fields count
print(f"\n📊 Extracted Field Statistics:")

# Receipts with amounts
cur.execute("""
    SELECT COUNT(*)
    FROM pdf_staging
    WHERE category = 'receipt'
      AND extracted_data->>'amount' IS NOT NULL
""")
receipt_amounts = cur.fetchone()[0]
print(f"  Receipts with amounts: {receipt_amounts}")

# Payroll with gross pay
cur.execute("""
    SELECT COUNT(*)
    FROM pdf_staging
    WHERE category = 'payroll'
      AND extracted_data->>'gross_pay' IS NOT NULL
""")
payroll_amounts = cur.fetchone()[0]
print(f"  Payroll with gross pay: {payroll_amounts}")

# Insurance with policy numbers
cur.execute("""
    SELECT COUNT(*)
    FROM pdf_staging
    WHERE category = 'insurance'
      AND extracted_data->>'policy_number' IS NOT NULL
""")
insurance_policies = cur.fetchone()[0]
print(f"  Insurance with policy #: {insurance_policies}")

# Banking with account numbers
cur.execute("""
    SELECT COUNT(*)
    FROM pdf_staging
    WHERE category = 'banking'
      AND extracted_data->>'account_number' IS NOT NULL
""")
banking_accounts = cur.fetchone()[0]
print(f"  Banking with account #: {banking_accounts}")

# Vehicles with VINs
cur.execute("""
    SELECT COUNT(*)
    FROM pdf_staging
    WHERE category = 'vehicle'
      AND extracted_data->>'vin' IS NOT NULL
""")
vehicle_vins = cur.fetchone()[0]
print(f"  Vehicles with VINs: {vehicle_vins}")

print("\n" + "="*70)
print("[OK] PDF EXTRACTION COMPLETE")
print("="*70)
print("\n📋 Next Steps:")
print("  1. Query specific data: SELECT * FROM pdf_staging WHERE category='payroll'")
print("  2. Export to CSV: \\copy (SELECT ...) TO 'output.csv' CSV HEADER")
print("  3. Import into target tables based on extracted_data fields")

cur.close()
conn.close()
