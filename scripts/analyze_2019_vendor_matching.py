"""
Analyze 2012-2014 receipts to find real vendor names and match to truncated Scotia descriptions.
"""
import psycopg2
from collections import defaultdict
import re

def normalize_for_matching(text):
    """Normalize text for fuzzy matching."""
    if not text:
        return ""
    # Convert to uppercase, remove special chars, collapse whitespace
    text = text.upper()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get 2012-2014 receipt vendors (Scotia was only active 2012-2014)
    print("=" * 80)
    print("TOP 2012-2014 RECEIPT VENDORS")
    print("=" * 80)
    
    cur.execute("""
        SELECT DISTINCT vendor_name, COUNT(*) as count 
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2014 
        AND vendor_name IS NOT NULL 
        AND vendor_name != '' 
        AND vendor_name != 'Unknown Vendor'
        GROUP BY vendor_name
        ORDER BY count DESC 
        LIMIT 50
    """)
    
    receipt_vendors = []
    for row in cur.fetchall():
        vendor = row[0]
        count = row[1]
        receipt_vendors.append((vendor, count))
        print(f"{count:4d} × {vendor}")
    
    print("\n" + "=" * 80)
    print("TOP 2012-2014 SCOTIA DESCRIPTIONS (Debits)")
    print("=" * 80)
    
    # Get 2012-2014 Scotia descriptions
    cur.execute("""
        SELECT DISTINCT description, COUNT(*) as count 
        FROM banking_transactions 
        WHERE account_number = '903990106011' 
        AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014 
        AND debit_amount > 0 
        AND description NOT LIKE 'DEPOSIT%' 
        AND description NOT LIKE 'CREDIT MEMO%'
        GROUP BY description
        ORDER BY count DESC 
        LIMIT 100
    """)
    
    scotia_descriptions = []
    for row in cur.fetchall():
        desc = row[0]
        count = row[1]
        scotia_descriptions.append((desc, count))
        print(f"{count:4d} × {desc}")
    
    # Find potential matches
    print("\n" + "=" * 80)
    print("POTENTIAL VENDOR MATCHES")
    print("=" * 80)
    
    matches = []
    for desc, desc_count in scotia_descriptions:
        desc_norm = normalize_for_matching(desc)
        
        for vendor, vendor_count in receipt_vendors:
            vendor_norm = normalize_for_matching(vendor)
            
            # Check if vendor name appears in description
            if vendor_norm in desc_norm or desc_norm in vendor_norm:
                # Calculate word overlap
                desc_words = set(desc_norm.split())
                vendor_words = set(vendor_norm.split())
                overlap = desc_words & vendor_words
                
                if len(overlap) > 0:
                    matches.append({
                        'scotia_desc': desc,
                        'scotia_count': desc_count,
                        'receipt_vendor': vendor,
                        'receipt_count': vendor_count,
                        'overlap': len(overlap),
                        'confidence': 'HIGH' if len(overlap) >= 2 else 'MEDIUM'
                    })
    
    # Sort by overlap (best matches first)
    matches.sort(key=lambda x: (-x['overlap'], -x['scotia_count']))
    
    for match in matches:
        print(f"\n{match['confidence']} MATCH ({match['overlap']} words overlap):")
        print(f"  Scotia: {match['scotia_desc']} ({match['scotia_count']} transactions)")
        print(f"  Receipt: {match['receipt_vendor']} ({match['receipt_count']} receipts)")
    
    if not matches:
        print("No automatic matches found. Manual review needed.")
    
    # Show unmatched Scotia descriptions
    matched_descs = {m['scotia_desc'] for m in matches}
    unmatched = [d for d, c in scotia_descriptions if d not in matched_descs]
    
    if unmatched:
        print("\n" + "=" * 80)
        print(f"UNMATCHED SCOTIA DESCRIPTIONS ({len(unmatched)} total)")
        print("=" * 80)
        for desc in unmatched[:30]:
            print(f"  {desc}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
