"""
Update receipts table with card data from staging_receipts_raw.

This script:
1. Matches receipts to staging records by vendor, date, and amount
2. Updates card_number, card_type, and pay_method fields
3. Shows detailed statistics and samples before updating
4. Can run in dry-run mode to preview changes
"""

import psycopg2
from datetime import datetime
import sys

# Database connection
conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost",
    port="5432"
)

# Check for --write flag
DRY_RUN = '--write' not in sys.argv

if DRY_RUN:
    print("\n" + "=" * 80)
    print("DRY RUN MODE - NO CHANGES WILL BE MADE")
    print("Run with --write flag to apply changes")
    print("=" * 80 + "\n")
else:
    print("\n" + "=" * 80)
    print("WRITE MODE - CHANGES WILL BE APPLIED")
    print("=" * 80 + "\n")

cur = conn.cursor()

print("=" * 80)
print("RECEIPT CARD DATA UPDATE - FROM STAGING TABLE")
print("=" * 80)

# Step 1: Check current state
print("\n1. CURRENT STATE OF RECEIPTS TABLE")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as banking_receipts,
        COUNT(CASE WHEN created_from_banking IS NULL OR created_from_banking = FALSE THEN 1 END) as non_banking_receipts,
        COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card_number,
        COUNT(CASE WHEN card_type IS NOT NULL AND card_type != '' THEN 1 END) as has_card_type,
        COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay_method
    FROM receipts
""")

row = cur.fetchone()
total, banking, non_banking, has_cn, has_ct, has_pm = row
print(f"Total receipts:              {total:6,}")
print(f"  Banking imports:           {banking:6,}")
print(f"  Non-banking:               {non_banking:6,}")
print(f"  With card_number:          {has_cn:6,} ({100*has_cn/total if total > 0 else 0:5.1f}%)")
print(f"  With card_type:            {has_ct:6,} ({100*has_ct/total if total > 0 else 0:5.1f}%)")
print(f"  With pay_method:           {has_pm:6,} ({100*has_pm/total if total > 0 else 0:5.1f}%)")

# Step 2: Check staging table
print("\n2. STAGING TABLE STATUS")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN raw_payload->'row'->>'Card number' IS NOT NULL 
                    AND raw_payload->'row'->>'Card number' != '' THEN 1 END) as has_card_number,
        COUNT(CASE WHEN raw_payload->'row'->>'Pay method' IS NOT NULL 
                    AND raw_payload->'row'->>'Pay method' != '' THEN 1 END) as has_pay_method
    FROM staging_receipts_raw
""")

row = cur.fetchone()
staging_total, staging_cn, staging_pm = row
print(f"Total staging receipts:      {staging_total:6,}")
print(f"  With card_number:          {staging_cn:6,} ({100*staging_cn/staging_total if staging_total > 0 else 0:5.1f}%)")
print(f"  With pay_method:           {staging_pm:6,} ({100*staging_pm/staging_total if staging_total > 0 else 0:5.1f}%)")

# Step 3: Create matching strategy
print("\n3. MATCHING RECEIPTS TO STAGING DATA")
print("-" * 80)
print("Strategy: Match on vendor_name, receipt_date, and gross_amount")

# First, let's see how many receipts can be matched
cur.execute("""
    WITH staging_data AS (
        SELECT 
            raw_payload->'row'->>'Vendor' as vendor,
            CASE 
                WHEN raw_payload->'row'->>'Date issued' IS NOT NULL 
                     AND raw_payload->'row'->>'Date issued' != ''
                THEN (raw_payload->'row'->>'Date issued')::date
                ELSE NULL
            END as receipt_date,
            CASE 
                WHEN raw_payload->'row'->>'Total' IS NOT NULL 
                     AND raw_payload->'row'->>'Total' != ''
                THEN (raw_payload->'row'->>'Total')::numeric
                ELSE NULL
            END as amount,
            raw_payload->'row'->>'Card number' as card_number,
            raw_payload->'row'->>'Card type' as card_type,
            raw_payload->'row'->>'Pay method' as pay_method,
            id as staging_id
        FROM staging_receipts_raw
        WHERE raw_payload->'row'->>'Vendor' IS NOT NULL
          AND raw_payload->'row'->>'Date issued' IS NOT NULL
          AND raw_payload->'row'->>'Date issued' != ''
    )
    SELECT 
        COUNT(DISTINCT r.id) as matchable_receipts,
        COUNT(DISTINCT s.staging_id) as matched_staging,
        COUNT(DISTINCT CASE WHEN s.card_number IS NOT NULL AND s.card_number != '' 
                            THEN r.id END) as receipts_getting_card_number,
        COUNT(DISTINCT CASE WHEN s.pay_method IS NOT NULL AND s.pay_method != '' 
                            THEN r.id END) as receipts_getting_pay_method
    FROM receipts r
    INNER JOIN staging_data s ON 
        r.vendor_name = s.vendor
        AND r.receipt_date = s.receipt_date
        AND r.gross_amount = s.amount
    WHERE r.created_from_banking IS NULL OR r.created_from_banking = FALSE
""")

