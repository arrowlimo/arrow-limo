#!/usr/bin/env python3
"""Show summary of staged PDFs"""
import psycopg2
import os

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
print("STAGED PDFs SUMMARY")
print("="*70)

# By category
cur.execute("""
    SELECT category, COUNT(*), SUM(file_size)/1024/1024 AS size_mb 
    FROM pdf_staging 
    GROUP BY category 
    ORDER BY COUNT(*) DESC
""")

print("\n📊 By Category:")
print(f"{'Category':<15} {'Count':>8} {'Size (MB)':>12}")
print("-"*40)
for row in cur.fetchall():
    print(f"{row[0]:<15} {row[1]:>8} {float(row[2] or 0):>12.1f}")

# Total
cur.execute("SELECT COUNT(*), SUM(file_size)/1024/1024 FROM pdf_staging")
total = cur.fetchone()
print("-"*40)
print(f"{'TOTAL':<15} {total[0]:>8} {float(total[1]):>12.1f}")

# Sample files by category
print(f"\n📋 Sample files by category:")
cur.execute("""
    SELECT DISTINCT ON (category) 
        category, file_name, year_detected
    FROM pdf_staging 
    WHERE category != 'other'
    ORDER BY category, year_detected DESC
""")

for row in cur.fetchall():
    print(f"  {row[0]:12} {row[2] or 'N/A':>6} | {row[1][:50]}")

print("\n[OK] Staging complete! Ready for extraction.")

cur.close()
conn.close()
