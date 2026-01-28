"""
Find all 2019 receipts with "CLIENT" in description
Show what GL codes were used for client-related expenses
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def analyze_2019_client_receipts():
    """Find all 2019 receipts with CLIENT in description"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("2019 RECEIPTS WITH 'CLIENT' IN DESCRIPTION")
    print("=" * 100)
    
    # Find all receipts with "client" in description
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            gl_account_code,
            gl_account_name,
            description
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
          AND description ~* 'client'
        ORDER BY description, receipt_date
    """)
    
    receipts = cur.fetchall()
    print(f"\n📊 Found {len(receipts)} receipts with 'CLIENT' in description\n")
    
    # Group by description pattern
    from collections import defaultdict
    by_desc = defaultdict(list)
    
    for rid, date, vendor, amount, code, name, desc in receipts:
        # Extract key phrase from description
        desc_lower = (desc or '').lower()
        key = None
        
        if 'client food' in desc_lower:
            key = 'CLIENT FOOD'
        elif 'client bev' in desc_lower or 'client drink' in desc_lower:
            key = 'CLIENT BEVERAGE'
        elif 'client amenity' in desc_lower or 'client amenities' in desc_lower:
            key = 'CLIENT AMENITIES'
        elif 'client water' in desc_lower:
            key = 'CLIENT WATER'
        elif 'client coffee' in desc_lower:
            key = 'CLIENT COFFEE'
        elif 'client entertain' in desc_lower:
            key = 'CLIENT ENTERTAINMENT'
        elif 'client gift' in desc_lower:
            key = 'CLIENT GIFTS'
        elif 'client supp' in desc_lower:
            key = 'CLIENT SUPPLIES'
        else:
            key = 'CLIENT (OTHER)'
        
        by_desc[key].append((rid, date, vendor, amount, code, name, desc))
    
    # Show grouped results
    for category in sorted(by_desc.keys()):
        items = by_desc[category]
        total = sum(item[3] for item in items)
        
        print("=" * 100)
        print(f"📦 {category} ({len(items)} receipts, ${total:,.2f} total)")
        print("=" * 100)
        
        # Show GL codes used
        gl_usage = defaultdict(lambda: {'count': 0, 'total': 0})
        for item in items:
            code = item[4] or 'NULL'
            gl_usage[code]['count'] += 1
            gl_usage[code]['total'] += item[3]
        
        print("\nGL Codes Used:")
        for code in sorted(gl_usage.keys()):
            count = gl_usage[code]['count']
            total = gl_usage[code]['total']
            name = next((item[5] for item in items if (item[4] or 'NULL') == code), 'No Name')
            print(f"   {code} — {name}: {count} times, ${total:,.2f}")
        
        print("\nSample Receipts:")
        for rid, date, vendor, amount, code, name, desc in items[:10]:
            print(f"   #{rid} | {date} | {vendor[:30]:30s} | ${amount:>8,.2f} | {code or 'NULL'}")
            print(f"      Description: {(desc or '')[:90]}")
        
        if len(items) > 10:
            print(f"   ... and {len(items) - 10} more")
        print()
    
    # Summary recommendations
    print("=" * 100)
    print("💡 RECOMMENDATIONS")
    print("=" * 100)
    
    recommendations = {
        'CLIENT FOOD': '5116 (Client Amenities - Food, Coffee, Supplies)',
        'CLIENT COFFEE': '5116 (Client Amenities - Food, Coffee, Supplies)',
        'CLIENT AMENITIES': '5116 (Client Amenities - Food, Coffee, Supplies)',
        'CLIENT WATER': '4115 (Client Beverage Service Charges)',
        'CLIENT BEVERAGE': '4115 (Client Beverage Service Charges)',
        'CLIENT ENTERTAINMENT': '5700 (Travel and Entertainment) or 5116',
        'CLIENT GIFTS': '5930 (Miscellaneous) or create new code',
        'CLIENT SUPPLIES': '5116 (Client Amenities - Food, Coffee, Supplies)',
    }
    
    for category, gl_code in recommendations.items():
        if category in by_desc:
            count = len(by_desc[category])
            total = sum(item[3] for item in by_desc[category])
            print(f"\n{category} ({count} receipts, ${total:,.2f}):")
            print(f"   → Recommend: {gl_code}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    analyze_2019_client_receipts()