row = cur.fetchone()
if row:
    matchable, matched_staging, getting_cn, getting_pm = row
    print(f"\nMatching results:")
    print(f"  Receipts that can be matched:        {matchable:6,}")
    print(f"  Staging records matched:             {matched_staging:6,}")
    print(f"  Receipts getting card_number:        {getting_cn:6,}")
    print(f"  Receipts getting pay_method:         {getting_pm:6,}")

# Step 4: Show sample matches
print("\n4. SAMPLE MATCHES (showing what will be updated)")
print("-" * 80)

cur.execute("""
    WITH staging_data AS (
        SELECT 
            raw_payload->'row'->>'Vendor' as vendor,
            CASE 
                WHEN raw_payload->'row'->>'Date issued' IS NOT NULL 
                     AND raw_payload->'row'->>'Date issued' != ''
                THEN (raw_payload->'row'->>'Date issued')::date
                ELSE NULL
            END as receipt_date,
            CASE 
                WHEN raw_payload->'row'->>'Total' IS NOT NULL 
                     AND raw_payload->'row'->>'Total' != ''
                THEN (raw_payload->'row'->>'Total')::numeric
                ELSE NULL
            END as amount,
            raw_payload->'row'->>'Card number' as card_number,
            raw_payload->'row'->>'Card type' as card_type,
            raw_payload->'row'->>'Pay method' as pay_method,
            id as staging_id
        FROM staging_receipts_raw
        WHERE raw_payload->'row'->>'Vendor' IS NOT NULL
          AND raw_payload->'row'->>'Date issued' IS NOT NULL
          AND raw_payload->'row'->>'Date issued' != ''
    )
    SELECT 
        r.id,
        r.vendor_name,
        r.receipt_date,
        r.gross_amount,
        r.card_number as current_card,
        s.card_number as new_card,
        r.pay_method as current_pay,
        s.pay_method as new_pay
    FROM receipts r
    INNER JOIN staging_data s ON 
        r.vendor_name = s.vendor
        AND r.receipt_date = s.receipt_date
        AND r.gross_amount = s.amount
    WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
      AND (s.card_number IS NOT NULL AND s.card_number != '' 
           OR s.pay_method IS NOT NULL AND s.pay_method != '')
    ORDER BY r.receipt_date DESC
    LIMIT 20
""")

results = cur.fetchall()
if results:
    print(f"{'ID':6} {'Date':12} {'Vendor':25} {'Amount':12} {'Card':6}→{'New':6} {'Pay':10}→{'New':10}")
    print("-" * 95)
    for row in results:
        rid, vendor, date, amount, curr_card, new_card, curr_pay, new_pay = row
        vendor = (vendor or '')[:24]
        curr_card = (curr_card or '')[:5]
        new_card = (new_card or '')[:5]
        curr_pay = (curr_pay or '')[:9]
        new_pay = (new_pay or '')[:9]
        print(f"{rid:6} {str(date):12} {vendor:25} ${amount:10,.2f} {curr_card:6}→{new_card:6} {curr_pay:10}→{new_pay:10}")

# Step 5: Card number distribution from staging
print("\n5. CARD NUMBER DISTRIBUTION (from staging)")
print("-" * 80)

cur.execute("""
    SELECT 
        raw_payload->'row'->>'Card number' as card_number,
        COUNT(*) as count
    FROM staging_receipts_raw
    WHERE raw_payload->'row'->>'Card number' IS NOT NULL
        AND raw_payload->'row'->>'Card number' != ''
    GROUP BY raw_payload->'row'->>'Card number'
    ORDER BY count DESC
    LIMIT 15
""")

results = cur.fetchall()
if results:
    print(f"{'Card Number':15} {'Count':>10} {'Description'}")
    print("-" * 60)
    descriptions = {
        '3265': 'CIBC business debit card (primary)',
        '0853': 'Money Mart location ID',
        '9206': 'Driver card (for reimbursement)',
        '3559': 'Driver card (for reimbursement)',
        '8547': 'Driver card (for reimbursement)'
    }
    for row in results:
        card_num, count = row
        desc = descriptions.get(card_num, 'Driver/other card')
        print(f"{card_num:15} {count:10,} {desc}")

# Step 6: Payment method distribution
print("\n6. PAYMENT METHOD DISTRIBUTION (from staging)")
print("-" * 80)

