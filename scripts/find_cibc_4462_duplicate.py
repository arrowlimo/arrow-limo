#!/usr/bin/env python3
"""Find the duplicate transaction from cibc 4462 2025.csv"""
import csv
from datetime import datetime
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print("=== FINDING DUPLICATE FROM CIBC 4462 2025.CSV ===\n")

csv_path = r"l:\limo\CIBC UPLOADS\8314462 (CIBC vehicle loans)\cibc 4462 2025.csv"

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    
    for row_num, row in enumerate(reader, 1):
        if not row or len(row) < 4:
            continue
        
        date_str, description, debit, credit = row[0], row[1], row[2], row[3]
        
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        
        # Determine amount and type
        if debit:
            amount = float(debit)
        elif credit:
            amount = float(credit)
        else:
            continue
        
        # Check if exists in receipts table
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, expense, description
            FROM receipts
            WHERE created_from_banking = true
              AND receipt_date = %s
              AND vendor_name = %s
              AND (ABS(COALESCE(expense, 0) - %s) < 0.01 OR ABS(COALESCE(revenue, 0) - %s) < 0.01)
            LIMIT 1
        """, (date_str, description[:50], amount, amount))
        
        result = cur.fetchone()
        if result:
            print(f"[DUPLICATE FOUND]")
            print(f"  CSV Row {row_num}: {date_str} | {description} | ${amount:.2f}")
            print(f"  Existing Receipt: ID={result[0]}, Date={result[1]}, Vendor={result[2]}, Amount={result[3]}, Desc={result[4][:50]}")
            print()

conn.close()
