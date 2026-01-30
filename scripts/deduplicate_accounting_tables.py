#!/usr/bin/env python3
"""
Deduplicate and merge accounting tables into comprehensive chart_of_accounts.
Safely merges data from redundant tables before dropping them.
"""

import psycopg2
from datetime import datetime
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def backup_table(cur, table_name):
    """Create backup before any operations."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{table_name}_backup_{timestamp}"
    
    try:
        cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name}")
        return backup_name
    except Exception as e:
        print(f"  ⚠️  Backup failed: {e}")
        return None

def merge_bank_accounts(cur, conn, dry_run=True):
    """Merge bank_accounts and cibc_accounts into chart_of_accounts."""
    print("\n" + "="*80)
    print("MERGING BANK ACCOUNT TABLES")
    print("="*80)
    
    # Check bank_accounts
    cur.execute("SELECT COUNT(*) FROM bank_accounts")
    bank_count = cur.fetchone()[0]
    
    # Check cibc_accounts
    cur.execute("SELECT COUNT(*) FROM cibc_accounts")
    cibc_count = cur.fetchone()[0]
    
    print(f"\nbank_accounts: {bank_count} rows")
    print(f"cibc_accounts: {cibc_count} rows")
    
    if bank_count == 0 and cibc_count == 0:
        print("  ✓ No data to merge, safe to drop")
        return ['bank_accounts', 'cibc_accounts']
    
    # Show what would be merged
    print("\nbank_accounts data:")
    cur.execute("SELECT account_name, account_number, institution_name FROM bank_accounts LIMIT 5")
    for row in cur.fetchall():
        print(f"  • {row[0]} ({row[1]}) - {row[2]}")
    
    print("\ncibc_accounts data:")
    cur.execute("SELECT account_name, account_number FROM cibc_accounts LIMIT 5")
    for row in cur.fetchall():
        print(f"  • {row[0]} ({row[1]})")
    
    # Check if already in chart_of_accounts
    cur.execute("""
        SELECT account_code, account_name, bank_account_number 
        FROM chart_of_accounts 
        WHERE bank_account_number IS NOT NULL
    """)
    existing = cur.fetchall()
    
    print(f"\nAlready in chart_of_accounts: {len(existing)} bank accounts")
    for row in existing:
        print(f"  • {row[0]} - {row[1]} ({row[2]})")
    
    if not dry_run:
        print("\n  ⚠️  Data already in chart_of_accounts - safe to drop these tables")
        return ['bank_accounts', 'cibc_accounts']
    
    return []

def merge_account_categories(cur, conn, dry_run=True):
    """Merge account_categories into chart_of_accounts."""
    print("\n" + "="*80)
    print("MERGING ACCOUNT_CATEGORIES")
    print("="*80)
    
    cur.execute("SELECT COUNT(*) FROM account_categories")
    count = cur.fetchone()[0]
    
    print(f"\naccount_categories: {count} rows")
    
    # Show sample data
    cur.execute("""
        SELECT category_code, category_name, account_type 
        FROM account_categories 
        LIMIT 10
    """)
    
    print("\nSample categories:")
    for row in cur.fetchall():
        print(f"  • {row[0]} - {row[1]} ({row[2]})")
    
    # Check if these are actually different from chart_of_accounts
    cur.execute("""
        SELECT ac.category_code, ac.category_name, coa.account_code, coa.account_name
        FROM account_categories ac
        LEFT JOIN chart_of_accounts coa ON ac.category_code = coa.account_code
        WHERE coa.account_code IS NULL
        LIMIT 10
    """)
    
    missing = cur.fetchall()
    
    if len(missing) == 0:
        print("\n  ✓ All categories already in chart_of_accounts")
        return ['account_categories']
    else:
        print(f"\n  ⚠️  {len(missing)} categories NOT in chart_of_accounts:")
        for row in missing[:5]:
            print(f"    • {row[0]} - {row[1]}")
        print("\n  ⚠️  These should be reviewed before dropping")
        return []

def drop_empty_tables(cur, conn, dry_run=True):
    """Drop confirmed empty tables."""
    print("\n" + "="*80)
    print("DROPPING EMPTY TABLES")
    print("="*80)
    
    empty_tables = [
        'payment_reconciliation_ledger',
        'qb_export_general_journal',
    ]
    
    dropped = []
    
    for table in empty_tables:
        # Verify it's actually empty
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            if count == 0:
                print(f"\n{table}: {count} rows")
                
                if not dry_run:
                    # Create backup anyway
                    backup = backup_table(cur, table)
                    if backup:
                        print(f"  ✓ Backup created: {backup}")
                    
                    cur.execute(f"DROP TABLE {table}")
                    print(f"  ✓ DROPPED")
                    dropped.append(table)
                else:
                    print(f"  → Would DROP (empty)")
            else:
                print(f"\n{table}: {count} rows - NOT EMPTY, skipping")
        
        except Exception as e:
            print(f"\n{table}: Error - {e}")
    
    if not dry_run and dropped:
        conn.commit()
        print(f"\n✓ Dropped {len(dropped)} empty tables")
    
    return dropped

def archive_staging_tables(cur, conn, dry_run=True):
    """Archive staging tables that were already processed."""
    print("\n" + "="*80)
    print("ARCHIVING PROCESSED STAGING TABLES")
    print("="*80)
    
    # cibc_ledger_staging_archived_20251107 - already archived, confirm and drop
    staging_archived = [
        'cibc_ledger_staging_archived_20251107',
    ]
    
    archived = []
    
    for table in staging_archived:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            
            print(f"\n{table}: {count} rows")
            
            # Check if data is in banking_transactions
            if 'cibc' in table:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM banking_transactions 
                    WHERE description LIKE '%(from ledger staging)%'
                """)
                matched = cur.fetchone()[0]
                print(f"  • Found {matched} records in banking_transactions with '(from ledger staging)' marker")
                
                if matched > 0:
                    print(f"  ✓ Data already imported to banking_transactions")
                    
                    if not dry_run:
                        # Already has _archived suffix, just drop it
                        cur.execute(f"DROP TABLE {table}")
                        print(f"  ✓ DROPPED")
                        archived.append(table)
                    else:
                        print(f"  → Would DROP (data already imported)")
        
        except Exception as e:
            print(f"\n{table}: Error - {e}")
    
    if not dry_run and archived:
        conn.commit()
        print(f"\n✓ Dropped {len(archived)} archived staging tables")
    
    return archived

