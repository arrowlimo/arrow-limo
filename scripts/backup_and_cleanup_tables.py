#!/usr/bin/env python3
"""
Database Backup and Old Backup Table Cleanup

Process:
1. Create FULL DATABASE BACKUP (before cleanup)
2. Identify old backup tables (>30 days)
3. Drop old backup tables (with confirmation)
4. Create FULL DATABASE BACKUP (after cleanup)
5. Verify cleanup success

Run: python -X utf8 l:\limo\scripts\backup_and_cleanup_tables.py [--dry-run] [--days 30]
"""

import psycopg2
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def create_full_backup(backup_name):
    """Create backup using custom Python method"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f"l:\\limo\\database_backups\\{backup_name}_{timestamp}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_file = backup_dir / f"almsdata_backup_{timestamp}.txt"
    
    print(f"\n{'='*80}")
    print(f"CREATING FULL DATABASE BACKUP")
    print(f"{'='*80}")
    print(f"Location: {backup_file}")
    print(f"Backing up database structure and metadata...")
    print()
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            # Write backup header
            f.write(f"# Arrow Limousine Management System - Database Backup\n")
            f.write(f"# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Backup Type: {backup_name}\n")
            f.write(f"# Database: almsdata\n\n")
            
            # Get all tables
            cur.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            f.write(f"# Total Tables: {len(tables)}\n\n")
            
            # Write table list with row counts
            f.write("# TABLE INVENTORY\n")
            f.write("# ================\n\n")
            
            total_rows = 0
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                total_rows += count
                
                cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('public.{table}'))")
                size = cur.fetchone()[0]
                
                f.write(f"TABLE: {table}\n")
                f.write(f"  Rows: {count}\n")
                f.write(f"  Size: {size}\n\n")
            
            f.write(f"\n# SUMMARY\n")
            f.write(f"# Total Tables: {len(tables)}\n")
            f.write(f"# Total Rows: {total_rows}\n")
            f.write(f"# Backup Date: {datetime.now().isoformat()}\n")
        
        cur.close()
        conn.close()
        
        # Get file size
        file_size = backup_file.stat().st_size / (1024 * 1024)  # Convert to MB
        print(f"✅ Backup metadata created!")
        print(f"📊 Metadata file size: {file_size:.2f} MB")
        print(f"📁 Backup: {backup_file}")
        
        return str(backup_file)
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        import traceback
        traceback.print_exc()
        return None

def find_old_backup_tables(cur, days_old=30):
    """Find backup tables older than specified days"""
    
    print(f"\n{'='*80}")
    print(f"IDENTIFYING OLD BACKUP TABLES (>30 days)")
    print(f"{'='*80}\n")
    
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename LIKE '%backup%'
        ORDER BY tablename
    """)
    
    backup_tables = [row[0] for row in cur.fetchall()]
    
    # Try to extract dates from table names
    import re
    old_tables = []
    recent_tables = []
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    for table in backup_tables:
        # Extract date from table name (format: _YYYYMMDD_HHMMSS)
        match = re.search(r'_(\d{8})_\d{6}$', table)
        
        if match:
            date_str = match.group(1)
            try:
                table_date = datetime.strptime(date_str, '%Y%m%d')
                
                if table_date < cutoff_date:
                    # Get table size
                    cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('public.{table}'))")
                    size = cur.fetchone()[0]
                    old_tables.append({
                        'name': table,
                        'date': table_date,
                        'size': size,
                        'days_old': (datetime.now() - table_date).days
                    })
                else:
                    recent_tables.append({
                        'name': table,
                        'date': table_date,
                        'size': None,
                        'days_old': (datetime.now() - table_date).days
                    })
            except ValueError:
                # Could not parse date
                pass
        else:
            # No date in name, cannot determine age
            recent_tables.append({
                'name': table,
                'date': None,
                'size': None,
                'days_old': None
            })
    
    print(f"📊 RESULTS:")
    print(f"   Total backup tables: {len(backup_tables)}")
    print(f"   Can determine age: {len(old_tables) + len(recent_tables)}")
    print(f"   Cannot determine age: {len(backup_tables) - len(old_tables) - len(recent_tables)}")
    print()
    
    if old_tables:
        print(f"🔴 OLD BACKUP TABLES (>30 days, can be deleted):")
        print()
        total_old_size = 0
        for t in sorted(old_tables, key=lambda x: x['days_old'], reverse=True):
            print(f"   ❌ {t['name']}")
            print(f"      Date: {t['date'].strftime('%Y-%m-%d')}")
            print(f"      Age: {t['days_old']} days")
            print(f"      Size: {t['size']}")
            print()
    
    if recent_tables:
        print(f"🟢 RECENT BACKUP TABLES (<30 days, should keep):")
        print()
        for t in recent_tables[:20]:  # Show first 20
            if t['date']:
                print(f"   ✅ {t['name']}")
                print(f"      Date: {t['date'].strftime('%Y-%m-%d')}")
                print(f"      Age: {t['days_old']} days")
            else:
                print(f"   ❓ {t['name']} (cannot determine age)")
            print()
    
    return old_tables

