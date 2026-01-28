#!/usr/bin/env python3
"""
Show POINT OF SALE banking descriptions with generic prefix removed
to reveal the actual vendor name fragments
"""
import psycopg2
import re

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get all POINT OF SALE receipts with their banking descriptions
cur.execute("""
    SELECT DISTINCT
        bt.description as banking_desc,
        COUNT(*) as cnt
    FROM receipts r
    INNER JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE (r.vendor_name ILIKE '%point%of%sale%' OR r.vendor_name ILIKE '%pointofsale%')
      AND r.vendor_name NOT ILIKE '%peavey%'
      AND r.vendor_name NOT ILIKE '%pack%post%'
    GROUP BY bt.description
    ORDER BY cnt DESC
""")

print("VENDOR FRAGMENTS AFTER STRIPPING GENERIC PREFIX")
print("=" * 100)
print(f"{'Count':<8} | {'Vendor Fragment'}")
print("-" * 100)

for row in cur.fetchall():
    banking_desc, cnt = row
    
    # Strip common prefixes and transaction numbers
    cleaned = banking_desc
    
    # Remove "Point of Sale -" prefix (case insensitive)
    cleaned = re.sub(r'Point\s*of\s*Sale\s*-\s*', '', cleaned, flags=re.IGNORECASE)
    
    # Remove "Interac" keyword
    cleaned = re.sub(r'Interac\s+', '', cleaned, flags=re.IGNORECASE)
    
    # Remove "RETAIL PURCHASE" or "PURCHASE"
    cleaned = re.sub(r'RETAIL\s+PURCHASE\s+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'PURCHASE\s*', '', cleaned, flags=re.IGNORECASE)
    
    # Remove "Visa Debit"
    cleaned = re.sub(r'Visa\s+Debit\s+', '', cleaned, flags=re.IGNORECASE)
    
    # Remove "INTLVISA DEB"
    cleaned = re.sub(r'INTLVISA\s+DEB\s+', '', cleaned, flags=re.IGNORECASE)
    
    # Remove transaction numbers (12+ digits)
    cleaned = re.sub(r'\d{12,}', '', cleaned)
    
    # Remove card numbers (4506*******534)
    cleaned = re.sub(r'4506\*+\d{3,4}', '', cleaned)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if cleaned:
        print(f"{cnt:<8} | {cleaned}")
    else:
        print(f"{cnt:<8} | (EMPTY - no vendor name)")

cur.close()
conn.close()
