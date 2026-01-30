#!/usr/bin/env python3
"""Verify liquor purchases are recorded as client beverages (GL 5900)"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("LIQUOR PURCHASES - GL CODE VERIFICATION")
print("="*100)

# Search for liquor-related receipts by vendor and category
cur.execute("""
    SELECT 
        vendor_name,
        category,
        gl_account_code,
        COUNT(*) as cnt,
        SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%'
       OR vendor_name ILIKE '%wine%'
       OR vendor_name ILIKE '%beer%'
       OR vendor_name ILIKE '%alcohol%'
       OR canonical_vendor ILIKE '%liquor%'
       OR category ILIKE '%liquor%'
       OR category ILIKE '%beverage%'
       OR description ILIKE '%liquor%'
       OR description ILIKE '%wine%'
       OR description ILIKE '%alcohol%'
    GROUP BY vendor_name, category, gl_account_code
    ORDER BY cnt DESC, total DESC
""")

rows = cur.fetchall()

if rows:
    print(f"\n{'Vendor':<40} {'Category':<30} {'GL':>6}  {'Count':>5}  {'Total':>12}")
    print("="*100)
    
    total_receipts = 0
    total_amount = 0
    correct_gl = 0
    incorrect_gl = 0
    
    for r in rows:
        vendor = r[0] or 'Unknown'
        cat = r[1] or 'NULL'
        gl = r[2] or 'NULL'
        cnt = r[3]
        amount = r[4]
        
        total_receipts += cnt
        total_amount += amount
        
        # Mark if GL is correct (5900 for client beverages)
        status = "✓" if gl == '5900' else "✗"
        
        if gl == '5900':
            correct_gl += cnt
        else:
            incorrect_gl += cnt
        
        print(f"{vendor[:40]:<40} {cat[:30]:<30} {gl:>6}  {cnt:>5}  ${amount:>11,.2f} {status}")
    
    print("="*100)
    print(f"Total liquor receipts: {total_receipts:,}")
    print(f"Total amount: ${total_amount:,.2f}")
    print(f"\n✓ Correct GL 5900 (Client Beverages): {correct_gl:,} receipts")
    print(f"✗ Wrong GL code: {incorrect_gl:,} receipts")
    
    # List receipts that need correction
    if incorrect_gl > 0:
        print("\n" + "="*100)
        print("RECEIPTS NEEDING CORRECTION (should be GL 5900)")
        print("="*100)
        
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                category,
                gl_account_code,
                gross_amount,
                description
            FROM receipts
            WHERE (vendor_name ILIKE '%liquor%'
                OR vendor_name ILIKE '%wine%'
                OR vendor_name ILIKE '%beer%'
                OR vendor_name ILIKE '%alcohol%'
                OR canonical_vendor ILIKE '%liquor%'
                OR category ILIKE '%liquor%'
                OR category ILIKE '%beverage%'
                OR description ILIKE '%liquor%'
                OR description ILIKE '%wine%'
                OR description ILIKE '%alcohol%')
              AND (gl_account_code IS NULL OR gl_account_code != '5900')
            ORDER BY receipt_date DESC
            LIMIT 50
        """)
        
        incorrect = cur.fetchall()
        print(f"\n{'ID':<8} {'Date':<12} {'Vendor':<25} {'Category':<25} {'GL':>6}  {'Amount':>10}")
        print("="*100)
        for r in incorrect:
            rid = r[0]
            date = str(r[1]) if r[1] else 'NULL'
            vendor = (r[2] or 'Unknown')[:25]
            cat = (r[3] or 'NULL')[:25]
            gl = r[4] or 'NULL'
            amt = r[5] or 0
            print(f"{rid:<8} {date:<12} {vendor:<25} {cat:<25} {gl:>6}  ${amt:>9,.2f}")
        
        if len(incorrect) == 50:
            print(f"\n(Showing first 50 of {incorrect_gl} receipts needing correction)")

else:
    print("\n✓ No liquor purchases found")

cur.close()
conn.close()
