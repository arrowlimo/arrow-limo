#!/usr/bin/env python
"""Export receipts that are not linked to banking transactions."""

import psycopg2
import os
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*80)
print("UNLINKED RECEIPTS REPORT")
print("="*80)

cur.execute("""
    SELECT source_system, source_file, COUNT(*) as cnt,
           ROUND(SUM(COALESCE(gross_amount,0))::numeric,2) as total
    FROM receipts
    WHERE banking_transaction_id IS NULL
    GROUP BY source_system, source_file
    ORDER BY cnt DESC
""")

groups = cur.fetchall()
print(f"Found {len(groups)} source groups without banking links")

os.makedirs('reports', exist_ok=True)
filename = f"reports/unlinked_receipts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(filename, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["source_system", "source_file", "count", "total_amount"])
    for row in groups:
        writer.writerow([row[0], row[1], row[2], f"${float(row[3]):.2f}"])

print(f"CSV written: {filename}")

# Show top 10 rows to console
print("\nTop groups:")
for row in groups[:10]:
    print(f"  {row[0]:<20} {str(row[1])[:40]:<40} {row[2]:>5} | ${float(row[3]):>12.2f}")

cur.close()
conn.close()
