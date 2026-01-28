"""
Improved receipt card data update with fuzzy matching.

This script uses multiple matching strategies:
1. Exact match (vendor, date, amount)
2. Fuzzy vendor match (handles spelling variations)
3. Amount tolerance (handles rounding differences)
4. Date proximity (handles date entry errors)
"""

import psycopg2
from datetime import datetime, timedelta
import sys

# Database connection
conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
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
print("IMPROVED RECEIPT CARD DATA UPDATE - FUZZY MATCHING")
print("=" * 80)

# Step 1: Current state
print("\n1. CURRENT STATE")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN created_from_banking IS NULL OR created_from_banking = FALSE THEN 1 END) as non_banking,
        COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card,
        COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay_method
    FROM receipts
""")

row = cur.fetchone()
total, non_banking, has_card, has_pay = row
print(f"Total receipts:              {total:6,}")
print(f"  Non-banking:               {non_banking:6,}")
print(f"  With card_number:          {has_card:6,}")
print(f"  With pay_method:           {has_pay:6,}")
print(f"  Still need card data:      {non_banking - has_card:6,}")

# Step 2: Staging table status
print("\n2. STAGING TABLE DATA AVAILABLE")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN raw_payload->'row'->>'Card number' IS NOT NULL 
                    AND raw_payload->'row'->>'Card number' != '' THEN 1 END) as has_card,
        COUNT(CASE WHEN raw_payload->'row'->>'Pay method' IS NOT NULL 
                    AND raw_payload->'row'->>'Pay method' != '' THEN 1 END) as has_pay_method
    FROM staging_receipts_raw
""")

row = cur.fetchone()
staging_total, staging_card, staging_pay = row
print(f"Total staging receipts:      {staging_total:6,}")
print(f"  With card_number:          {staging_card:6,}")
print(f"  With pay_method:           {staging_pay:6,}")

# Step 3: Create normalized vendor names for better matching
print("\n3. MATCHING STRATEGIES")
print("-" * 80)
print("Strategy 1: Exact match (vendor, date, amount)")
print("Strategy 2: Normalized vendor + exact date + exact amount")
print("Strategy 3: Normalized vendor + exact date + amount ±$0.50")
print("Strategy 4: Normalized vendor + date ±1 day + amount ±$0.50")

# Create a function to normalize vendor names
cur.execute("""
    CREATE OR REPLACE FUNCTION normalize_vendor(vendor TEXT) RETURNS TEXT AS $$
    BEGIN
        RETURN UPPER(TRIM(
            REGEXP_REPLACE(
                REGEXP_REPLACE(vendor, '[^A-Za-z0-9 ]', '', 'g'),
                '\s+', ' ', 'g'
            )
        ));
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
""")

# Strategy 1: Exact match
print("\nStrategy 1: Exact matching...")
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
    SELECT COUNT(DISTINCT r.id) as exact_matches
    FROM receipts r
    INNER JOIN staging_data s ON 
        r.vendor_name = s.vendor
        AND r.receipt_date = s.receipt_date
        AND r.gross_amount = s.amount
    WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
      AND (r.card_number IS NULL OR r.card_number = '')