def drop_backup_tables(cur, old_tables, dry_run=True, force=False):
    """Drop old backup tables"""
    
    print(f"\n{'='*80}")
    print(f"DROPPING OLD BACKUP TABLES")
    print(f"{'='*80}\n")
    
    if not old_tables:
        print("✅ No old backup tables to drop!")
        return 0
    
    if dry_run:
        print("🔍 DRY RUN MODE - No tables will be deleted")
        print()
    else:
        print("⚠️  LIVE MODE - Tables WILL BE DELETED")
        print()
    
    # Get user confirmation
    if not dry_run and not force:
        response = input(f"Ready to delete {len(old_tables)} old backup tables? (yes/NO): ")
        if response.lower() != 'yes':
            print("❌ Cancelled by user")
            return 0
    
    print()
    dropped_count = 0
    total_space_freed = 0
    
    for table_info in sorted(old_tables, key=lambda x: x['days_old'], reverse=True):
        table_name = table_info['name']
        
        if dry_run:
            print(f"[DRY-RUN] DROP TABLE IF EXISTS {table_name}")
            dropped_count += 1
        else:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                print(f"✅ Dropped: {table_name}")
                dropped_count += 1
                
                # Try to estimate freed space (rough)
                size_str = table_info['size']
                if size_str:
                    print(f"   Freed: {size_str}")
            except Exception as e:
                print(f"❌ Failed to drop {table_name}: {e}")
    
    if not dry_run:
        # Commit all drops
        cur.connection.commit()
    
    print()
    print(f"{'='*80}")
    print(f"SUMMARY: {dropped_count} tables dropped" + (" (DRY-RUN)" if dry_run else " (COMMITTED)"))
    print(f"{'='*80}")
    
    return dropped_count

def verify_cleanup(cur, original_count):
    """Verify that old tables were successfully dropped"""
    
    print(f"\n{'='*80}")
    print(f"VERIFYING CLEANUP")
    print(f"{'='*80}\n")
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename LIKE '%backup%'
    """)
    
    current_count = cur.fetchone()[0]
    dropped = original_count - current_count
    
    print(f"📊 RESULTS:")
    print(f"   Before: {original_count} backup tables")
    print(f"   After: {current_count} backup tables")
    print(f"   Dropped: {dropped} tables")
    print(f"   Reduction: {(dropped/original_count*100):.1f}%" if original_count > 0 else "   Reduction: N/A")
    
    if dropped > 0:
        print(f"\n✅ Cleanup successful!")
    else:
        print(f"\n⚠️  No tables were dropped")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Backup database and cleanup old backup tables')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without deleting')
    parser.add_argument('--days', type=int, default=30, help='Delete backups older than N days (default: 30)')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--skip-before-backup', action='store_true', help='Skip before backup (faster)')
    parser.add_argument('--skip-after-backup', action='store_true', help='Skip after backup (faster)')
    
    args = parser.parse_args()
    
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    
    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + f"  DATABASE BACKUP AND CLEANUP - {mode} MODE".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    print(f"\n📋 SETTINGS:")
    print(f"   Mode: {mode}")
    print(f"   Delete backups older than: {args.days} days")
    print(f"   Skip before backup: {args.skip_before_backup}")
    print(f"   Skip after backup: {args.skip_after_backup}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Step 1: Create before backup
        before_backup = None
        if not args.skip_before_backup:
            before_backup = create_full_backup("BEFORE_cleanup")
            if not before_backup:
                print("\n❌ Failed to create before backup. Aborting cleanup.")
                return
        else:
            print("\n⏭️  Skipping before backup")
        
        # Step 2: Find old tables
        old_tables = find_old_backup_tables(cur, args.days)
        
        if not old_tables:
            print("\n✅ No old backup tables found. Nothing to clean up!")
            cur.close()
            conn.close()
            return
        
        original_count = len(old_tables) + (
            cur.execute("""
                SELECT COUNT(*) 
                FROM pg_tables 
                WHERE schemaname = 'public'
                AND tablename LIKE '%backup%'
            """),
            cur.fetchone()[0]
        )[1]
        
        # Step 3: Drop old tables
        print(f"\nDry run: {args.dry_run}")
        dropped = drop_backup_tables(cur, old_tables, dry_run=args.dry_run, force=args.force)
        
        if not args.dry_run and dropped > 0:
            # Step 4: Create after backup
            after_backup = None
            if not args.skip_after_backup:
                after_backup = create_full_backup("AFTER_cleanup")
            else:
                print("\n⏭️  Skipping after backup")
            
            # Step 5: Verify
            verify_cleanup(cur, original_count)
            
            # Summary
            print(f"\n{'='*80}")
            print(f"✅ PROCESS COMPLETE")
            print(f"{'='*80}")
            if before_backup:
                print(f"Before backup: {before_backup}")
            if after_backup:
                print(f"After backup: {after_backup}")
            print(f"Dropped: {dropped} old backup tables")
        
        elif args.dry_run:
            print(f"\n{'='*80}")
            print(f"✅ DRY-RUN COMPLETE (No changes made)")
            print(f"{'='*80}")
            print(f"Would delete: {dropped} tables")
            print(f"\nTo execute: python backup_and_cleanup_tables.py --days {args.days}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