cur.execute("""
    SELECT 
        raw_payload->'row'->>'Pay method' as pay_method,
        COUNT(*) as count
    FROM staging_receipts_raw
    WHERE raw_payload->'row'->>'Pay method' IS NOT NULL
        AND raw_payload->'row'->>'Pay method' != ''
    GROUP BY raw_payload->'row'->>'Pay method'
    ORDER BY count DESC
""")

results = cur.fetchall()
if results:
    print(f"{'Pay Method':20} {'Count':>10}")
    print("-" * 35)
    for row in results:
        pay_method, count = row
        print(f"{pay_method:20} {count:10,}")

# Step 7: Perform the update (if --write flag is set)
if not DRY_RUN:
    print("\n7. UPDATING RECEIPTS TABLE")
    print("-" * 80)
    
    # Create a temporary mapping table
    cur.execute("""
        CREATE TEMP TABLE receipt_card_updates AS
        WITH staging_data AS (
            SELECT 
                raw_payload->'row'->>'Vendor' as vendor,
                CASE 
                    WHEN raw_payload->'row'->>'Date issued' IS NOT NULL 
                         AND raw_payload->'row'->>'Date issued' != ''
                    THEN (raw_payload->'row'->>'Date issued')::date
                    ELSE NULL
                END as receipt_date,
                CASE 
                    WHEN raw_payload->'row'->>'Total' IS NOT NULL 
                         AND raw_payload->'row'->>'Total' != ''
                    THEN (raw_payload->'row'->>'Total')::numeric
                    ELSE NULL
                END as amount,
                raw_payload->'row'->>'Card number' as card_number,
                raw_payload->'row'->>'Card type' as card_type,
                raw_payload->'row'->>'Pay method' as pay_method
            FROM staging_receipts_raw
            WHERE raw_payload->'row'->>'Vendor' IS NOT NULL
              AND raw_payload->'row'->>'Date issued' IS NOT NULL
              AND raw_payload->'row'->>'Date issued' != ''
        )
        SELECT 
            r.id as receipt_id,
            s.card_number,
            s.card_type,
            s.pay_method
        FROM receipts r
        INNER JOIN staging_data s ON 
            r.vendor_name = s.vendor
            AND r.receipt_date = s.receipt_date
            AND r.gross_amount = s.amount
        WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
    """)
    
    temp_count = cur.rowcount
    print(f"Created temporary mapping table with {temp_count:,} matches")
    
    # Update card_number
    cur.execute("""
        UPDATE receipts r
        SET card_number = u.card_number
        FROM receipt_card_updates u
        WHERE r.id = u.receipt_id
          AND u.card_number IS NOT NULL
          AND u.card_number != ''
    """)
    card_num_updates = cur.rowcount
    print(f"Updated card_number: {card_num_updates:,} receipts")
    
    # Update card_type
    cur.execute("""
        UPDATE receipts r
        SET card_type = u.card_type
        FROM receipt_card_updates u
        WHERE r.id = u.receipt_id
          AND u.card_type IS NOT NULL
          AND u.card_type != ''
    """)
    card_type_updates = cur.rowcount
    print(f"Updated card_type: {card_type_updates:,} receipts")
    
    # Update pay_method
    cur.execute("""
        UPDATE receipts r
        SET pay_method = u.pay_method
        FROM receipt_card_updates u
        WHERE r.id = u.receipt_id
          AND u.pay_method IS NOT NULL
          AND u.pay_method != ''
    """)
    pay_method_updates = cur.rowcount
    print(f"Updated pay_method: {pay_method_updates:,} receipts")
    
    conn.commit()
    print("\n✓ Changes committed to database!")
    
    # Show updated statistics
    print("\n8. UPDATED RECEIPTS TABLE STATUS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card_number,
            COUNT(CASE WHEN card_type IS NOT NULL AND card_type != '' THEN 1 END) as has_card_type,
            COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay_method
        FROM receipts
    """)
    
    row = cur.fetchone()
    total, has_cn, has_ct, has_pm = row
    print(f"Total receipts:              {total:6,}")
    print(f"  With card_number:          {has_cn:6,} ({100*has_cn/total if total > 0 else 0:5.1f}%)")
    print(f"  With card_type:            {has_ct:6,} ({100*has_ct/total if total > 0 else 0:5.1f}%)")
    print(f"  With pay_method:           {has_pm:6,} ({100*has_pm/total if total > 0 else 0:5.1f}%)")
    
else:
    print("\n7. DRY RUN COMPLETE - NO CHANGES MADE")
    print("-" * 80)
    print("Review the sample matches above.")
    print("If everything looks correct, run with --write flag to apply changes:")
    print("  python scripts/update_receipts_with_card_data.py --write")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("COMPLETE!")
print("=" * 80)
