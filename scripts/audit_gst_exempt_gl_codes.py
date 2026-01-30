#!/usr/bin/env python3
"""
Auto-verify and correct GST-exempt GL codes
Identifies receipts marked as GST-exempt and validates their GL account codes
"""
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

try:
    # ============================================================================
    # STEP 1: Identify GST-exempt receipts
    # ============================================================================
    print("=" * 80)
    print("STEP 1: Finding GST-Exempt Receipts")
    print("=" * 80)
    
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN gst_code = 'GST_EXEMPT' THEN 1 END) as by_code,
               COUNT(CASE WHEN gst_amount = 0 AND gst_code IS NULL THEN 1 END) as zero_gst_no_code,
               COUNT(CASE WHEN gst_code = 'DRIVER_PERSONAL' THEN 1 END) as driver_personal
        FROM receipts
        WHERE gst_amount = 0 OR gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL'
    """)
    
    counts = cur.fetchone()
    total, by_code, zero_no_code, driver_personal = counts
    
    print(f"\nReceipts with $0 GST:")
    print(f"  - Marked as GST_EXEMPT: {by_code}")
    print(f"  - Have $0 GST but no code: {zero_no_code}")
    print(f"  - Marked as DRIVER_PERSONAL: {driver_personal}")
    print(f"  - Total GST=0 receipts: {total}")
    
    # ============================================================================
    # STEP 2: Check for invalid GL codes on GST-exempt items
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 2: Validating GL Codes")
    print("=" * 80)
    
    # Get all valid GL codes
    cur.execute("""
        SELECT account_code FROM chart_of_accounts WHERE account_code IS NOT NULL
        ORDER BY account_code
    """)
    valid_gl_codes = set(row[0] for row in cur.fetchall())
    print(f"\n✓ Found {len(valid_gl_codes)} valid GL codes in chart of accounts")
    
    # Check GST-exempt receipts with invalid GL codes
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, category, 
               gl_account_code, gl_account_name, gross_amount, gst_code
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        AND (gl_account_code IS NULL OR gl_account_code = '')
        ORDER BY receipt_date DESC
        LIMIT 50
    """)
    
    missing_gl = cur.fetchall()
    print(f"\n⚠ GST-exempt receipts missing GL codes: {len(missing_gl)}")
    
    if missing_gl:
        print("\nSample of receipts with missing GL codes:")
        for row in missing_gl[:10]:
            receipt_id, receipt_date, vendor_name, category, gl_code, gl_name, amount, gst_code = row
            print(f"  #{receipt_id:8} | {receipt_date} | {vendor_name:20} | Cat: {category or 'None':15} | GL: {gl_code or 'MISSING':8} | ${amount:8.2f}")
    
    # Check for invalid GL codes
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, category,
               gl_account_code, gl_account_name, gross_amount, gst_code
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        AND gl_account_code IS NOT NULL
        AND gl_account_code != ''
        ORDER BY receipt_date DESC
    """)
    
    gst_exempt_with_gl = cur.fetchall()
    invalid_gl = []
    
    for row in gst_exempt_with_gl:
        receipt_id, receipt_date, vendor_name, category, gl_code, gl_name, amount, gst_code = row
        if gl_code not in valid_gl_codes:
            invalid_gl.append(row)
    
    print(f"\n⚠ GST-exempt receipts with INVALID GL codes: {len(invalid_gl)}")
    
    if invalid_gl:
        print("\nInvalid GL codes found:")
        for row in invalid_gl[:10]:
            receipt_id, receipt_date, vendor_name, category, gl_code, gl_name, amount, gst_code = row
            print(f"  #{receipt_id:8} | {receipt_date} | {vendor_name:20} | GL: {gl_code or 'INVALID':8} (name: {gl_name or 'None'}) | ${amount:8.2f}")
    
    # ============================================================================
    # STEP 3: Suggest GL codes based on vendor/category
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 3: Suggesting Correct GL Codes")
    print("=" * 80)
    
    # Get common GL codes used in the database
    cur.execute("""
        SELECT gl_account_code, COUNT(*) as usage_count
        FROM receipts
        WHERE gl_account_code IS NOT NULL AND gl_account_code != ''
        GROUP BY gl_account_code
        ORDER BY usage_count DESC
        LIMIT 20
    """)
    
    common_gl = cur.fetchall()
    print(f"\nMost commonly used GL codes:")
    for gl_code, count in common_gl:
        print(f"  {gl_code}: {count} receipts")
    
    # ============================================================================
    # STEP 4: Group GST-exempt items by vendor to identify patterns
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 4: Analyzing GST-Exempt Vendors & Categories")
    print("=" * 80)
    
    cur.execute("""
        SELECT COALESCE(canonical_vendor, vendor_name) as vendor, 
               COALESCE(category, 'UNCATEGORIZED') as category,
               COUNT(*) as count,
               SUM(gross_amount) as total_amount,
               COUNT(DISTINCT gl_account_code) as gl_code_count,
               STRING_AGG(DISTINCT gl_account_code, ', ') as gl_codes
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        GROUP BY COALESCE(canonical_vendor, vendor_name), COALESCE(category, 'UNCATEGORIZED')
        ORDER BY count DESC
    """)
    
    vendor_patterns = cur.fetchall()
    print(f"\nVendors/Categories with GST-exempt items ({len(vendor_patterns)} total):")
    print(f"{'Vendor':<30} {'Category':<20} {'Count':<6} {'Total':<12} {'GL Codes':<40}")
    print("-" * 110)
    
    for vendor, category, count, total, gl_count, gl_codes in vendor_patterns[:20]:
        gl_str = (gl_codes or 'NONE')[:38]
        print(f"{vendor:<30} {category:<20} {count:<6} ${total:>10.2f}  {gl_str:<40}")
    
    # ============================================================================
    # STEP 5: Suggest corrections
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 5: Identifying Items Needing GL Code Fixes")
    print("=" * 80)
    
    # Find GST-exempt items missing GL codes, group by vendor to suggest appropriate code
    cur.execute("""
        SELECT vendor_name, category, COUNT(*) as count
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        AND (gl_account_code IS NULL OR gl_account_code = '')
        GROUP BY vendor_name, category
        ORDER BY count DESC
    """)
    
    missing_gl_by_vendor = cur.fetchall()
    
    print(f"\nVendors/Categories needing GL code assignment ({len(missing_gl_by_vendor)} total):")
    print(f"{'Vendor':<30} {'Category':<20} {'Count':<6}")
    print("-" * 56)
    
    for vendor, category, count in missing_gl_by_vendor[:20]:
        cat_str = category or 'UNCATEGORIZED'
        print(f"{vendor:<30} {cat_str:<20} {count:<6}")
    
    # ============================================================================
    # STEP 6: Create mapping suggestions
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 6: GL Code Mapping Recommendations")
    print("=" * 80)
    
    # Common GST-exempt vendors and their typical GL codes
    gst_exempt_mappings = {
        'WCB': '6950',  # Workers Compensation
        'CRA': '5100',  # Taxes (CRA payments)
        'GST': '2550',  # GST Payable
        'PST': '2550',  # Sales Tax Payable
        'FUEL': '5200', # Fuel & Lubricants
        'INSURANCE': '5300', # Insurance
    }
    
    print("\nRecommended GL codes for GST-exempt items:")
    cur.execute("""
        SELECT DISTINCT canonical_vendor, vendor_name
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        AND (gl_account_code IS NULL OR gl_account_code = '')
        ORDER BY canonical_vendor
    """)
    
    vendors_to_fix = cur.fetchall()
    suggestions = []
    
    for canonical, vendor_name in vendors_to_fix:
        vendor_upper = (canonical or vendor_name or '').upper()
        suggested_code = None
        
        # Try to match vendor to known GST-exempt types
        for key, code in gst_exempt_mappings.items():
            if key in vendor_upper:
                suggested_code = code
                break
        
        if suggested_code:
            suggestions.append((vendor_name, canonical, suggested_code))
            print(f"  {vendor_name or canonical:<30} → Suggest GL code {suggested_code}")
    
    # ============================================================================
    # STEP 7: Summary and recommendations
    # ============================================================================
    print("\n" + "=" * 80)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 80)
    
    print(f"\n📊 Audit Results:")
    print(f"  ✓ Total GST=0 receipts: {total}")
    print(f"  ✓ Marked as GST_EXEMPT: {by_code}")
    print(f"  ✓ Marked as DRIVER_PERSONAL: {driver_personal}")
    print(f"  ⚠ Missing GL codes: {len(missing_gl)}")
    print(f"  ⚠ Invalid GL codes: {len(invalid_gl)}")
    
    print(f"\n🔧 Recommended Actions:")
    print(f"  1. Assign GL codes to {len(missing_gl)} receipts missing GL accounts")
    print(f"  2. Correct {len(invalid_gl)} receipts with invalid GL codes")
    print(f"  3. Run the auto-correction script to apply fixes")
    
    print(f"\n✅ To auto-fix, run:")
    print(f"   python scripts/auto_correct_gst_exempt_gl_codes.py --apply")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
