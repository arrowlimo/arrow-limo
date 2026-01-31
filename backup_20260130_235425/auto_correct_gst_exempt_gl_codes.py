#!/usr/bin/env python3
"""
Auto-correct GST-exempt GL codes based on vendor and category patterns
Identifies and fixes incorrect or missing GL codes
"""
import psycopg2
import sys
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

def get_gl_code_for_vendor_category(vendor, category):
    """Suggest GL code based on vendor name and category"""
    
    vendor_upper = (vendor or '').upper()
    category_lower = (category or '').lower()
    
    # Hard-coded mappings for known vendors
    vendor_mappings = {
        'WCB': '6950',  # Workers Compensation
        'CRA': '5100',  # Taxes
        'REVENUE CANADA': '5100',
        'GST': '2550',  # GST Payable
        'PST': '2550',  # Sales Tax Payable
    }
    
    # Check vendor-based mapping
    for key, code in vendor_mappings.items():
        if key in vendor_upper:
            return code, f"Vendor match: {key}"
    
    # Category-based mappings
    category_mappings = {
        'fuel': '5200',
        'insurance': '5300',
        'maintenance': '5400',
        'office': '5600',
        'utilities': '5700',
        'rent': '5800',
        'licenses': '5900',
        'professional': '6000',
        'advertising': '6100',
        'travel': '6200',
        'meals': '6300',
        'supplies': '6400',
        'equipment': '6500',
        'repairs': '6550',
        'training': '6700',
        'legal': '6800',
    }
    
    for key, code in category_mappings.items():
        if key in category_lower:
            return code, f"Category match: {key}"
    
    # Default for uncategorized GST-exempt
    return '6900', "Default GST-exempt expense"

try:
    dry_run = '--apply' not in sys.argv
    
    if dry_run:
        print("=" * 80)
        print("DRY RUN MODE - No changes will be made")
        print("Run with --apply flag to make changes")
        print("=" * 80)
    else:
        print("=" * 80)
        print("APPLYING CORRECTIONS")
        print("=" * 80)
    
    # ============================================================================
    # Step 1: Fix missing GL codes
    # ============================================================================
    print("\n📋 Step 1: Fixing Missing GL Codes")
    print("-" * 80)
    
    cur.execute("""
        SELECT receipt_id, vendor_name, category, gst_code
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        AND (gl_account_code IS NULL OR gl_account_code = '')
        ORDER BY receipt_date DESC
    """)
    
    missing_gl_receipts = cur.fetchall()
    print(f"\nFound {len(missing_gl_receipts)} receipts with missing GL codes\n")
    
    corrections_to_apply = []
    
    for receipt_id, vendor_name, category, gst_code in missing_gl_receipts:
        suggested_gl, reason = get_gl_code_for_vendor_category(vendor_name, category)
        
        # Get GL name
        cur.execute("SELECT account_name FROM chart_of_accounts WHERE account_code = %s", (suggested_gl,))
        gl_result = cur.fetchone()
        gl_name = gl_result[0] if gl_result else None
        
        corrections_to_apply.append({
            'receipt_id': receipt_id,
            'vendor_name': vendor_name,
            'category': category,
            'gl_code': suggested_gl,
            'gl_name': gl_name,
            'reason': reason
        })
        
        print(f"  #{receipt_id}: {vendor_name or 'Unknown':<25} ({category or 'No category':<15}) → {suggested_gl} ({reason})")
    
    # ============================================================================
    # Step 2: Apply corrections if --apply flag
    # ============================================================================
    if not dry_run and corrections_to_apply:
        print(f"\n✏️  Applying corrections for {len(corrections_to_apply)} receipts...\n")
        
        applied = 0
        for corr in corrections_to_apply:
            try:
                cur.execute("""
                    UPDATE receipts
                    SET gl_account_code = %s,
                        gl_account_name = %s
                    WHERE receipt_id = %s
                """, (corr['gl_code'], corr['gl_name'], corr['receipt_id']))
                
                applied += 1
                
                if applied <= 10:  # Show first 10
                    print(f"  ✓ #{corr['receipt_id']}: {corr['gl_code']} ({corr['gl_name']})")
                elif applied == 11:
                    print(f"  ... and {len(corrections_to_apply) - 10} more")
            except Exception as e:
                print(f"  ❌ #{corr['receipt_id']}: {e}")
        
        conn.commit()
        print(f"\n✅ Applied {applied} corrections")
    
    # ============================================================================
    # Step 3: Verify invalid GL codes
    # ============================================================================
    print("\n📋 Step 2: Checking for Invalid GL Codes")
    print("-" * 80)
    
    cur.execute("SELECT account_code FROM chart_of_accounts WHERE account_code IS NOT NULL")
    valid_gl_codes = set(row[0] for row in cur.fetchall())
    
    cur.execute("""
        SELECT receipt_id, vendor_name, gl_account_code, gl_account_name, gst_code
        FROM receipts
        WHERE (gst_code = 'GST_EXEMPT' OR gst_code = 'DRIVER_PERSONAL' OR (gst_amount = 0 AND gst_code IS NULL))
        AND gl_account_code IS NOT NULL
        AND gl_account_code != ''
    """)
    
    receipts_with_gl = cur.fetchall()
    invalid_gl_receipts = []
    
    for receipt_id, vendor_name, gl_code, gl_name, gst_code in receipts_with_gl:
        if gl_code not in valid_gl_codes:
            invalid_gl_receipts.append({
                'receipt_id': receipt_id,
                'vendor_name': vendor_name,
                'gl_code': gl_code,
                'gl_name': gl_name,
                'gst_code': gst_code
            })
    
    print(f"\nFound {len(invalid_gl_receipts)} receipts with invalid GL codes\n")
    
    if invalid_gl_receipts:
        for rec in invalid_gl_receipts[:10]:
            print(f"  #{rec['receipt_id']}: {rec['vendor_name']:<25} GL={rec['gl_code']:<8} (INVALID)")
        
        if len(invalid_gl_receipts) > 10:
            print(f"  ... and {len(invalid_gl_receipts) - 10} more")
        
        if not dry_run:
            print(f"\n⚠️  Skipped: Invalid GL codes need manual review")
    else:
        print("  ✓ No invalid GL codes found")
    
    # ============================================================================
    # Final Summary
    # ============================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if dry_run:
        print(f"\n📊 Dry Run Results:")
        print(f"  • Would fix: {len(corrections_to_apply)} receipts with missing GL codes")
        print(f"  • Found invalid: {len(invalid_gl_receipts)} receipts with invalid GL codes")
        print(f"\n✅ To apply these corrections, run:")
        print(f"   python scripts/auto_correct_gst_exempt_gl_codes.py --apply")
    else:
        print(f"\n✅ Applied corrections:")
        print(f"  • Fixed: {applied} receipts with missing GL codes")
        print(f"  • Invalid GL codes: {len(invalid_gl_receipts)} (require manual review)")

except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
