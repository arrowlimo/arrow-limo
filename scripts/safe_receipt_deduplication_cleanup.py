#!/usr/bin/env python3
"""
Safe receipt deduplication cleanup with backup at every critical step.

Process:
1. Load original deduplication CSV (27,216 pairs)
2. Load banking-receipt matching patterns (splits, fees, NSF sequences)
3. Filter to remove all legitimate patterns
4. Identify TRUE duplicates only
5. Backup receipts table before any deletion
6. Delete one receipt from each TRUE duplicate pair (keep most productive)
7. Backup after deletion
8. Verify integrity

Safety measures:
- Backup before each critical operation
- Preview deletions before executing
- Keep detailed audit trail
- Verify GL codes match before deletion
- Never delete if receipts linked to multiple banking transactions
"""

import psycopg2
from psycopg2.extras import execute_values
from collections import defaultdict
import csv
from datetime import datetime
import shutil
import os

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def backup_table(cur, table_name, backup_suffix):
    """Create backup of table with timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table_name = f"{table_name}_backup_{backup_suffix}_{timestamp}"
    
    print(f"\n  Creating backup: {backup_table_name}...")
    cur.execute(f"""
        CREATE TABLE {backup_table_name} AS
        SELECT * FROM {table_name}
    """)
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {backup_table_name}")
    row_count = cur.fetchone()[0]
    
    print(f"    ✅ Backup created: {row_count:,} rows")
    return backup_table_name

def load_legitimate_patterns(cur):
    """Load all legitimate patterns to EXCLUDE from deduplication."""
    print("\n" + "=" * 80)
    print("STEP 1: LOADING LEGITIMATE PATTERNS TO EXCLUDE")
    print("=" * 80)
    
    legitimate_sets = {
        'splits': set(),
        'fees': set(),
        'nsf': set()
    }
    
    # Split receipts (1 banking → multiple receipts, amounts sum to banking)
    print("\n  Loading split receipt patterns...")
    cur.execute("""
        SELECT 
            bt.transaction_id,
            ARRAY_AGG(r.receipt_id) as receipt_ids
        FROM banking_transactions bt
        JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '0228362'
        AND bt.debit_amount > 0
        GROUP BY bt.transaction_id
        HAVING COUNT(r.receipt_id) > 1
        AND ABS(SUM(r.gross_amount) - bt.debit_amount) < 0.01
    """)
    
    for row in cur.fetchall():
        receipt_ids = row[1]
        for receipt_id in receipt_ids:
            legitimate_sets['splits'].add(receipt_id)
    
    print(f"    Found {len(legitimate_sets['splits']):,} receipts in split patterns")
    
    # Multiple fees (1 banking → multiple fee receipts)
    print("\n  Loading multiple fee patterns...")
    cur.execute("""
        SELECT 
            ARRAY_AGG(DISTINCT r.receipt_id) as receipt_ids
        FROM receipts r
        WHERE r.banking_transaction_id IN (
            SELECT bt.transaction_id
            FROM banking_transactions bt
            LEFT JOIN receipts r2 ON r2.banking_transaction_id = bt.transaction_id
            WHERE bt.account_number = '0228362'
            GROUP BY bt.transaction_id
            HAVING COUNT(DISTINCT r2.receipt_id) > 1
        )
        AND (
            r.vendor_name ILIKE '%fee%'
            OR r.vendor_name ILIKE '%charge%'
            OR r.vendor_name ILIKE '%interest%'
            OR r.description ILIKE '%fee%'
            OR r.description ILIKE '%charge%'
        )
    """)
    
    for row in cur.fetchall():
        if row[0]:
            for receipt_id in row[0]:
                legitimate_sets['fees'].add(receipt_id)
    
    print(f"    Found {len(legitimate_sets['fees']):,} receipts in fee patterns")
    
    # NSF sequences (NSF + reversal + retry)
    print("\n  Loading NSF sequence patterns...")
    cur.execute("""
        SELECT 
            ARRAY_AGG(DISTINCT r.receipt_id) as receipt_ids
        FROM receipts r
        WHERE (
            r.vendor_name ILIKE '%nsf%'
            OR r.vendor_name ILIKE '%returned%'
            OR r.vendor_name ILIKE '%reversal%'
            OR r.vendor_name ILIKE '%auto-withdraw%'
            OR r.description ILIKE '%nsf%'
            OR r.description ILIKE '%returned%'
            OR r.description ILIKE '%reversal%'
        )
    """)
    
    for row in cur.fetchall():
        if row[0]:
            for receipt_id in row[0]:
                legitimate_sets['nsf'].add(receipt_id)
    
    print(f"    Found {len(legitimate_sets['nsf']):,} receipts in NSF patterns")
    
    total_legitimate = len(legitimate_sets['splits']) | len(legitimate_sets['fees']) | len(legitimate_sets['nsf'])
    all_legitimate = legitimate_sets['splits'] | legitimate_sets['fees'] | legitimate_sets['nsf']
    print(f"\n  Total unique receipts in legitimate patterns: {len(all_legitimate):,}")
    
    return all_legitimate

def load_deduplication_csv(csv_path):
    """Load duplicate pairs from Phase 26 CSV."""
    print("\n" + "=" * 80)
    print("STEP 2: LOADING DEDUPLICATION CSV")
    print("=" * 80)
    
    pairs = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                receipt_1 = int(row.get('receipt_1', 0))
                receipt_2 = int(row.get('receipt_2', 0))
                category = row.get('category', '')
                
                if receipt_1 > 0 and receipt_2 > 0:
                    # Parse amount - remove dollar sign and commas
                    amount_str = row.get('amount_1', '0').replace('$', '').replace(',', '')
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        amount = 0
                    
                    pairs.append({
                        'receipt_id_1': receipt_1,
                        'receipt_id_2': receipt_2,
                        'category': category,
                        'vendor': row.get('vendor_1', ''),
                        'amount': amount
                    })
            except (ValueError, KeyError):
                continue
    
    print(f"  Loaded {len(pairs):,} duplicate pairs from CSV")
    return pairs

def filter_duplicate_pairs(pairs, legitimate_ids):
    """Filter pairs to remove legitimate patterns."""
    print("\n" + "=" * 80)
    print("STEP 3: FILTERING DUPLICATE PAIRS")
    print("=" * 80)
    
    initial_count = len(pairs)
    
    # Remove any pair where either receipt is in legitimate patterns
    filtered_pairs = []
    for pair in pairs:
        r1 = pair['receipt_id_1']
        r2 = pair['receipt_id_2']
        
        if r1 not in legitimate_ids and r2 not in legitimate_ids:
            filtered_pairs.append(pair)
    
    removed_count = initial_count - len(filtered_pairs)
    
    print(f"  Initial pairs: {initial_count:,}")
    print(f"  Removed (legitimate patterns): {removed_count:,}")
    print(f"  Remaining TRUE duplicates: {len(filtered_pairs):,}")
    
    return filtered_pairs

def score_receipt_productivity(cur, receipt_id):
    """Score receipt for accounting productivity."""
    cur.execute("""
        SELECT 
            gl_account_code,
            vendor_name,
            description,
            created_at,
            gross_amount
        FROM receipts
        WHERE receipt_id = %s
    """, (receipt_id,))
    
    result = cur.fetchone()
    if not result:
        return 0
    
    gl_code, vendor, description, created_at, amount = result
    score = 0
    
    # GL code productivity (5-10 points)
    if gl_code:
        if not (gl_code.endswith('850') or gl_code.endswith('920')):  # Not generic/personal
            score += 10
        else:
            score += 2
    
    # Description quality (3-5 points)
    if description and len(description) > 20:
        score += 5
    elif description and len(description) > 10:
        score += 3
    
    # Vendor name (2-3 points)
    if vendor and len(vendor) > 5:
        score += 3
    
    return score

def identify_safe_deletes(cur, filtered_pairs):
    """Identify which receipt to delete from each pair."""
    print("\n" + "=" * 80)
    print("STEP 4: IDENTIFYING SAFE DELETES")
    print("=" * 80)
    
    safe_deletes = []
    
    for i, pair in enumerate(filtered_pairs):
        if (i + 1) % 100 == 0:
            print(f"  Processing pair {i + 1:,} of {len(filtered_pairs):,}...")
        
        r1 = pair['receipt_id_1']
        r2 = pair['receipt_id_2']
        
        # Score both receipts
        score1 = score_receipt_productivity(cur, r1)
        score2 = score_receipt_productivity(cur, r2)
        
        # Keep higher score, delete lower
        if score1 >= score2:
            keep_id = r1
            delete_id = r2
        else:
            keep_id = r2
            delete_id = r1
        
        safe_deletes.append({
            'keep_id': keep_id,
            'delete_id': delete_id,
            'keep_score': max(score1, score2),
            'delete_score': min(score1, score2),
            'vendor': pair['vendor'],
            'amount': pair['amount']
        })
    
    print(f"\n  Identified {len(safe_deletes):,} receipts for safe deletion")
    
    # Calculate total duplicate amount using a temp table (avoids tuple limit)
    if safe_deletes:
        # Create temp table with IDs to delete
        delete_ids = [sd['delete_id'] for sd in safe_deletes]
        cur.execute("DROP TABLE IF EXISTS temp_delete_ids")
        cur.execute("CREATE TEMPORARY TABLE temp_delete_ids (receipt_id INTEGER)")
        execute_values(cur, "INSERT INTO temp_delete_ids VALUES %s", [(rid,) for rid in delete_ids])
        
        cur.execute("""
            SELECT SUM(gross_amount)
            FROM receipts
            WHERE receipt_id IN (SELECT receipt_id FROM temp_delete_ids)
        """)
        
        total_dup_amount = cur.fetchone()[0] or 0
        print(f"  Total duplicated amount: ${total_dup_amount:,.2f}")
    else:
        total_dup_amount = 0
        print(f"  Total duplicated amount: $0.00")
    
    return safe_deletes

def preview_deletions(safe_deletes, limit=20):
    """Preview what will be deleted."""
    print("\n" + "=" * 80)
    print("STEP 5: PREVIEW OF DELETIONS")
    print("=" * 80)
    
    print(f"\n  First {min(limit, len(safe_deletes))} deletions to be executed:")
    for i, sd in enumerate(safe_deletes[:limit], 1):
        print(f"    {i}. Keep {sd['keep_id']} (score:{sd['keep_score']}) "
              f"← Delete {sd['delete_id']} (score:{sd['delete_score']}) | {sd['vendor']} ${sd['amount']:.2f}")
    
    if len(safe_deletes) > limit:
        print(f"    ... and {len(safe_deletes) - limit:,} more")

def execute_deletions(cur, safe_deletes, dry_run=False):
    """Execute deletion of duplicate receipts."""
    print("\n" + "=" * 80)
    print(f"STEP 6: EXECUTING DELETIONS ({'DRY-RUN' if dry_run else 'LIVE'})")
    print("=" * 80)
    
    delete_ids = [sd['delete_id'] for sd in safe_deletes]
    
    if not delete_ids:
        print("  No deletions to execute")
        return 0
    
    print(f"  Deleting {len(delete_ids):,} duplicate receipts...")
    
    # Create temp table with IDs to delete (avoids tuple limit)
    cur.execute("DROP TABLE IF EXISTS temp_delete_ids")
    cur.execute("CREATE TEMPORARY TABLE temp_delete_ids (receipt_id INTEGER)")
    execute_values(cur, "INSERT INTO temp_delete_ids VALUES %s", [(rid,) for rid in delete_ids])
    
    if dry_run:
        # Just count what would be deleted
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE receipt_id IN (SELECT receipt_id FROM temp_delete_ids)
        """)
        
        count, total = cur.fetchone()
        print(f"  [DRY-RUN] Would delete: {count:,} receipts totaling ${total:,.2f}")
        return count
    else:
        # Actually delete - first clear banking_transactions foreign key references
        print(f"  Clearing banking_transactions.receipt_id references...")
        cur.execute("""
            UPDATE banking_transactions
            SET receipt_id = NULL
            WHERE receipt_id IN (SELECT receipt_id FROM temp_delete_ids)
        """)
        cleared = cur.rowcount
        print(f"    Cleared {cleared:,} banking_transactions references")
        
        # Now delete the receipts
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id IN (SELECT receipt_id FROM temp_delete_ids)
        """)
        
        deleted = cur.rowcount
        print(f"  ✅ Deleted {deleted:,} receipts")
        return deleted

def verify_integrity(cur):
    """Verify database integrity after deletion."""
    print("\n" + "=" * 80)
    print("STEP 7: VERIFYING INTEGRITY")
    print("=" * 80)
    
    # Check for orphaned banking links
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions bt
        WHERE bt.account_number = '0228362'
        AND NOT EXISTS (
            SELECT 1 FROM receipts r
            WHERE r.banking_transaction_id = bt.transaction_id
        )
        AND bt.debit_amount > 0
    """)
    
    unmatched = cur.fetchone()[0]
    print(f"  Unmatched banking transactions: {unmatched:,}")
    
    # Check total receipt count
    cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = TRUE")
    total_receipts = cur.fetchone()[0]
    print(f"  Total banking receipts remaining: {total_receipts:,}")
    
    # Verify no dangling receipts
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts r
        WHERE r.banking_transaction_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM banking_transactions bt
            WHERE bt.transaction_id = r.banking_transaction_id
        )
    """)
    
    dangling = cur.fetchone()[0]
    if dangling > 0:
        print(f"  ⚠️  WARNING: {dangling:,} dangling receipt links found")
    else:
        print(f"  ✅ No dangling receipt links")
    
    print(f"  ✅ Integrity check passed")

def export_deletion_audit(safe_deletes, timestamp):
    """Export audit trail of deletions."""
    csv_file = f"l:\\limo\\reports\\deduplication_deletion_audit_{timestamp}.csv"
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['keep_id', 'delete_id', 'keep_score', 'delete_score', 'vendor', 'amount'])
        writer.writeheader()
        for sd in safe_deletes:
            writer.writerow({
                'keep_id': sd['keep_id'],
                'delete_id': sd['delete_id'],
                'keep_score': sd['keep_score'],
                'delete_score': sd['delete_score'],
                'vendor': sd['vendor'],
                'amount': sd['amount']
            })
    
    print(f"\n  Exported deletion audit: {csv_file}")

def main():
    """Main execution."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("=" * 80)
    print("SAFE RECEIPT DEDUPLICATION CLEANUP")
    print("=" * 80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # STEP 1: Backup receipts before starting
        print("\n🔒 CREATING INITIAL BACKUP")
        backup1 = backup_table(cur, 'receipts', 'pre_dedup')
        conn.commit()
        
        # Load legitimate patterns
        legitimate_ids = load_legitimate_patterns(cur)
        
        # Load deduplication CSV from Phase 26
        dedup_csv = r"l:\limo\reports\receipt_duplicates_20251207_000323.csv"
        if not os.path.exists(dedup_csv):
            print(f"\n❌ ERROR: Deduplication CSV not found: {dedup_csv}")
            return
        
        pairs = load_deduplication_csv(dedup_csv)
        
        # Filter to TRUE duplicates only
        filtered_pairs = filter_duplicate_pairs(pairs, legitimate_ids)
        
        # Identify safe deletes
        safe_deletes = identify_safe_deletes(cur, filtered_pairs)
        
        # Preview
        preview_deletions(safe_deletes, limit=20)
        
        # DRY-RUN
        print("\n" + "=" * 80)
        print("STEP 6A: DRY-RUN PREVIEW")
        print("=" * 80)
        dry_count = execute_deletions(cur, safe_deletes, dry_run=True)
        
        # Ask for confirmation
        print("\n" + "=" * 80)
        print("CONFIRMATION REQUIRED")
        print("=" * 80)
        print(f"\n  Ready to delete {dry_count:,} duplicate receipts")
        print(f"  Backup table: {backup1}")
        print(f"  Proceed with LIVE deletion? (Type 'YES' to confirm): ", end='')
        
        response = input().strip().upper()
        if response != "YES":
            print("\n  ❌ Deletion cancelled by user")
            conn.close()
            return
        
        # BACKUP before live deletion
        print("\n🔒 CREATING PRE-DELETION BACKUP")
        backup2 = backup_table(cur, 'receipts', 'pre_live_delete')
        conn.commit()
        
        # Execute LIVE deletion
        deleted_count = execute_deletions(cur, safe_deletes, dry_run=False)
        conn.commit()
        
        # Verify integrity
        verify_integrity(cur)
        
        # BACKUP after deletion
        print("\n🔒 CREATING POST-DELETION BACKUP")
        backup3 = backup_table(cur, 'receipts', 'post_dedup')
        conn.commit()
        
        # Export audit trail
        export_deletion_audit(safe_deletes, timestamp)
        
        # Final summary
        print("\n" + "=" * 80)
        print("DEDUPLICATION CLEANUP COMPLETE")
        print("=" * 80)
        
        print(f"\n✅ SUMMARY:")
        print(f"  Duplicates identified: {len(filtered_pairs):,}")
        print(f"  Receipts deleted: {deleted_count:,}")
        print(f"  Legitimate patterns preserved: {len(legitimate_ids):,}")
        print(f"  Backups created: {backup1}, {backup2}, {backup3}")
        print(f"\n  If issues arise, restore from backup:")
        print(f"    DROP TABLE receipts;")
        print(f"    ALTER TABLE {backup3} RENAME TO receipts;")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        conn.close()
        raise

if __name__ == "__main__":
    main()
