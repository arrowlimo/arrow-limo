"""
Auto-update telecom vendor receipts to GL 6800 (Telephone & Internet)

These vendors provide phone and internet services:
- Rogers (wireless and cable)
- Telus (wireless and internet)
- Shaw Cable (cable and internet)
- Bell (wireless and landline)

All receipts should be classified as Telephone & Internet (GL 6800).
"""

import psycopg2
import sys

# Telecom vendor patterns
TELECOM_VENDOR_PATTERNS = [
    '%rogers%',
    '%telus%',
    '%shaw cable%',
    '%shaw %',
    '%bell canada%',
    '%bell mobility%',
]

# Exclude patterns that aren't actually telecom vendors
EXCLUDE_PATTERNS = [
    '%shawn%',
    '%robert crawshaw%',
    '%jason rogers%',
    '%armor heatco%',
    '%hot tub%',
]

def main():
    dry_run = '--dry-run' in sys.argv or '--write' not in sys.argv
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    # Show current state
    print("="*80)
    print("Telecom Vendors (Rogers/Telus/Shaw/Bell) GL Code Analysis")
    print("="*80)
    
    # Build WHERE clause for vendor patterns
    vendor_like_clauses = []
    for _ in TELECOM_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
    
    exclude_like_clauses = []
    for _ in EXCLUDE_PATTERNS:
        exclude_like_clauses.append("LOWER(vendor_name) NOT LIKE %s")
    
    vendor_conditions = "(" + " OR ".join(vendor_like_clauses) + ")"
    exclude_conditions = " AND ".join(exclude_like_clauses)
    
    # Check current state
    query = f"""
        SELECT 
            vendor_name,
            gl_account_code,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE {vendor_conditions}
          AND {exclude_conditions}
          AND (gl_account_code != '6800' OR gl_account_code IS NULL)
        GROUP BY vendor_name, gl_account_code
        ORDER BY total DESC
    """
    
    all_patterns = TELECOM_VENDOR_PATTERNS + EXCLUDE_PATTERNS
    cur.execute(query, all_patterns)
    rows = cur.fetchall()
    
    if not rows:
        print("\n✅ All telecom receipts already have GL code 6800")
        cur.close()
        conn.close()
        return
    
    print(f"\n{'Vendor':<60} {'Current GL':<12} {'Count':>6} {'Amount':>12}")
    print("-" * 92)
    
    total_count = 0
    total_amount = 0
    
    for r in rows:
        total_count += r[2]
        total_amount += r[3] or 0
        print(f"{r[0][:59]:<60} {str(r[1] or 'NULL'):<12} {r[2]:>6} ${r[3]:>11,.2f}")
    
    print("-" * 92)
    print(f"Total receipts to update: {total_count} (${total_amount:,.2f})")
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
        print("   Run with --write to apply updates")
    else:
        print("\n✍️  WRITE MODE - Updating receipts...")
        
        # Update query with correct parameter order
        update_query = f"""
            UPDATE receipts
            SET gl_account_code = %s,
                gl_account_name = %s,
                category = %s,
                verified_by_edit = %s,
                verified_at = NOW(),
                verified_by_user = %s
            WHERE {vendor_conditions}
              AND {exclude_conditions}
              AND (gl_account_code != %s OR gl_account_code IS NULL)
        """
        
        # Parameters in correct order: SET values first, then WHERE patterns, then != check
        update_params = [
            '6800',                           # gl_account_code
            'Telephone & Internet',           # gl_account_name
            'Utilities - Phone/Internet',     # category
            True,                             # verified_by_edit
            'auto_telecom_gl_update',         # verified_by_user
        ] + TELECOM_VENDOR_PATTERNS + EXCLUDE_PATTERNS + ['6800']  # WHERE patterns + != check
        
        cur.execute(update_query, update_params)
        updated_count = cur.rowcount
        conn.commit()
        
        print(f"✅ Updated {updated_count} receipts to GL 6800 (Telephone & Internet)")
        
        # Show updated state
        print("\n" + "="*80)
        print("Updated Receipt Summary:")
        print("="*80)
        
        summary_query = f"""
            SELECT 
                vendor_name,
                COUNT(*) as count,
                SUM(gross_amount) as total
            FROM receipts
            WHERE {vendor_conditions}
              AND {exclude_conditions}
              AND gl_account_code = '6800'
            GROUP BY vendor_name
            ORDER BY total DESC
        """
        
        cur.execute(summary_query, TELECOM_VENDOR_PATTERNS + EXCLUDE_PATTERNS)
        
        print(f"\n{'Vendor':<60} {'Count':>6} {'Amount':>12}")
        print("-" * 80)
        
        summary_total = 0
        summary_count = 0
        
        for r in cur.fetchall():
            summary_count += r[1]
            summary_total += r[2] or 0
            print(f"{r[0][:59]:<60} {r[1]:>6} ${r[2]:>11,.2f}")
        
        print("-" * 80)
        print(f"Total: {summary_count} receipts, ${summary_total:,.2f}")
        print(f"\nAll marked as verified by: auto_telecom_gl_update")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
