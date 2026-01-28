#!/usr/bin/env python3
"""
Core table protection safeguards.

Creates a defensive barrier against accidental deletion of critical tables:
- journal (general ledger entries)
- receipts (expense tracking)
- payments (revenue tracking)
- charters (bookings)
- clients (customers)
- employees (staff)

Usage:
  from table_protection import protect_deletion, PROTECTED_TABLES
  
  # Before any DELETE operation:
  protect_deletion('receipts', dry_run=False)  # Raises exception if protected
  
  # Or check if table is protected:
  if 'journal' in PROTECTED_TABLES:
      raise ValueError("Cannot delete from journal table!")
"""
import os
import sys
from datetime import datetime

# Core tables that should NEVER be truncated or mass-deleted without explicit override
PROTECTED_TABLES = {
    'journal',
    'receipts',
    'payments',
    'charters',
    'clients',
    'employees',
    'vehicles',
    'banking_transactions',
    'unified_general_ledger',
}


class TableProtectionError(Exception):
    """Raised when attempting to delete from a protected table."""
    pass


def protect_deletion(table_name: str, dry_run: bool = True, override_key: str = None):
    """
    Safeguard against accidental deletion from protected tables.
    
    Args:
        table_name: Name of table being deleted from
        dry_run: If True, allows deletion (dry-run mode doesn't modify data)
        override_key: Optional explicit override (use with extreme caution)
    
    Raises:
        TableProtectionError: If attempting to delete from protected table without override
    """
    if table_name.lower() in PROTECTED_TABLES:
        if dry_run:
            print(f"[WARN]  DRY-RUN: Would delete from PROTECTED table '{table_name}' (blocked in --write mode)")
            return
        
        if override_key != f"ALLOW_DELETE_{table_name.upper()}_{datetime.now().strftime('%Y%m%d')}":
            raise TableProtectionError(
                f"\n{'='*70}\n"
                f"🛑 CRITICAL PROTECTION: Cannot delete from '{table_name}'\n"
                f"{'='*70}\n"
                f"This table is in PROTECTED_TABLES and requires explicit override.\n"
                f"If you MUST delete (e.g., reimporting clean data), add:\n"
                f"  --override-key ALLOW_DELETE_{table_name.upper()}_{datetime.now().strftime('%Y%m%d')}\n"
                f"\n"
                f"Protected tables: {', '.join(sorted(PROTECTED_TABLES))}\n"
                f"{'='*70}\n"
            )
        else:
            print(f"[WARN]  OVERRIDE ACCEPTED: Deleting from '{table_name}' with explicit key")


def create_backup_before_delete(cur, table_name: str, condition: str = None):
    """
    Create a timestamped backup table before deletion.
    
    Args:
        cur: Database cursor
        table_name: Table to backup
        condition: Optional WHERE clause for selective backup
    
    Returns:
        str: Name of backup table created
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{table_name}_backup_{timestamp}"
    
    if condition:
        sql = f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name} WHERE {condition}"
    else:
        sql = f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name}"
    
    cur.execute(sql)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_name}")
    count = cur.fetchone()[0]
    
    print(f"✓ Created backup: {backup_name} ({count:,} rows)")
    return backup_name


def require_write_mode(args):
    """
    Helper to ensure --write flag is explicitly set.
    
    Usage in main():
        if require_write_mode(args):
            # Apply changes
        else:
            # Dry-run only
    """
    if not getattr(args, 'write', False):
        print("🔒 DRY-RUN MODE: No changes will be made.")
        print("   Add --write to apply changes.\n")
        return False
    return True


def log_deletion_audit(table_name: str, row_count: int, condition: str = None, script_name: str = None):
    """
    Log deletion operations to audit trail.
    
    Args:
        table_name: Table deleted from
        row_count: Number of rows deleted
        condition: WHERE clause used
        script_name: Name of script performing deletion
    """
    script = script_name or os.path.basename(sys.argv[0])
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        'timestamp': timestamp,
        'script': script,
        'table': table_name,
        'rows_deleted': row_count,
        'condition': condition or '(all rows)',
        'user': os.getenv('USER') or os.getenv('USERNAME') or 'unknown',
    }
    
    # Log to file
    log_file = 'deletion_audit.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | {script} | DELETE FROM {table_name} | {row_count} rows | {condition or 'ALL'}\n")
    
    print(f"📝 Logged to {log_file}")
    return log_entry


# Example usage pattern for scripts
EXAMPLE_USAGE = """
#!/usr/bin/env python3
import argparse
import psycopg2
from table_protection import protect_deletion, create_backup_before_delete, require_write_mode, log_deletion_audit

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--override-key', help='Override key for protected table deletion')
    args = parser.parse_args()
    
    conn = psycopg2.connect(...)
    cur = conn.cursor()
    
    table_name = 'receipts'
    
    # STEP 1: Check protection
    protect_deletion(table_name, dry_run=not args.write, override_key=args.override_key)
    
    # STEP 2: Create backup before deletion
    if args.write:
        backup_name = create_backup_before_delete(cur, table_name, condition="category = 'test'")
    
    # STEP 3: Perform deletion
    if require_write_mode(args):
        cur.execute("DELETE FROM receipts WHERE category = 'test'")
        deleted_count = cur.rowcount
        conn.commit()
        
        # STEP 4: Log the operation
        log_deletion_audit(table_name, deleted_count, condition="category = 'test'")
        
        print(f"Deleted {deleted_count} rows from {table_name}")
    else:
        print("DRY-RUN: Would delete test receipts")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
"""

if __name__ == '__main__':
    print("Table Protection Module")
    print("=" * 70)
    print(f"Protected tables: {', '.join(sorted(PROTECTED_TABLES))}")
    print("\nExample usage:")
    print(EXAMPLE_USAGE)
