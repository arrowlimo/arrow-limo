#!/usr/bin/env python3
"""
Second pass: Fix vehicle_id mismatches caused by hyphen variations.

Handles cases like:
  - Charter has "L3" but vehicle_number is "L-3"
  - Charter has "L10" but vehicle_number is "L-10"
"""

import psycopg2
import argparse
from datetime import datetime

def analyze_hyphen_matches(cur):
    """Analyze how many can be matched by removing hyphens."""
    print(f"\n{'='*80}")
    print(f"ANALYZING HYPHEN-NORMALIZED MATCHES")
    print(f"{'='*80}\n")
    
    # Total still needing fix
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL 
          AND TRIM(vehicle) != ''
          AND vehicle_id IS NULL
    """)
    total = cur.fetchone()[0]
    print(f"📊 Charters still needing vehicle_id: {total:,}")
    
    # Hyphen-normalized matches
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        INNER JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
        WHERE c.vehicle IS NOT NULL 
          AND TRIM(c.vehicle) != ''
          AND c.vehicle_id IS NULL
    """)
    hyphen_matches = cur.fetchone()[0]
    print(f"✅ Hyphen-normalized matches: {hyphen_matches:,}")
    
    # Show sample matches
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.vehicle, v.vehicle_id, v.vehicle_number, v.make, v.model
        FROM charters c
        INNER JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
        WHERE c.vehicle IS NOT NULL 
          AND TRIM(c.vehicle) != ''
          AND c.vehicle_id IS NULL
        LIMIT 15
    """)
    
    print(f"\nSample hyphen-normalized matches:")
    print(f"{'Charter':<10} {'Reserve#':<12} {'Text':<10} {'→ Vehicle ID':<13} {'Vehicle#':<12} {'Make/Model'}")
    print("-" * 85)
    for row in cur.fetchall():
        cid, rnum, vtext, vid, vnum, make, model = row
        print(f"{cid:<10} {rnum or 'N/A':<12} {vtext:<10} → {vid:<11} {vnum:<12} {make or 'N/A'} {model or ''}")
    
    # Still unmatched after hyphen normalization
    unmatched = total - hyphen_matches
    if unmatched > 0:
        print(f"\n⚠️  Still unmatched after hyphen normalization: {unmatched:,}")
        
        cur.execute("""
            SELECT DISTINCT c.vehicle, COUNT(*) as count
            FROM charters c
            LEFT JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
            WHERE c.vehicle IS NOT NULL 
              AND TRIM(c.vehicle) != ''
              AND c.vehicle_id IS NULL 
              AND v.vehicle_id IS NULL
            GROUP BY c.vehicle
            ORDER BY count DESC
            LIMIT 15
        """)
        
        print(f"\nTop still-unmatched vehicle values:")
        print(f"{'Vehicle Text':<30} {'Count'}")
        print("-" * 40)
        for row in cur.fetchall():
            vtext, count = row
            print(f"{repr(vtext):<30} {count:,}")
    
    return total, hyphen_matches, unmatched

def fix_vehicle_ids_pass2(cur, dry_run=True):
    """Update vehicle_id using hyphen-normalized matching."""
    print(f"\n{'='*80}")
    print(f"FIXING VEHICLE IDs (PASS 2 - HYPHEN NORMALIZATION)")
    print(f"{'='*80}\n")
    
    if dry_run:
        print("🔍 DRY-RUN MODE - No changes will be made\n")
    else:
        print("⚠️  LIVE MODE - Database will be updated\n")
    
    # Show the UPDATE query
    update_query = """
        UPDATE charters c
        SET vehicle_id = v.vehicle_id
        FROM vehicles v
        WHERE UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
          AND c.vehicle IS NOT NULL 
          AND TRIM(c.vehicle) != ''
          AND c.vehicle_id IS NULL
    """
    
    print("SQL to execute:")
    print(update_query)
    
    if dry_run:
        # Just count
        cur.execute("""
            SELECT COUNT(*)
            FROM charters c
            INNER JOIN vehicles v ON UPPER(REPLACE(TRIM(c.vehicle), '-', '')) = UPPER(REPLACE(TRIM(v.vehicle_number), '-', ''))
            WHERE c.vehicle IS NOT NULL 
              AND TRIM(c.vehicle) != ''
              AND c.vehicle_id IS NULL
        """)
        count = cur.fetchone()[0]
        print(f"\n✅ Would update {count:,} charters")
        return count
    else:
        # Actually update
        cur.execute(update_query)
        count = cur.rowcount
        print(f"\n✅ Updated {count:,} charters")
        return count

def verify_results(cur):
    """Verify the fix worked."""
    print(f"\n{'='*80}")
    print(f"VERIFICATION")
    print(f"{'='*80}\n")
    
    # Remaining NULL vehicle_ids (non-blank)
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL 
          AND TRIM(vehicle) != ''
          AND vehicle_id IS NULL
    """)
    remaining = cur.fetchone()[0]
    
    # Fixed count
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL 
          AND TRIM(vehicle) != ''
          AND vehicle_id IS NOT NULL
    """)
    fixed = cur.fetchone()[0]
    
    # Blank vehicle text (expected to have NULL vehicle_id)
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL 
          AND TRIM(vehicle) = ''
          AND vehicle_id IS NULL
    """)
    blank = cur.fetchone()[0]
    
    print(f"📊 Charters with vehicle text AND vehicle_id: {fixed:,} ✅")
    print(f"📊 Charters with non-blank vehicle but NULL vehicle_id: {remaining:,}")
    print(f"📊 Charters with blank/empty vehicle text: {blank:,} (expected NULL)")
    
    if remaining == 0:
        print(f"\n🎉 ALL NON-BLANK VEHICLES FIXED!")
    elif remaining > 0:
        print(f"\n⚠️  {remaining:,} charters still need manual review")
    
    return remaining

def main():
    parser = argparse.ArgumentParser(description='Fix vehicle_id - Pass 2 (hyphen normalization)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not fix')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"FIX VEHICLE_ID - PASS 2 (HYPHEN NORMALIZATION)")
    print(f"{'='*80}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Strategy: Match by removing hyphens from both sides")
    print(f"{'='*80}\n")
    
    # Connect
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    try:
        # Step 1: Analyze matches
        total, hyphen_matches, unmatched = analyze_hyphen_matches(cur)
        
        if args.analyze_only:
            print(f"\n📋 Analysis complete. Use --dry-run to preview fix, or remove flags to apply.")
            return
        
        # Step 2: Fix vehicle_ids
        updated_count = fix_vehicle_ids_pass2(cur, dry_run=args.dry_run)
        
        # Step 3: Commit (only if live mode)
        if not args.dry_run:
            conn.commit()
            print(f"\n✅ COMMITTED: {updated_count:,} vehicle_ids updated")
            
            # Step 4: Verify
            remaining = verify_results(cur)
        else:
            print(f"\n🔍 Dry-run complete. Run without --dry-run to apply changes.")
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        if not args.dry_run:
            conn.rollback()
            print("🔄 Rolled back transaction")
        import traceback
        traceback.print_exc()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
