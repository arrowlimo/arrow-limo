"""
Analyze unlinked refunds to find reservation numbers in Square transaction descriptions.
Cross-check with items CSV files that contain Square transaction details.
"""
import os
import psycopg2
import pandas as pd
import re
from pathlib import Path

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("ANALYZING UNLINKED REFUNDS FOR RESERVATION NUMBERS IN SQUARE DATA")
print("="*80)

# Get unlinked refunds with Square payment IDs
cur.execute("""
    SELECT id, refund_date, amount, square_payment_id, description, 
           customer, source_file
    FROM charter_refunds
    WHERE (reserve_number IS NULL OR charter_id IS NULL)
      AND square_payment_id IS NOT NULL
    ORDER BY refund_date DESC
""")
unlinked_refunds = cur.fetchall()

print(f"\nFound {len(unlinked_refunds)} unlinked refunds with Square payment IDs")

# Pattern to match reservation numbers
RESERVE_PATTERNS = [
    re.compile(r'\b0(\d{5})\b'),  # 019592, 015400, etc.
    re.compile(r'\bres[:\s]*0?(\d{5})\b', re.IGNORECASE),  # res 19592, res: 015400
    re.compile(r'\breserve[:\s]*0?(\d{5})\b', re.IGNORECASE),  # reserve 19592
    re.compile(r'\b(\d{6})\b'),  # 019592 as 6-digit
]

def extract_reserve_numbers(text):
    """Extract potential reservation numbers from text"""
    if not text:
        return []
    reserves = []
    for pattern in RESERVE_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            # Normalize to 6-digit format
            reserve = match.zfill(6)
            if reserve not in reserves:
                reserves.append(reserve)
    return reserves

# Look for Square items CSV files
items_dir = Path('L:/limo/Square reports')
items_files = list(items_dir.glob('items-*.csv'))
print(f"\nFound {len(items_files)} Square items CSV files to check")

# Also check qb_storage/exports_verified
qb_dir = Path('L:/limo/qb_storage/exports_verified')
if qb_dir.exists():
    qb_files = list(qb_dir.glob('items-*.csv'))
    items_files.extend(qb_files)
    print(f"  + {len(qb_files)} from qb_storage/exports_verified")

# Load all items CSVs into memory for faster lookup
print("\nLoading Square transaction data...")
square_data = {}
for csv_file in items_files:
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig')
        print(f"  Loaded {csv_file.name}: {len(df)} rows")
        
        # Index by various ID columns
        for _, row in df.iterrows():
            # Try different possible column names
            payment_id = None
            for col in ['Payment ID', 'Transaction ID', 'payment_id', 'transaction_id']:
                if col in df.columns and pd.notna(row.get(col)):
                    payment_id = str(row[col])
                    break
            
            if payment_id:
                square_data[payment_id] = {
                    'file': csv_file.name,
                    'row': row.to_dict()
                }
    except Exception as e:
        print(f"  [WARN] Error loading {csv_file.name}: {e}")

print(f"\nIndexed {len(square_data)} Square transactions")

# Analyze each unlinked refund
print(f"\n{'='*80}")
print("DETAILED ANALYSIS OF UNLINKED REFUNDS")
print(f"{'='*80}")

found_reserves = []
not_found = []

for refund in unlinked_refunds[:30]:  # Analyze first 30
    refund_id, refund_date, amount, square_id, description, customer, source_file = refund
    
    print(f"\n{'*'*60}")
    print(f"Refund #{refund_id}: ${amount} on {refund_date}")
    print(f"  Square ID: {square_id}")
    print(f"  Current Desc: {description[:100] if description else 'None'}")
    
    # Check if Square ID is in our loaded data
    square_info = square_data.get(square_id)
    
    if square_info:
        print(f"  [OK] Found in Square data: {square_info['file']}")
        row = square_info['row']
        
        # Look for reservation numbers in various fields
        search_fields = ['Details', 'Notes', 'Description', 'Item', 'details', 'notes', 'description']
        found_in_square = []
        
        for field in search_fields:
            if field in row and pd.notna(row[field]):
                field_text = str(row[field])
                reserves = extract_reserve_numbers(field_text)
                if reserves:
                    found_in_square.extend(reserves)
                    print(f"  🎯 Found in {field}: {field_text[:100]}")
                    print(f"     Extracted reserves: {', '.join(reserves)}")
        
        if found_in_square:
            # Verify these reserves exist in charters
            for reserve in set(found_in_square):
                cur.execute("""
                    SELECT charter_id, reserve_number, charter_date, status
                    FROM charters
                    WHERE reserve_number = %s
                """, (reserve,))
                charter = cur.fetchone()
                
                if charter:
                    print(f"  [OK] VERIFIED: Reserve {reserve} → Charter {charter[0]} (Date: {charter[2]})")
                    found_reserves.append({
                        'refund_id': refund_id,
                        'amount': amount,
                        'square_id': square_id,
                        'reserve': reserve,
                        'charter_id': charter[0],
                        'charter_date': charter[2]
                    })
                else:
                    print(f"  [WARN] Reserve {reserve} NOT FOUND in charters")
        else:
            print(f"  ℹ️ No reservation numbers found in Square transaction data")
            not_found.append(refund_id)
    else:
        print(f"  [WARN] Square ID not found in loaded CSV files")
        not_found.append(refund_id)

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")

print(f"\n📊 Analysis Results:")
print(f"  Total Unlinked Refunds Analyzed: {min(30, len(unlinked_refunds))}")
print(f"  Found Reservation Numbers: {len(found_reserves)}")
print(f"  No Reservation Found: {len(not_found)}")

if found_reserves:
    print(f"\n[OK] REFUNDS WITH RESERVATION NUMBERS FOUND:")
    for item in found_reserves:
        print(f"  Refund #{item['refund_id']}: ${item['amount']} → Reserve {item['reserve']}, Charter {item['charter_id']}")

if found_reserves:
    print(f"\n💡 RECOMMENDATION:")
    print(f"  Create a script to automatically link these {len(found_reserves)} refunds")
    print(f"  Use Square transaction data to extract reservation numbers")
    print(f"  This will improve linkage rate from 50.2% to approximately {(207 + len(found_reserves))/412*100:.1f}%")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("ANALYSIS COMPLETE")
print(f"{'='*80}")
