import psycopg2
import json

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)

cur = conn.cursor()

print("=" * 80)
print("RECEIPT STAGING - NESTED JSONB ANALYSIS")
print("=" * 80)

# Get a sample row and check the nested structure
cur.execute("""
    SELECT 
        id,
        source_system,
        raw_payload,
        imported_at
    FROM staging_receipts_raw
    ORDER BY id
    LIMIT 3
""")

for i, row in enumerate(cur.fetchall(), 1):
    rid, source, payload, imported = row
    print(f"\n--- Row {i} (ID: {rid}) ---")
    print(f"Source: {source}")
    print(f"Imported: {imported}")
    if payload:
        print(f"Top-level keys: {list(payload.keys())}")
        if 'row' in payload:
            print(f"Row data keys: {list(payload['row'].keys())}")
            
            # Show card-related fields
            row_data = payload['row']
            card_fields = ['Card number', 'Card type', 'Pay method', 'Vendor', 'Total', 'Date issued']
            print("\nCard/Payment fields:")
            for field in card_fields:
                if field in row_data:
                    print(f"  {field}: {row_data[field]}")

# Now check for card data properly
print("\n" + "=" * 80)
print("CHECKING FOR CARD DATA IN NESTED 'row' JSONB")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN raw_payload->'row' ? 'Card number' THEN 1 END) as has_card_number,
        COUNT(CASE WHEN raw_payload->'row' ? 'Card type' THEN 1 END) as has_card_type,
        COUNT(CASE WHEN raw_payload->'row' ? 'Pay method' THEN 1 END) as has_pay_method,
        COUNT(CASE WHEN raw_payload->'row'->>'Card number' IS NOT NULL 
                    AND raw_payload->'row'->>'Card number' != '' THEN 1 END) as has_card_number_value
    FROM staging_receipts_raw
""")

row = cur.fetchone()
if row:
    total, has_cn, has_ct, has_pm, has_cn_val = row
    print(f"Total rows: {total:,}")
    print(f"\nCard data availability:")
    print(f"  Has 'Card number' field:         {has_cn:6,} ({100*has_cn/total if total > 0 else 0:5.1f}%)")
    print(f"  Has 'Card number' with value:    {has_cn_val:6,} ({100*has_cn_val/total if total > 0 else 0:5.1f}%)")
    print(f"  Has 'Card type' field:           {has_ct:6,} ({100*has_ct/total if total > 0 else 0:5.1f}%)")
    print(f"  Has 'Pay method' field:          {has_pm:6,} ({100*has_pm/total if total > 0 else 0:5.1f}%)")

# Find rows with card number "3265"
print("\n" + "=" * 80)
print("SEARCHING FOR CIBC CARD (3265)")
print("=" * 80)

cur.execute("""
    SELECT 
        id,
        raw_payload->'row'->>'Date issued' as date_issued,
        raw_payload->'row'->>'Vendor' as vendor,
        raw_payload->'row'->>'Total' as total,
        raw_payload->'row'->>'Card number' as card_number,
        raw_payload->'row'->>'Card type' as card_type,
        raw_payload->'row'->>'Pay method' as pay_method,
        raw_payload->'row'->>'Description' as description
    FROM staging_receipts_raw
    WHERE raw_payload->'row'->>'Card number' = '3265'
    ORDER BY raw_payload->'row'->>'Date issued' DESC
    LIMIT 15
""")

results = cur.fetchall()
if results:
    print(f"\nFound {len(results)} receipts with card number '3265' (CIBC debit):")
    print(f"{'ID':6} {'Date':12} {'Vendor':25} {'Amount':12} {'Card#':6} {'Type':10} {'PayMeth':10}")
    print("-" * 95)
    for row in results:
        rid, date, vendor, amount, card_num, card_type, pay_meth, desc = row
        vendor = (vendor or '')[:24]
        card_type = (card_type or '')[:9]
        pay_meth = (pay_meth or '')[:9]
        print(f"{rid:6} {str(date or ''):12} {vendor:25} {amount or '':>12} {card_num or '':6} {card_type or '':10} {pay_meth or '':10}")
else:
    print("\nNo receipts found with card number '3265'")

# Check for cash receipts
print("\n" + "=" * 80)
print("PAYMENT METHOD DISTRIBUTION")
print("=" * 80)

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
        print(f"{pay_method or 'NULL':20} {count:10,}")
else:
    print("No pay_method data found")

# Card number distribution
print("\n" + "=" * 80)
print("CARD NUMBER DISTRIBUTION")
print("=" * 80)

cur.execute("""
    SELECT 
        raw_payload->'row'->>'Card number' as card_number,
        COUNT(*) as count
    FROM staging_receipts_raw
    WHERE raw_payload->'row'->>'Card number' IS NOT NULL
        AND raw_payload->'row'->>'Card number' != ''
    GROUP BY raw_payload->'row'->>'Card number'
    ORDER BY count DESC
    LIMIT 20
""")

results = cur.fetchall()
if results:
    print(f"{'Card Number':15} {'Count':>10}")
    print("-" * 30)
    for row in results:
        card_num, count = row
        print(f"{card_num or 'NULL':15} {count:10,}")
else:
    print("No card_number data found")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("SUCCESS! CARD DATA FOUND IN STAGING TABLE!" if has_cn_val > 0 else "Card data not found in staging")
print("=" * 80)
