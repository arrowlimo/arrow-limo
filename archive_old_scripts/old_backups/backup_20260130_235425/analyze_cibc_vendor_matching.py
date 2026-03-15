"""
Analyze CIBC receipts to find real vendor names and match to truncated banking descriptions.
"""
import psycopg2
from collections import defaultdict
import re

def normalize_for_matching(text):
    """Normalize text for fuzzy matching."""
    if not text:
        return ""
    text = text.upper()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # First, check what years CIBC was active
    print("=" * 80)
    print("CIBC ACCOUNT ACTIVITY BY YEAR")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year, 
            COUNT(*) as count
        FROM banking_transactions 
        WHERE account_number = '0228362'
        GROUP BY year 
        ORDER BY year
    """)
    
    years = []
    for row in cur.fetchall():
        year = int(row[0])
        count = row[1]
        years.append(year)
        print(f"{year}: {count:5d} transactions")
    
    if not years:
        print("No CIBC transactions found!")
        return
    
    min_year = min(years)
    max_year = max(years)
    
    # Get receipts from CIBC years
    print(f"\n{'=' * 80}")
    print(f"TOP {min_year}-{max_year} RECEIPT VENDORS")
    print("=" * 80)
    
    cur.execute(f"""
        SELECT DISTINCT vendor_name, COUNT(*) as count 
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN {min_year} AND {max_year}
        AND vendor_name IS NOT NULL 
        AND vendor_name != '' 
        AND vendor_name != 'Unknown Vendor'
        GROUP BY vendor_name
        ORDER BY count DESC 
        LIMIT 100
    """)
    
    receipt_vendors = []
    for row in cur.fetchall():
        vendor = row[0]
        count = row[1]
        receipt_vendors.append((vendor, count))
        print(f"{count:4d} × {vendor}")
    
    print(f"\n{'=' * 80}")
    print(f"TOP {min_year}-{max_year} CIBC DESCRIPTIONS (Debits)")
    print("=" * 80)
    
    # Get CIBC descriptions
    cur.execute(f"""
        SELECT DISTINCT description, COUNT(*) as count 
        FROM banking_transactions 
        WHERE account_number = '0228362' 
        AND EXTRACT(YEAR FROM transaction_date) BETWEEN {min_year} AND {max_year}
        AND debit_amount > 0 
        AND description NOT LIKE 'DEPOSIT%' 
        AND description NOT LIKE 'CREDIT MEMO%'
        GROUP BY description
        ORDER BY count DESC 
        LIMIT 150
    """)
    
    scotia_descriptions = []
    for row in cur.fetchall():
        desc = row[0]
        count = row[1]
        scotia_descriptions.append((desc, count))
        print(f"{count:4d} × {desc}")
    
    # Find potential matches
    print(f"\n{'=' * 80}")
    print("POTENTIAL VENDOR MATCHES")
    print("=" * 80)
    
    matches = []
    for desc, desc_count in scotia_descriptions:
        desc_norm = normalize_for_matching(desc)
        
        for vendor, vendor_count in receipt_vendors:
            vendor_norm = normalize_for_matching(vendor)
            
            # Check if vendor name appears in description
            if vendor_norm in desc_norm or desc_norm in vendor_norm:
                desc_words = set(desc_norm.split())
                vendor_words = set(vendor_norm.split())
                overlap = desc_words & vendor_words
                
                if len(overlap) > 0:
                    matches.append({
                        'cibc_desc': desc,
                        'cibc_count': desc_count,
                        'receipt_vendor': vendor,
                        'receipt_count': vendor_count,
                        'overlap': len(overlap),
                        'confidence': 'HIGH' if len(overlap) >= 2 else 'MEDIUM'
                    })
    
    # Sort by overlap (best matches first)
    matches.sort(key=lambda x: (-x['overlap'], -x['cibc_count']))
    
    for match in matches[:100]:  # Show top 100 matches
        print(f"\n{match['confidence']} MATCH ({match['overlap']} words overlap):")
        print(f"  CIBC: {match['cibc_desc']} ({match['cibc_count']} transactions)")
        print(f"  Receipt: {match['receipt_vendor']} ({match['receipt_count']} receipts)")
    
    if not matches:
        print("No automatic matches found.")
    
    # Show unmatched CIBC descriptions
    matched_descs = {m['cibc_desc'] for m in matches}
    unmatched = [d for d, c in scotia_descriptions if d not in matched_descs]
    
    if unmatched:
        print(f"\n{'=' * 80}")
        print(f"UNMATCHED CIBC DESCRIPTIONS ({len(unmatched)} total)")
        print("=" * 80)
        for desc in unmatched[:50]:
            print(f"  {desc}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
