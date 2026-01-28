"""
Check if specific LMS deposit refunds are in charter_refunds table.
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# LMS refunds to check
LMS_REFUNDS = [
    ('0020670', '2023-12-07', 231.00, 'Refund'),
    ('0020858', '2024-02-12', 31.50, ''),
    ('0021292', '2024-07-17', 200.00, 'Remb Cab Fare/meal'),
    ('0021302', '2024-07-22', 720.00, ''),
    ('0021305', '2024-07-22', 239.85, '07/22/24'),
    ('0022254', '2025-06-20', 100.00, 'Credit'),  # Note: positive amount
    ('0022319', '2025-07-15', 173.25, 'Wanted Tip Back Paid'),
    ('0022341', '2025-07-21', 150.93, ''),
    ('0022368', '2025-07-28', 400.00, ''),  # Note: positive amount
]

print("="*80)
print("CHECKING LMS REFUNDS IN CHARTER_REFUNDS TABLE")
print("="*80)

found_count = 0
missing_count = 0
unlinked_count = 0

for deposit_num, refund_date, amount, description in LMS_REFUNDS:
    print(f"\n{'*'*60}")
    print(f"LMS Deposit {deposit_num}: ${amount} on {refund_date}")
    print(f"  Description: {description if description else '(none)'}")
    
    # Search by amount and approximate date (within 7 days)
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id, 
               description, source_file
        FROM charter_refunds
        WHERE ABS(amount) = %s
          AND refund_date BETWEEN %s::date - INTERVAL '7 days' 
                              AND %s::date + INTERVAL '7 days'
        ORDER BY ABS(refund_date - %s::date)
        LIMIT 3
    """, (amount, refund_date, refund_date, refund_date))
    matches = cur.fetchall()
    
    if matches:
        print(f"  [OK] FOUND {len(matches)} match(es):")
        for match in matches:
            refund_id, date, amt, reserve, charter, desc, source = match
            linked = "[OK] LINKED" if reserve and charter else "[FAIL] UNLINKED"
            print(f"    Refund #{refund_id}: ${amt} on {date} - {linked}")
            print(f"      Reserve: {reserve}, Charter: {charter}")
            print(f"      Desc: {desc[:80] if desc else 'None'}")
            print(f"      Source: {source}")
            
            if reserve and charter:
                found_count += 1
            else:
                unlinked_count += 1
            break  # Count first match only
    else:
        print(f"  [FAIL] NOT FOUND in charter_refunds")
        missing_count += 1
        
        # Check if it's in description field
        cur.execute("""
            SELECT id, refund_date, amount, reserve_number, charter_id, description
            FROM charter_refunds
            WHERE description ILIKE %s
            ORDER BY refund_date DESC
            LIMIT 2
        """, (f'%{deposit_num}%',))
        desc_matches = cur.fetchall()
        
        if desc_matches:
            print(f"  💡 Found by deposit number in description:")
            for match in desc_matches:
                refund_id, date, amt, reserve, charter, desc = match
                linked = "[OK] LINKED" if reserve and charter else "[FAIL] UNLINKED"
                print(f"    Refund #{refund_id}: ${amt} on {date} - {linked}")
                print(f"      Desc: {desc[:100] if desc else 'None'}")

print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Total LMS refunds checked: {len(LMS_REFUNDS)}")
print(f"Found and linked: {found_count}")
print(f"Found but unlinked: {unlinked_count}")
print(f"Not found: {missing_count}")

# Check specifically for deposit numbers in description
print(f"\n{'='*80}")
print("SEARCH BY LMS DEPOSIT NUMBER")
print(f"{'='*80}")

for deposit_num, refund_date, amount, description in LMS_REFUNDS:
    cur.execute("""
        SELECT COUNT(*) 
        FROM charter_refunds
        WHERE description ILIKE %s OR notes ILIKE %s
    """, (f'%{deposit_num}%', f'%{deposit_num}%'))
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"Deposit {deposit_num}: Found in {count} refund(s)")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("COMPLETE")
print(f"{'='*80}")