""")
exact_matches = cur.fetchone()[0]
print(f"  Exact matches found: {exact_matches:6,}")

# Strategy 2: Normalized vendor match
print("\nStrategy 2: Normalized vendor matching...")
cur.execute("""
    WITH staging_data AS (
        SELECT 
            normalize_vendor(raw_payload->'row'->>'Vendor') as vendor_norm,
            raw_payload->'row'->>'Vendor' as vendor_orig,
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
    SELECT COUNT(DISTINCT r.id) as norm_matches
    FROM receipts r
    INNER JOIN staging_data s ON 
        normalize_vendor(r.vendor_name) = s.vendor_norm
        AND r.receipt_date = s.receipt_date
        AND r.gross_amount = s.amount
    WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
      AND (r.card_number IS NULL OR r.card_number = '')
""")
norm_matches = cur.fetchone()[0]
print(f"  Normalized vendor matches: {norm_matches:6,}")

# Strategy 3: Amount tolerance
print("\nStrategy 3: Amount tolerance (±$0.50)...")
cur.execute("""
    WITH staging_data AS (
        SELECT 
            normalize_vendor(raw_payload->'row'->>'Vendor') as vendor_norm,
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
    SELECT COUNT(DISTINCT r.id) as tolerance_matches
    FROM receipts r
    INNER JOIN staging_data s ON 
        normalize_vendor(r.vendor_name) = s.vendor_norm
        AND r.receipt_date = s.receipt_date
        AND ABS(r.gross_amount - s.amount) <= 0.50
    WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
      AND (r.card_number IS NULL OR r.card_number = '')
""")
tolerance_matches = cur.fetchone()[0]
print(f"  Amount tolerance matches: {tolerance_matches:6,}")

# Strategy 4: Date proximity
print("\nStrategy 4: Date proximity (±1 day) + amount tolerance...")
cur.execute("""
    WITH staging_data AS (
        SELECT 
            normalize_vendor(raw_payload->'row'->>'Vendor') as vendor_norm,
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
    SELECT COUNT(DISTINCT r.id) as proximity_matches
    FROM receipts r
    INNER JOIN staging_data s ON 
        normalize_vendor(r.vendor_name) = s.vendor_norm
        AND ABS(r.receipt_date - s.receipt_date) <= 1
        AND ABS(r.gross_amount - s.amount) <= 0.50
    WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
      AND (r.card_number IS NULL OR r.card_number = '')
""")
proximity_matches = cur.fetchone()[0]
print(f"  Date proximity matches: {proximity_matches:6,}")

# Step 4: Show sample matches from best strategy
print("\n4. SAMPLE MATCHES (using best strategy)")
print("-" * 80)

cur.execute("""
    WITH staging_data AS (
        SELECT 
            normalize_vendor(raw_payload->'row'->>'Vendor') as vendor_norm,
            raw_payload->'row'->>'Vendor' as vendor_orig,
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
        r.vendor_name as db_vendor,
        s.vendor_orig as csv_vendor,
        r.receipt_date,
        r.gross_amount,
        s.amount as csv_amount,
        r.card_number as current_card,
        s.card_number as new_card,
        r.pay_method as current_pay,
        s.pay_method as new_pay,
        CASE 
            WHEN r.vendor_name = s.vendor_orig 
                 AND r.receipt_date = s.receipt_date 
                 AND r.gross_amount = s.amount THEN 'Exact'
            WHEN normalize_vendor(r.vendor_name) = s.vendor_norm 
                 AND r.receipt_date = s.receipt_date 
                 AND r.gross_amount = s.amount THEN 'Normalized'
            WHEN normalize_vendor(r.vendor_name) = s.vendor_norm 
                 AND r.receipt_date = s.receipt_date 
                 AND ABS(r.gross_amount - s.amount) <= 0.50 THEN 'Amount±0.50'
            WHEN normalize_vendor(r.vendor_name) = s.vendor_norm 
                 AND ABS(r.receipt_date - s.receipt_date) <= 1
                 AND ABS(r.gross_amount - s.amount) <= 0.50 THEN 'Date±1+Amt±0.50'
            ELSE 'Other'
        END as match_type
    FROM receipts r
    INNER JOIN staging_data s ON 
        normalize_vendor(r.vendor_name) = s.vendor_norm
        AND ABS(r.receipt_date - s.receipt_date) <= 1
        AND ABS(r.gross_amount - s.amount) <= 0.50
    WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
      AND (r.card_number IS NULL OR r.card_number = '')
      AND (s.card_number IS NOT NULL AND s.card_number != '' 
           OR s.pay_method IS NOT NULL AND s.pay_method != '')
    ORDER BY match_type, r.receipt_date DESC
    LIMIT 25
""")

results = cur.fetchall()
if results:
    print(f"{'ID':6} {'Date':12} {'DB Vendor':25} {'Amount':12} {'Card':6}→{'New':6} {'Pay':8}→{'New':8} {'Match':12}")
    print("-" * 115)
    for row in results:
        rid, db_vendor, csv_vendor, date, db_amt, csv_amt, curr_card, new_card, curr_pay, new_pay, match_type = row
        db_vendor = (db_vendor or '')[:24]
        curr_card = (curr_card or '')[:5]
        new_card = (new_card or '')[:5]
        curr_pay = (curr_pay or '')[:7]
        new_pay = (new_pay or '')[:7]
        print(f"{rid:6} {str(date):12} {db_vendor:25} ${db_amt:10,.2f} {curr_card:6}→{new_card:6} {curr_pay:8}→{new_pay:8} {match_type:12}")

# Step 5: Perform update if --write
if not DRY_RUN:
    print("\n5. APPLYING UPDATES")
    print("-" * 80)
    
    # Create temp table with all matches using fuzzy logic
    cur.execute("""
        CREATE TEMP TABLE receipt_card_updates_fuzzy AS
        WITH staging_data AS (
            SELECT 
                normalize_vendor(raw_payload->'row'->>'Vendor') as vendor_norm,
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
        SELECT DISTINCT ON (r.id)
            r.id as receipt_id,
            s.card_number,
            s.card_type,
            s.pay_method,
            CASE 
                WHEN r.vendor_name = s.vendor_norm 
                     AND r.receipt_date = s.receipt_date 
                     AND r.gross_amount = s.amount THEN 1
                WHEN normalize_vendor(r.vendor_name) = s.vendor_norm 
                     AND r.receipt_date = s.receipt_date 
                     AND r.gross_amount = s.amount THEN 2
                WHEN normalize_vendor(r.vendor_name) = s.vendor_norm 
                     AND r.receipt_date = s.receipt_date 
                     AND ABS(r.gross_amount - s.amount) <= 0.50 THEN 3
                ELSE 4
            END as match_quality
        FROM receipts r
        INNER JOIN staging_data s ON 
            normalize_vendor(r.vendor_name) = s.vendor_norm
            AND ABS(r.receipt_date - s.receipt_date) <= 1
            AND ABS(r.gross_amount - s.amount) <= 0.50
        WHERE (r.created_from_banking IS NULL OR r.created_from_banking = FALSE)
          AND (r.card_number IS NULL OR r.card_number = '')
        ORDER BY r.id, match_quality
    """)
    
    temp_count = cur.rowcount
    print(f"Created temporary mapping with {temp_count:,} matches")
    
    # Update card_number
    cur.execute("""
        UPDATE receipts r
        SET card_number = u.card_number
        FROM receipt_card_updates_fuzzy u
        WHERE r.id = u.receipt_id
          AND u.card_number IS NOT NULL
          AND u.card_number != ''
    """)
    card_updates = cur.rowcount
    print(f"Updated card_number: {card_updates:,} receipts")
    
    # Update card_type
    cur.execute("""
        UPDATE receipts r
        SET card_type = u.card_type
        FROM receipt_card_updates_fuzzy u
        WHERE r.id = u.receipt_id
          AND u.card_type IS NOT NULL
          AND u.card_type != ''
    """)
    type_updates = cur.rowcount
    print(f"Updated card_type: {type_updates:,} receipts")
    
    # Update pay_method
    cur.execute("""
        UPDATE receipts r
        SET pay_method = u.pay_method
        FROM receipt_card_updates_fuzzy u
        WHERE r.id = u.receipt_id
          AND u.pay_method IS NOT NULL
          AND u.pay_method != ''
    """)
    pay_updates = cur.rowcount
    print(f"Updated pay_method: {pay_updates:,} receipts")
    
    conn.commit()
    print("\n✓ Changes committed!")
    
    # Show final stats
    print("\n6. FINAL STATUS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card,
            COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay
        FROM receipts
    """)
    
    row = cur.fetchone()
    total, has_card, has_pay = row
    print(f"Total receipts:              {total:6,}")
    print(f"  With card_number:          {has_card:6,} ({100*has_card/total if total > 0 else 0:5.1f}%)")
    print(f"  With pay_method:           {has_pay:6,} ({100*has_pay/total if total > 0 else 0:5.1f}%)")
    
else:
    print("\n5. DRY RUN COMPLETE - NO CHANGES MADE")
    print("-" * 80)
    print("Based on the strategies above:")
    print(f"  Could match up to {proximity_matches:,} more receipts")
    print("\nRun with --write to apply fuzzy matching updates")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("COMPLETE!")
print("=" * 80)
