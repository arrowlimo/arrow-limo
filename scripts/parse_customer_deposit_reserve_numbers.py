#!/usr/bin/env python3
"""
Parse reserve numbers from CUSTOMER DEPOSITS descriptions and link to charters.
CUSTOMER DEPOSITS descriptions contain reserve numbers, e-transfer references, or customer names.
"""
import os
import re
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def extract_reserve_number(description):
    """
    Extract reserve number from description.
    Patterns:
    - 6-digit numbers starting with 0
    - E-TRANSFER reference numbers (ignore these)
    - Customer names (can't extract reserve from these)
    """
    if not description:
        return None
    
    # Skip e-transfer references (9-12 digit numbers)
    if re.search(r'\b\d{9,12}\b', description):
        return None
    
    # Look for 6-digit reserve numbers (format: 0XXXXX)
    match = re.search(r'\b(0\d{5})\b', description)
    if match:
        return match.group(1)
    
    return None

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get unlinked CUSTOMER DEPOSITS
    print("Analyzing unlinked CUSTOMER DEPOSITS...")
    cur.execute("""
        SELECT receipt_id, receipt_date, revenue, description
        FROM receipts
        WHERE revenue > 0
        AND vendor_name ILIKE '%customer%deposit%'
        AND reserve_number IS NULL
        AND charter_id IS NULL
        ORDER BY receipt_date DESC
    """)
    
    receipts = cur.fetchall()
    print(f"Found {len(receipts):,} unlinked CUSTOMER DEPOSITS")
    
    # Parse reserve numbers
    matches = []
    etransfers = 0
    names_only = 0
    no_pattern = 0
    
    for receipt_id, date, revenue, description in receipts:
        reserve = extract_reserve_number(description)
        
        if reserve:
            # Verify reserve exists in charters
            cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
            charter = cur.fetchone()
            
            if charter:
                matches.append({
                    "receipt_id": receipt_id,
                    "reserve_number": reserve,
                    "charter_id": charter[0],
                    "description": description
                })
            else:
                print(f"  WARNING: Reserve {reserve} not found in charters (receipt {receipt_id})")
        elif re.search(r'\b\d{9,12}\b', description):
            etransfers += 1
        elif re.search(r'[A-Z]{2,}', description):
            names_only += 1
        else:
            no_pattern += 1
    
    print(f"\nParsing results:")
    print(f"  - Found reserve numbers: {len(matches):,}")
    print(f"  - E-transfers (no reserve): {etransfers:,}")
    print(f"  - Names only (no reserve): {names_only:,}")
    print(f"  - No recognizable pattern: {no_pattern:,}")
    
    if len(matches) == 0:
        print("\nNo matches found. Sample descriptions:")
        for _, _, _, desc in receipts[:10]:
            print(f"  {desc[:80]}")
        cur.close()
        conn.close()
        return
    
    # Show samples
    print(f"\nSample matches (first 10):")
    for m in matches[:10]:
        print(f"  {m['reserve_number']} | {m['description'][:60]}")
    
    # Apply updates
    print("\n" + "="*80)
    response = input(f"Update {len(matches):,} receipts with reserve numbers? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        cur.close()
        conn.close()
        return
    
    print("\nApplying updates...")
    for match in matches:
        cur.execute("""
            UPDATE receipts
            SET reserve_number = %s, charter_id = %s
            WHERE receipt_id = %s
        """, (match["reserve_number"], match["charter_id"], match["receipt_id"]))
    
    conn.commit()
    print(f"✅ Updated {len(matches):,} receipts with reserve numbers")
    
    # Verify
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN reserve_number IS NOT NULL THEN 1 ELSE 0 END) as has_reserve
        FROM receipts
        WHERE revenue > 0
    """)
    r = cur.fetchone()
    print(f"\nFinal state: {r[0]:,} revenue receipts, {r[1]:,} with reserve_number ({r[1]/r[0]*100:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
