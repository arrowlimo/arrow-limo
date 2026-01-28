#!/usr/bin/env python3
"""
Correct David-paid tagging by removing the tag from receipts that ARE in banking.
Only receipts WITHOUT banking matches should be tagged as David-paid.
"""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

print("\n" + "="*70)
print("CORRECTING DAVID-PAID TAGGING")
print("="*70 + "\n")

# Step 1: Find receipts that ARE in banking (should NOT be David-paid)
cur.execute("""
    SELECT DISTINCT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date
    FROM receipts r
    JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
    WHERE r.description ILIKE '%David paid%'
    AND (r.vendor_name ILIKE 'wix%' OR r.vendor_name ILIKE 'ionos%')
    ORDER BY r.receipt_date
""")

banking_matched = cur.fetchall()
print(f"Found {len(banking_matched)} receipts in banking that were incorrectly tagged as David-paid")

if banking_matched:
    print("\nRemoving 'David paid' tag from banking-matched receipts:")
    print("-"*70)
    
    for receipt_id, vendor, amount, date in banking_matched:
        # Remove "(David paid - reimbursement/loan)" from description
        cur.execute("""
            UPDATE receipts
            SET description = REPLACE(description, ' (David paid - reimbursement/loan)', '')
            WHERE receipt_id = %s
        """, (receipt_id,))
        print(f"  ✅ {vendor:<20} ${amount:>8.2f}  {date}")
    
    conn.commit()
    print(f"\n✅ Corrected {len(banking_matched)} receipts")

# Step 2: Verify final counts
cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name ILIKE 'godaddy%' THEN 'GoDaddy'
            WHEN vendor_name ILIKE 'wix%' THEN 'Wix'
            WHEN vendor_name ILIKE 'ionos%' THEN 'IONOS'
        END as vendor,
        COUNT(*) as total_receipts,
        SUM(CASE WHEN description ILIKE '%David paid%' THEN 1 ELSE 0 END) as david_paid,
        SUM(gross_amount) as total_amount,
        SUM(CASE WHEN description ILIKE '%David paid%' THEN gross_amount ELSE 0 END) as david_amount
    FROM receipts
    WHERE currency = 'USD'
    AND (vendor_name ILIKE 'godaddy%' OR vendor_name ILIKE 'wix%' OR vendor_name ILIKE 'ionos%')
    GROUP BY vendor
    ORDER BY vendor
""")

print("\n" + "="*70)
print("CORRECTED BREAKDOWN")
print("="*70)
print(f"\n{'Vendor':<10} │ {'Total':>5} │ {'David':>5} │ {'Banking':>7} │ {'David Amt':>12} │ {'Banking Amt':>12}")
print("-"*70)

total_receipts = 0
total_david = 0
total_david_amt = 0
total_banking_amt = 0

for vendor, total, david, total_amt, david_amt in cur.fetchall():
    banking = total - david
    banking_amt = total_amt - david_amt
    
    total_receipts += total
    total_david += david
    total_david_amt += david_amt
    total_banking_amt += banking_amt
    
    print(f"{vendor:<10} │ {total:>5} │ {david:>5} │ {banking:>7} │ ${david_amt:>11,.2f} │ ${banking_amt:>11,.2f}")

print("-"*70)
print(f"{'TOTALS':<10} │ {total_receipts:>5} │ {total_david:>5} │ {total_receipts-total_david:>7} │ ${total_david_amt:>11,.2f} │ ${total_banking_amt:>11,.2f}")

print("\n✅ David reimbursement owed: ${:,.2f}".format(total_david_amt))
print("="*70 + "\n")

cur.close()
conn.close()
