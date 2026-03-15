"""
Auto-update Fibrenew and Mike Woodrow receipts to GL 5410 (Rent Expense)

These are office rent payments:
- Mike Woodrow (landlord)
- Fibrenew (office rent)

EXCLUDES:
- FIBRENEW entries with GL 4110 (Customer Deposits - not rent)
- FIBRENEW OFFICE RENT (already correct at GL 5410)
"""

import psycopg2
import sys

# Rent vendor patterns
RENT_VENDOR_PATTERNS = [
    '%mike woodrow%',
    '%fibrenew%',
]

def main():
    dry_run = '--dry-run' in sys.argv or '--write' not in sys.argv
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    # Show current state
    print("="*80)
    print("Rent Expense (Fibrenew/Mike Woodrow) GL Code Analysis")
    print("="*80)
    
    # Build WHERE clause for vendor patterns
    vendor_like_clauses = []
    for _ in RENT_VENDOR_PATTERNS:
        vendor_like_clauses.append("LOWER(vendor_name) LIKE %s")
    
    vendor_conditions = "(" + " OR ".join(vendor_like_clauses) + ")"
    
    # Check current state - exclude customer deposits (GL 4110) and already correct (GL 5410)
    query = f"""
        SELECT 
            vendor_name,
            gl_account_code,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE {vendor_conditions}
          AND gl_account_code != '4110'  -- Exclude customer deposits
          AND (gl_account_code != '5410' OR gl_account_code IS NULL)
        GROUP BY vendor_name, gl_account_code
        ORDER BY total DESC
    """
    
    cur.execute(query, RENT_VENDOR_PATTERNS)
    rows = cur.fetchall()
    
    if not rows:
        print("\n✅ All rent receipts already have GL code 5410 (excluding customer deposits)")
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
    print("\nNote: Excludes FIBRENEW GL 4110 (Customer Deposits)")
    
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
              AND gl_account_code != %s  -- Exclude customer deposits
              AND (gl_account_code != %s OR gl_account_code IS NULL)
        """
        
        # Parameters in correct order: SET values first, then WHERE patterns, then exclusions
        update_params = [
            '5410',                       # gl_account_code
            'Rent Expense',               # gl_account_name
            'Rent',                       # category
            True,                         # verified_by_edit
            'auto_rent_gl_update',        # verified_by_user
        ] + RENT_VENDOR_PATTERNS + ['4110', '5410']  # WHERE patterns + exclusions
        
        cur.execute(update_query, update_params)
        updated_count = cur.rowcount
        conn.commit()
        
        print(f"✅ Updated {updated_count} receipts to GL 5410 (Rent Expense)")
        
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
              AND gl_account_code = '5410'
            GROUP BY vendor_name
            ORDER BY total DESC
        """
        
        cur.execute(summary_query, RENT_VENDOR_PATTERNS)
        
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
        print(f"\nAll marked as verified by: auto_rent_gl_update")
        
        # Show what was excluded
        print("\n" + "="*80)
        print("Customer Deposits (Excluded from update):")
        print("="*80)
        
        deposits_query = f"""
            SELECT vendor_name, COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE {vendor_conditions}
              AND gl_account_code = '4110'
            GROUP BY vendor_name
        """
        
        cur.execute(deposits_query, RENT_VENDOR_PATTERNS)
        deposits = cur.fetchall()
        
        if deposits:
            for r in deposits:
                print(f"{r[0]:<60} {r[1]:>6} ${r[2]:>11,.2f} (GL 4110 - kept)")
        else:
            print("None found")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
