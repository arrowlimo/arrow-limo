"""
Delete true duplicate refunds safely.

Deletes:
1. Cross-source import duplicates (64 refunds) - keeps payments.table, deletes items CSV
2. Same-charter duplicates (9 refunds) - keeps first, deletes rest

Total: 73 refunds, $42,625.11

Before deletion, links 2 unlinked refunds to their charter (to avoid deleting linked version).
"""

import psycopg2
import sys

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

# Check for --write flag
DRY_RUN = '--write' not in sys.argv

if DRY_RUN:
    print("=" * 80)
    print("DRY RUN MODE - No changes will be made")
    print("Run with --write flag to apply deletions")
    print("=" * 80)
else:
    print("=" * 80)
    print("[WARN]  WRITE MODE - Will delete duplicate refunds")
    print("=" * 80)

print("\nDELETE TRUE DUPLICATES")
print("=" * 80)

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

# STEP 1: First, link the 2 unlinked refunds to avoid deleting their linked versions
print("\nStep 1: Linking unlinked refunds that have linked duplicates...")
print("-" * 80)

linkable = [
    {'refund_id': 1059, 'charter_id': 16537, 'reserve': '017660'},  # Has duplicate 1189
    {'refund_id': 1058, 'charter_id': 15225, 'reserve': '016345'}   # Has duplicate 1175
]

for link in linkable:
    print(f"  Linking refund #{link['refund_id']} → Charter {link['charter_id']} (Reserve {link['reserve']})")
    
    if not DRY_RUN:
        pg_cur.execute("""
            UPDATE charter_refunds
            SET charter_id = %s, reserve_number = %s
            WHERE id = %s AND charter_id IS NULL
        """, (link['charter_id'], link['reserve'], link['refund_id']))
        print(f"    ✓ Linked")

if not DRY_RUN:
    pg_conn.commit()
    print(f"\n✓ Linked {len(linkable)} refunds")
else:
    print(f"\n[DRY RUN] Would link {len(linkable)} refunds")

# STEP 2: Identify deletable duplicates
print("\n" + "=" * 80)
print("Step 2: Identifying deletable duplicates...")
print("-" * 80)

pg_cur.execute("""
    SELECT 
        refund_date,
        amount,
        COUNT(*) as refund_count,
        ARRAY_AGG(id ORDER BY id) as refund_ids,
        ARRAY_AGG(COALESCE(charter_id, 0) ORDER BY id) as charter_ids,
        ARRAY_AGG(COALESCE(source_file, 'Unknown') ORDER BY id) as sources
    FROM charter_refunds
    GROUP BY refund_date, amount
    HAVING COUNT(*) > 1
    ORDER BY amount DESC
""")

clusters = pg_cur.fetchall()

deletable_ids = []

for cluster in clusters:
    date, amount, count, ids, charter_ids, sources = cluster
    
    # Cross-source import duplicates: delete items CSV version
    has_payments_table = any('payments.table' in s for s in sources)
    has_items_csv = any('items-' in s for s in sources)
    
    if has_payments_table and has_items_csv:
        # Delete items CSV versions
        for i, source in enumerate(sources):
            if 'items-' in source:
                deletable_ids.append(ids[i])
    
    # Same-charter duplicates: delete all but first
    elif len(set(sources)) == 1:
        unique_charters = set([c for c in charter_ids if c != 0])
        
        if len(unique_charters) == 1 and len(unique_charters) > 0:
            # All linked to same charter - keep first, delete rest
            for i in range(1, len(ids)):
                deletable_ids.append(ids[i])

print(f"Found {len(deletable_ids)} refunds to delete")

# Get details of deletable refunds
pg_cur.execute("""
    SELECT id, refund_date, amount, source_file, charter_id, reserve_number
    FROM charter_refunds
    WHERE id = ANY(%s)
    ORDER BY amount DESC
""", (deletable_ids,))

deletable_refunds = pg_cur.fetchall()

print(f"\nDeletable refunds breakdown:")
print(f"{'ID':<8} {'Amount':<12} {'Date':<12} {'Charter':<10} {'Source':<30}")
print("-" * 80)

cross_source_count = 0
same_charter_count = 0
total_amount = 0

for refund in deletable_refunds[:20]:  # Show first 20
    refund_id, date, amount, source, charter_id, reserve = refund
    source_short = (source or '')[:27] + '...' if source and len(source) > 30 else (source or '')
    charter = charter_id or 'NULL'
    
    print(f"{refund_id:<8} ${float(amount):<11,.2f} {date} {charter:<10} {source_short:<30}")
    
    if 'items-' in (source or ''):
        cross_source_count += 1
    else:
        same_charter_count += 1
    
    total_amount += float(amount)

if len(deletable_refunds) > 20:
    print(f"... and {len(deletable_refunds) - 20} more")

for refund in deletable_refunds[20:]:
    total_amount += float(refund[2])
    if 'items-' in (refund[3] or ''):
        cross_source_count += 1
    else:
        same_charter_count += 1

print(f"\nDeletion summary:")
print(f"  Cross-source import duplicates: {cross_source_count}")
print(f"  Same-charter duplicates: {same_charter_count}")
print(f"  Total refunds to delete: {len(deletable_ids)}")
print(f"  Total amount: ${total_amount:,.2f}")

# STEP 3: Delete duplicates
print("\n" + "=" * 80)
print("Step 3: Deleting duplicates...")
print("-" * 80)

if DRY_RUN:
    print("[DRY RUN] Would delete the above refunds")
    print("\nTo apply deletions, run:")
    print("  python delete_true_duplicates.py --write")
else:
    print("[WARN]  Deleting refunds...")
    
    pg_cur.execute("""
        DELETE FROM charter_refunds
        WHERE id = ANY(%s)
    """, (deletable_ids,))
    
    deleted_count = pg_cur.rowcount
    pg_conn.commit()
    
    print(f"✓ Deleted {deleted_count} duplicate refunds")

# STEP 4: Verify results
print("\n" + "=" * 80)
print("Step 4: Verification")
print("-" * 80)

pg_cur.execute("SELECT COUNT(*) FROM charter_refunds")
total_refunds = pg_cur.fetchone()[0]

pg_cur.execute("SELECT COUNT(*) FROM charter_refunds WHERE reserve_number IS NULL")
unlinked_refunds = pg_cur.fetchone()[0]

print(f"\nAfter deletion:")
print(f"  Total refunds: {total_refunds}")
print(f"  Unlinked refunds: {unlinked_refunds}")
print(f"  Linked refunds: {total_refunds - unlinked_refunds}")
print(f"  Linkage rate: {(total_refunds - unlinked_refunds) / total_refunds * 100:.1f}%")

# Check for remaining duplicates
pg_cur.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT refund_date, amount
        FROM charter_refunds
        GROUP BY refund_date, amount
        HAVING COUNT(*) > 1
    ) subq
""")
remaining_duplicates = pg_cur.fetchone()[0]

print(f"\nRemaining duplicate clusters: {remaining_duplicates}")

pg_cur.close()
pg_conn.close()

print("\n" + "=" * 80)
if DRY_RUN:
    print("DRY RUN COMPLETE")
    print("=" * 80)
    print("\nNo changes made. Run with --write to apply deletions.")
else:
    print("DELETION COMPLETE")
    print("=" * 80)
    print(f"\n✓ Deleted {len(deletable_ids)} duplicate refunds")
    print(f"✓ Linked {len(linkable)} unlinked refunds before deletion")
    print(f"✓ Linkage rate improved to {(total_refunds - unlinked_refunds) / total_refunds * 100:.1f}%")
