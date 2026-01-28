#!/usr/bin/env python3
"""
Fix missing vehicle_id foreign keys by matching vehicle text to vehicles table.

Problem: 18,645+ charters have vehicle text ('L10', 'L19', etc.) but NULL vehicle_id
Solution: Match charters.vehicle → vehicles.vehicle_number and set vehicle_id
"""

import psycopg2
import argparse
from datetime import datetime

def create_backup(cur, backup_name="charters_vehicle_id_fix"):
    """Create backup of charters table before modifications."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_table = f"{backup_name}_{timestamp}"
    
    print(f"\n{'='*80}")
    print(f"CREATING BACKUP")
    print(f"{'='*80}")
    print(f"Backup table: {backup_table}")
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM charters 
        WHERE vehicle IS NOT NULL AND vehicle_id IS NULL
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    print(f"✅ Backed up {count:,} charters to: {backup_table}\n")
    return backup_table

def analyze_matches(cur):
    """Analyze how many charters can be matched."""
    print(f"\n{'='*80}")
    print(f"ANALYZING VEHICLE MATCHES")
    print(f"{'='*80}\n")
    
    # Total needing fix
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL AND vehicle_id IS NULL
    """)
    total = cur.fetchone()[0]
    print(f"📊 Total charters needing vehicle_id: {total:,}")
    
    # Direct matches
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        INNER JOIN vehicles v ON UPPER(TRIM(c.vehicle)) = UPPER(TRIM(v.vehicle_number))
        WHERE c.vehicle IS NOT NULL AND c.vehicle_id IS NULL
    """)
    direct_matches = cur.fetchone()[0]
    print(f"✅ Direct matches (vehicle = vehicle_number): {direct_matches:,}")
    
    # Show sample matches
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.vehicle, v.vehicle_id, v.vehicle_number, v.make, v.model
        FROM charters c
        INNER JOIN vehicles v ON UPPER(TRIM(c.vehicle)) = UPPER(TRIM(v.vehicle_number))
        WHERE c.vehicle IS NOT NULL AND c.vehicle_id IS NULL
        LIMIT 10
    """)
    
    print(f"\nSample matches:")
    print(f"{'Charter':<10} {'Reserve#':<12} {'Text':<10} {'→ Vehicle ID':<13} {'Vehicle#':<12} {'Make/Model'}")
    print("-" * 85)
    for row in cur.fetchall():
        cid, rnum, vtext, vid, vnum, make, model = row
        print(f"{cid:<10} {rnum or 'N/A':<12} {vtext:<10} → {vid:<11} {vnum:<12} {make or 'N/A'} {model or ''}")
    
    # Unmatched
    unmatched = total - direct_matches
    if unmatched > 0:
        print(f"\n⚠️  Unmatched: {unmatched:,} charters (vehicle text doesn't match any vehicle_number)")
        
        cur.execute("""
            SELECT DISTINCT c.vehicle, COUNT(*) as count
            FROM charters c
            LEFT JOIN vehicles v ON UPPER(TRIM(c.vehicle)) = UPPER(TRIM(v.vehicle_number))
            WHERE c.vehicle IS NOT NULL 
              AND c.vehicle_id IS NULL 
              AND v.vehicle_id IS NULL
            GROUP BY c.vehicle
            ORDER BY count DESC
            LIMIT 15
        """)
        
        print(f"\nTop unmatched vehicle values:")
        print(f"{'Vehicle Text':<30} {'Count'}")
        print("-" * 40)
        for row in cur.fetchall():
            vtext, count = row
            print(f"{vtext:<30} {count:,}")
    
    return total, direct_matches, unmatched

def fix_vehicle_ids(cur, dry_run=True):
    """Update vehicle_id for charters where vehicle text matches vehicle_number."""
    print(f"\n{'='*80}")
    print(f"FIXING VEHICLE IDs")
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
        WHERE UPPER(TRIM(c.vehicle)) = UPPER(TRIM(v.vehicle_number))
          AND c.vehicle IS NOT NULL 
          AND c.vehicle_id IS NULL
    """
    
    print("SQL to execute:")
    print(update_query)
    
    if dry_run:
        # Just count
        cur.execute("""
            SELECT COUNT(*)
            FROM charters c
            INNER JOIN vehicles v ON UPPER(TRIM(c.vehicle)) = UPPER(TRIM(v.vehicle_number))
            WHERE c.vehicle IS NOT NULL AND c.vehicle_id IS NULL
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
    
    # Remaining NULL vehicle_ids
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL AND vehicle_id IS NULL
    """)
    remaining = cur.fetchone()[0]
    
    # Fixed count
    cur.execute("""
        SELECT COUNT(*) 
        FROM charters 
        WHERE vehicle IS NOT NULL AND vehicle_id IS NOT NULL
    """)
    fixed = cur.fetchone()[0]
    
    print(f"📊 Charters with vehicle text AND vehicle_id: {fixed:,} ✅")
    print(f"📊 Charters with vehicle text but NULL vehicle_id: {remaining:,}")
    
    if remaining == 0:
        print(f"\n🎉 ALL FIXED! No more missing vehicle_ids")
    elif remaining > 0:
        print(f"\n⚠️  {remaining:,} charters still need manual review (unmatched vehicle text)")
    
    return remaining

def main():
    parser = argparse.ArgumentParser(description='Fix missing vehicle_id foreign keys')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--skip-backup', action='store_true', help='Skip creating backup table')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not fix')
    
    args = parser.parse_args()
    
    print(f"\n{'='*80}")
    print(f"FIX MISSING VEHICLE_ID FOREIGN KEYS")
    print(f"{'='*80}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"Backup: {'Skipped' if args.skip_backup else 'Enabled'}")
    print(f"{'='*80}\n")
    
    # Connect
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    try:
        # Step 1: Create backup (unless skipped or dry-run)
        if not args.skip_backup and not args.dry_run:
            backup_table = create_backup(cur, "charters_backup_vehicle_id")
        
        # Step 2: Analyze matches
        total, direct_matches, unmatched = analyze_matches(cur)
        
        if args.analyze_only:
            print(f"\n📋 Analysis complete. Use --dry-run to preview fix, or remove flags to apply.")
            return
        
        # Step 3: Fix vehicle_ids
        updated_count = fix_vehicle_ids(cur, dry_run=args.dry_run)
        
        # Step 4: Commit (only if live mode)
        if not args.dry_run:
            conn.commit()
            print(f"\n✅ COMMITTED: {updated_count:,} vehicle_ids updated")
            
            # Step 5: Verify
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