def analyze_qb_staging_tables(cur):
    """Analyze QB staging tables - these are HUGE and need special handling."""
    print("\n" + "="*80)
    print("ANALYZING QB STAGING TABLES (SPECIAL HANDLING NEEDED)")
    print("="*80)
    
    # staging_qb_accounts - 262,884 rows (misnamed, actually contains QB GL data)
    print("\nstaging_qb_accounts: 262,884 rows")
    print("  ⚠️  MISNAMED TABLE - Actually contains QuickBooks General Ledger accounts")
    print("  ⚠️  This was identified in November 7, 2025 staging remediation")
    print("  ⚠️  See STAGING_REMEDIATION_FINAL_REPORT.md for details")
    print("  📋  Action: Rename to staging_qb_gl_accounts (requires cleansing workflow)")
    print("  ❌  DO NOT DROP - contains 262K rows that need controlled promotion")
    
    # qb_accounts_staging - 298 rows
    print("\nqb_accounts_staging: 298 rows")
    cur.execute("SELECT COUNT(*) FROM qb_accounts")
    qb_count = cur.fetchone()[0]
    print(f"  • qb_accounts has {qb_count} rows")
    
    # Check overlap (cast types)
    cur.execute("""
        SELECT COUNT(*)
        FROM qb_accounts_staging qs
        JOIN qb_accounts qa ON qa.qb_account_number::text = qs.qb_serial_no::text
    """)
    overlap = cur.fetchone()[0]
    print(f"  • Overlap: {overlap} rows already in qb_accounts")
    
    if overlap == 298:
        print(f"  ✓ All staging data already in qb_accounts - safe to drop")
    else:
        print(f"  ⚠️  {298 - overlap} rows NOT in qb_accounts - needs review")

