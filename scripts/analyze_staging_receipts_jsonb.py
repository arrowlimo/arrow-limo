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
print("RECEIPT STAGING - JSONB RAW PAYLOAD ANALYSIS")
print("=" * 80)

# Get count
cur.execute("SELECT COUNT(*) FROM staging_receipts_raw")
count = cur.fetchone()[0]
print(f"\nTotal rows in staging_receipts_raw: {count:,}")

# Sample a few rows to see structure
print("\n" + "=" * 80)
print("SAMPLE RAW PAYLOAD STRUCTURES")
print("=" * 80)

cur.execute("""
    SELECT 
        id,
        source_system,
        raw_payload,
        imported_at
    FROM staging_receipts_raw
    ORDER BY id
    LIMIT 5
""")

for i, row in enumerate(cur.fetchall(), 1):
    rid, source, payload, imported = row
    print(f"\n--- Row {i} (ID: {rid}) ---")
    print(f"Source: {source}")
    print(f"Imported: {imported}")
    if payload:
        # Pretty print the JSON
        print("Payload keys:", list(payload.keys()))
        
        # Check for card-related fields
        card_fields = ['card_number', 'card_type', 'Card number', 'Card type', 'pay_method', 'Pay method']
        found_fields = {k: v for k, v in payload.items() if any(cf.lower() in k.lower() for cf in card_fields)}
        if found_fields:
            print("CARD FIELDS FOUND:", found_fields)
        
        # Show a few key fields
        sample_fields = ['vendor_name', 'Vendor', 'gross_amount', 'Total', 'receipt_date', 'Date issued', 
                        'card_number', 'Card number', 'card_type', 'Card type', 'pay_method', 'Pay method']
        print("\nSample data:")
        for field in sample_fields:
            if field in payload:
                print(f"  {field}: {payload[field]}")

# Check for card data across all rows
print("\n" + "=" * 80)
print("CHECKING FOR CARD DATA IN ALL ROWS")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN raw_payload ? 'card_number' THEN 1 END) as has_card_number_lower,
        COUNT(CASE WHEN raw_payload ? 'Card number' THEN 1 END) as has_card_number_title,
        COUNT(CASE WHEN raw_payload ? 'card_type' THEN 1 END) as has_card_type_lower,
        COUNT(CASE WHEN raw_payload ? 'Card type' THEN 1 END) as has_card_type_title,
        COUNT(CASE WHEN raw_payload ? 'pay_method' THEN 1 END) as has_pay_method_lower,
        COUNT(CASE WHEN raw_payload ? 'Pay method' THEN 1 END) as has_pay_method_title
    FROM staging_receipts_raw
""")

row = cur.fetchone()
if row:
    total, cn_lower, cn_title, ct_lower, ct_title, pm_lower, pm_title = row
    print(f"Total rows: {total:,}")
    print(f"\nCard data availability:")
    print(f"  'card_number':  {cn_lower:6,} ({100*cn_lower/total if total > 0 else 0:5.1f}%)")
    print(f"  'Card number':  {cn_title:6,} ({100*cn_title/total if total > 0 else 0:5.1f}%)")
    print(f"  'card_type':    {ct_lower:6,} ({100*ct_lower/total if total > 0 else 0:5.1f}%)")
    print(f"  'Card type':    {ct_title:6,} ({100*ct_title/total if total > 0 else 0:5.1f}%)")
    print(f"  'pay_method':   {pm_lower:6,} ({100*pm_lower/total if total > 0 else 0:5.1f}%)")
    print(f"  'Pay method':   {pm_title:6,} ({100*pm_title/total if total > 0 else 0:5.1f}%)")

# Find rows with card number "3265"
print("\n" + "=" * 80)
print("SEARCHING FOR CIBC CARD (3265)")
print("=" * 80)

cur.execute("""
    SELECT 
        id,
        raw_payload->>'Date issued' as date_issued,
        raw_payload->>'Vendor' as vendor,
        raw_payload->>'Total' as total,
        raw_payload->>'Card number' as card_number,
        raw_payload->>'Card type' as card_type,
        raw_payload->>'Pay method' as pay_method
    FROM staging_receipts_raw
    WHERE raw_payload->>'Card number' = '3265'
    LIMIT 10
""")

results = cur.fetchall()
if results:
    print(f"\nFound {len(results)} receipts with card number '3265':")
    print(f"{'ID':6} {'Date':12} {'Vendor':25} {'Amount':12} {'Card#':6} {'Type':10} {'PayMethod':10}")
    print("-" * 95)
    for row in results:
        rid, date, vendor, amount, card_num, card_type, pay_meth = row
        vendor = (vendor or '')[:24]
        card_type = (card_type or '')[:9]
        pay_meth = (pay_meth or '')[:9]
        print(f"{rid:6} {str(date):12} {vendor:25} {amount:>12} {card_num or '':6} {card_type or '':10} {pay_meth or '':10}")
else:
    print("\nNo receipts found with card number '3265'")

# Check for cash receipts
cur.execute("""
    SELECT COUNT(*)
    FROM staging_receipts_raw
    WHERE raw_payload->>'Pay method' = 'Cash'
""")
cash_count = cur.fetchone()[0]
print(f"\nReceipts with 'Pay method' = 'Cash': {cash_count:,}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("STAGING TABLE CARD DATA: FOUND!" if cn_title > 0 or cn_lower > 0 else "STAGING TABLE CARD DATA: NOT FOUND")
print("=" * 80)
