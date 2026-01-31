"""
Analyze GL Code Duplicates and Usage Patterns
- Find duplicate/similar GL account descriptions
- Show usage frequency by year
- Suggest consolidation opportunities
- Review 2019 vendor patterns for GL mapping accuracy
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def analyze_gl_codes():
    """Analyze GL code usage and find duplicates"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("GL CODE DUPLICATE & USAGE ANALYSIS")
    print("=" * 80)
    
    # 1. Get all GL codes
    cur.execute("""
        SELECT account_code, account_name, account_type
        FROM chart_of_accounts
        ORDER BY account_code
    """)
    
    gl_codes = cur.fetchall()
    print(f"\n📊 Total GL Codes: {len(gl_codes)}")
    
    # 2. Find potential duplicates (similar names)
    print("\n" + "=" * 80)
    print("🔍 POTENTIAL DUPLICATE GL CODES (similar descriptions)")
    print("=" * 80)
    
    name_groups = defaultdict(list)
    for code, name, acct_type in gl_codes:
        # Normalize name for comparison
        normalized = name.lower().strip() if name else ""
        # Group by first 20 chars (catch similar names)
        key = normalized[:20] if len(normalized) > 20 else normalized
        name_groups[key].append((code, name, acct_type))
    
    duplicates_found = 0
    for key, codes in name_groups.items():
        if len(codes) > 1:
            duplicates_found += 1
            print(f"\n⚠️  Similar accounts (group {duplicates_found}):")
            for code, name, acct_type in codes:
                print(f"   {code} — {name} ({acct_type})")
    
    if duplicates_found == 0:
        print("✅ No obvious duplicates found")
    
    # 3. GL Code usage frequency
    print("\n" + "=" * 80)
    print("📈 GL CODE USAGE FREQUENCY (2019-2025)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COALESCE(r.gl_account_code, 'NULL') as code,
            COALESCE(r.gl_account_name, 'No Name') as name,
            EXTRACT(YEAR FROM r.receipt_date) as year,
            COUNT(*) as usage_count,
            SUM(r.gross_amount) as total_amount
        FROM receipts r
        WHERE EXTRACT(YEAR FROM r.receipt_date) >= 2019
        GROUP BY r.gl_account_code, r.gl_account_name, EXTRACT(YEAR FROM r.receipt_date)
        ORDER BY code, year
    """)
    
    usage = cur.fetchall()
    
    # Group by code
    code_usage = defaultdict(list)
    for code, name, year, count, amount in usage:
        code_usage[code].append((year, name, count, amount))
    
    print(f"\n📊 Top 20 Most Used GL Codes:")
    
    # Calculate total usage per code
    code_totals = []
    for code, years in code_usage.items():
        total_count = sum(y[2] for y in years)
        total_amount = sum(y[3] or 0 for y in years)
        code_totals.append((code, years[0][1], total_count, total_amount))
    
    code_totals.sort(key=lambda x: x[2], reverse=True)
    
    for code, name, total_count, total_amount in code_totals[:20]:
        print(f"\n{code} — {name}")
        print(f"   Total: {total_count} receipts, ${total_amount:,.2f}")
        for year, _, count, amount in code_usage[code]:
            print(f"   {int(year)}: {count} receipts, ${amount or 0:,.2f}")
    
    # 4. Vendor-GL mapping patterns (2019 focus)
    print("\n" + "=" * 80)
    print("🎯 2019 VENDOR → GL CODE PATTERNS (Manual Entry Era)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            r.vendor_name,
            r.gl_account_code,
            r.gl_account_name,
            COUNT(*) as frequency
        FROM receipts r
        WHERE EXTRACT(YEAR FROM r.receipt_date) = 2019
          AND r.vendor_name IS NOT NULL
          AND r.gl_account_code IS NOT NULL
        GROUP BY r.vendor_name, r.gl_account_code, r.gl_account_name
        HAVING COUNT(*) >= 3
        ORDER BY r.vendor_name, frequency DESC
    """)
    
    vendor_patterns = cur.fetchall()
    print(f"\n📋 Found {len(vendor_patterns)} vendor-GL patterns (3+ uses)")
    
    current_vendor = None
    for vendor, code, name, freq in vendor_patterns[:50]:
        if vendor != current_vendor:
            print(f"\n📦 {vendor}:")
            current_vendor = vendor
        print(f"   → {code} — {name} ({freq} times)")
    
    # 5. Specific checks for known categories
    print("\n" + "=" * 80)
    print("🔍 SPECIFIC CATEGORY CHECKS")
    print("=" * 80)
    
    categories = [
        ("FUEL", "fuel"),
        ("BEVERAGE", "beverage|bev"),
        ("AMENITIES", "amenity|amenities"),
        ("CHARTER", "charter"),
    ]
    
    for cat_name, pattern in categories:
        print(f"\n{cat_name} codes:")
        cur.execute("""
            SELECT account_code, account_name
            FROM chart_of_accounts
            WHERE account_name ~* %s
            ORDER BY account_code
        """, (pattern,))
        
        codes = cur.fetchall()
        if codes:
            for code, name in codes:
                # Get usage count
                cur.execute("""
                    SELECT COUNT(*), SUM(gross_amount)
                    FROM receipts
                    WHERE gl_account_code = %s
                """, (code,))
                count, total = cur.fetchone()
                print(f"   {code} — {name}")
                print(f"      Used: {count or 0} times, ${total or 0:,.2f} total")
        else:
            print(f"   ❌ No codes found matching pattern '{pattern}'")
    
    # 6. Missing GL codes (receipts with NULL)
    print("\n" + "=" * 80)
    print("⚠️  RECEIPTS MISSING GL CODES")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as missing_count,
            SUM(gross_amount) as missing_amount
        FROM receipts
        WHERE gl_account_code IS NULL
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    missing = cur.fetchall()
    total_missing = sum(m[1] for m in missing)
    print(f"\n📊 Total receipts without GL code: {total_missing}")
    for year, count, amount in missing:
        print(f"   {int(year)}: {count} receipts, ${amount or 0:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)


if __name__ == "__main__":
    analyze_gl_codes()