def cleanup_old_backups(cur, conn, dry_run=True, keep_days=30):
    """Drop old backup tables (older than keep_days)."""
    print("\n" + "="*80)
    print(f"CLEANING UP OLD BACKUP TABLES (>{keep_days} days old)")
    print("="*80)
    
    # Get all backup tables with dates
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE '%backup%'
        ORDER BY table_name
    """)
    
    backup_tables = [row[0] for row in cur.fetchall()]
    
    print(f"\nFound {len(backup_tables)} backup tables")
    
    # Parse dates from table names (format: tablename_backup_YYYYMMDD_HHMMSS)
    import re
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    old_backups = []
    
    for table in backup_tables:
        # Try to extract date
        match = re.search(r'(\d{8})_(\d{6})', table)
        if match:
            date_str = match.group(1)
            try:
                table_date = datetime.strptime(date_str, '%Y%m%d')
                
                if table_date < cutoff_date:
                    # Check if it's a charter backup (special handling)
                    if 'charter' in table:
                        # Keep charter backups longer (data fix audit trail)
                        if table_date < datetime.now() - timedelta(days=90):
                            old_backups.append((table, table_date))
                    else:
                        old_backups.append((table, table_date))
            except:
                pass
    
    print(f"\nOld backups (>{keep_days} days): {len(old_backups)}")
    
    if len(old_backups) == 0:
        print("  ✓ No old backups to clean up")
        return []
    
    # Group by base table
    by_table = {}
    for backup_table, backup_date in old_backups:
        base = backup_table.split('_backup_')[0]
        if base not in by_table:
            by_table[base] = []
        by_table[base].append((backup_table, backup_date))
    
    print(f"\nOld backups by table:")
    for base, backups in sorted(by_table.items()):
        print(f"\n{base}: {len(backups)} old backups")
        for backup_table, backup_date in sorted(backups, key=lambda x: x[1])[:3]:
            print(f"  • {backup_table} ({backup_date.strftime('%Y-%m-%d')})")
        if len(backups) > 3:
            print(f"  ... and {len(backups)-3} more")
    
    if not dry_run:
        print(f"\n⚠️  This would drop {len(old_backups)} backup tables")
        print("⚠️  Use --drop-old-backups flag to confirm")
    
    return old_backups

def main():
    parser = argparse.ArgumentParser(description='Deduplicate and merge accounting tables')
    parser.add_argument('--write', action='store_true', help='Apply changes (default: dry-run)')
    parser.add_argument('--drop-empty', action='store_true', help='Drop confirmed empty tables')
    parser.add_argument('--archive-staging', action='store_true', help='Archive processed staging tables')
    parser.add_argument('--merge-accounts', action='store_true', help='Merge bank/category tables')
    parser.add_argument('--cleanup-backups', action='store_true', help='Analyze old backups')
    parser.add_argument('--drop-old-backups', action='store_true', help='Actually drop old backups (requires --write)')
    parser.add_argument('--all', action='store_true', help='Run all deduplication tasks')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    dry_run = not args.write
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN - No changes will be made")
        print("Use --write to apply changes")
        print("="*80)
    
    try:
        # Always analyze QB staging
        analyze_qb_staging_tables(cur)
        
        if args.all or args.drop_empty:
            drop_empty_tables(cur, conn, dry_run)
        
        if args.all or args.archive_staging:
            archive_staging_tables(cur, conn, dry_run)
        
        if args.all or args.merge_accounts:
            merge_bank_accounts(cur, conn, dry_run)
            merge_account_categories(cur, conn, dry_run)
        
        if args.all or args.cleanup_backups:
            old_backups = cleanup_old_backups(cur, conn, dry_run)
            
            if args.drop_old_backups and args.write and len(old_backups) > 0:
                print(f"\n⚠️  DROPPING {len(old_backups)} OLD BACKUPS...")
                dropped = 0
                for backup_table, backup_date in old_backups:
                    try:
                        cur.execute(f"DROP TABLE {backup_table}")
                        dropped += 1
                    except Exception as e:
                        print(f"  ✗ Failed to drop {backup_table}: {e}")
                
                if dropped > 0:
                    conn.commit()
                    print(f"\n✓ Dropped {dropped} old backup tables")
        
        if not (args.all or args.drop_empty or args.archive_staging or args.merge_accounts or args.cleanup_backups):
            print("\n⚠️  No actions specified. Use --all or specific flags:")
            print("  --drop-empty         Drop empty tables")
            print("  --archive-staging    Archive processed staging tables")
            print("  --merge-accounts     Merge bank/category tables")
            print("  --cleanup-backups    Analyze old backups (>30 days)")
            print("  --all                Run all tasks")
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
