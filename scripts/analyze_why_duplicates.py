"""
Analyze WHY we have duplicate refunds and determine which ones are safe to delete.

Duplicates exist because:
1. Same refund imported from multiple sources (payments.table + Square items CSVs)
2. True data duplication in source systems
3. Partial refunds that happen to be same amount on same date
"""

import psycopg2

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

print("=" * 80)
print("WHY DO WE HAVE DUPLICATES? - Root Cause Analysis")
print("=" * 80)

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

# Get duplicate clusters
pg_cur.execute("""
    SELECT 
        refund_date,
        amount,
        COUNT(*) as refund_count,
        STRING_AGG(CAST(id AS TEXT), ', ' ORDER BY id) as refund_ids,
        STRING_AGG(COALESCE(reserve_number, 'NULL'), ', ' ORDER BY id) as reserves,
        STRING_AGG(COALESCE(CAST(charter_id AS TEXT), 'NULL'), ', ' ORDER BY id) as charter_ids,
        STRING_AGG(COALESCE(source_file, 'Unknown'), ' | ' ORDER BY id) as sources,
        STRING_AGG(COALESCE(square_payment_id, 'NULL'), ', ' ORDER BY id) as square_ids
    FROM charter_refunds
    GROUP BY refund_date, amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, amount DESC
""")

clusters = pg_cur.fetchall()

print(f"\nTotal duplicate clusters: {len(clusters)}")
print(f"Total refunds in clusters: {sum(row[2] for row in clusters)}")

# Categorize duplicates
print("\n" + "=" * 80)
print("DUPLICATE CATEGORIES")
print("=" * 80)

category_counts = {
    'cross_source_import': 0,  # payments.table + Square items CSV
    'same_source_duplicate': 0,  # Both from payments.table or both from items CSV
    'same_charter_linked': 0,  # Both linked to same charter (true duplicate)
    'different_charter_linked': 0,  # Linked to different charters (separate transactions)
    'mixed_linked_unlinked': 0,  # One linked, one unlinked
    'both_unlinked': 0  # Both unlinked
}

deletable_duplicates = []
linkable_duplicates = []

for cluster in clusters:
    date, amount, count, ids, reserves, charter_ids, sources, square_ids = cluster
    
    id_list = ids.split(', ')
    source_list = sources.split(' | ')
    charter_list = charter_ids.split(', ')
    reserve_list = reserves.split(', ')
    square_list = square_ids.split(', ')
    
    # Check if cross-source import
    has_payments_table = any('payments.table' in s for s in source_list)
    has_items_csv = any('items-' in s for s in source_list)
    
    if has_payments_table and has_items_csv:
        category_counts['cross_source_import'] += 1
        
        # These are import duplicates - can delete one
        # Keep payments.table version (older, more complete), delete items CSV version
        for i, source in enumerate(source_list):
            if 'items-' in source:
                deletable_duplicates.append({
                    'refund_id': int(id_list[i]),
                    'amount': float(amount),
                    'date': date,
                    'source': source,
                    'reason': 'Cross-source import duplicate (keeping payments.table version)',
                    'charter_id': charter_list[i]
                })
    
    elif len(set(source_list)) == 1:
        # Same source
        category_counts['same_source_duplicate'] += 1
        
        # Check if linked to same charter
        unique_charters = set([c for c in charter_list if c != 'NULL'])
        
        if len(unique_charters) == 1 and len(unique_charters) > 0:
            # Both linked to same charter - true duplicate
            category_counts['same_charter_linked'] += 1
            
            # Keep the first one, delete the rest
            for i in range(1, len(id_list)):
                deletable_duplicates.append({
                    'refund_id': int(id_list[i]),
                    'amount': float(amount),
                    'date': date,
                    'source': source_list[i],
                    'reason': f'Same charter duplicate (keeping ID {id_list[0]}, same charter {list(unique_charters)[0]})',
                    'charter_id': charter_list[i]
                })
        
        elif len(unique_charters) > 1:
            # Linked to different charters - separate transactions (DON'T DELETE)
            category_counts['different_charter_linked'] += 1
        
        else:
            # Both unlinked
            category_counts['both_unlinked'] += 1
    
    # Check if mixed linked/unlinked
    null_count = charter_list.count('NULL')
    if null_count > 0 and null_count < len(charter_list):
        category_counts['mixed_linked_unlinked'] += 1
        
        # Unlinked ones might be duplicates - can link them to same charter
        linked_charter = [c for c in charter_list if c != 'NULL'][0]
        linked_reserve = [r for i, r in enumerate(reserve_list) if charter_list[i] != 'NULL'][0]
        
        for i, charter in enumerate(charter_list):
            if charter == 'NULL':
                linkable_duplicates.append({
                    'refund_id': int(id_list[i]),
                    'amount': float(amount),
                    'date': date,
                    'source': source_list[i],
                    'link_to_charter': linked_charter,
                    'link_to_reserve': linked_reserve if linked_reserve != 'NULL' else None
                })

print("\nDuplicate Category Breakdown:")
print(f"  Cross-source imports (payments.table + items CSV): {category_counts['cross_source_import']} clusters")
print(f"  Same source duplicates: {category_counts['same_source_duplicate']} clusters")
print(f"    - Both linked to SAME charter: {category_counts['same_charter_linked']} (TRUE DUPLICATES)")
print(f"    - Linked to DIFFERENT charters: {category_counts['different_charter_linked']} (SEPARATE TRANSACTIONS)")
print(f"  Mixed linked/unlinked: {category_counts['mixed_linked_unlinked']} clusters")
print(f"  Both unlinked: {category_counts['both_unlinked']} clusters")

print("\n" + "=" * 80)
print("SAFE TO DELETE")
print("=" * 80)
print(f"\nFound {len(deletable_duplicates)} refunds safe to delete:")

if deletable_duplicates:
    # Group by reason
    by_reason = {}
    for dup in deletable_duplicates:
        reason = dup['reason'].split(' (')[0]
        by_reason[reason] = by_reason.get(reason, 0) + 1
    
    print("\nDeletable duplicates by reason:")
    for reason, count in by_reason.items():
        print(f"  {reason}: {count} refunds")
    
    total_deletable_amount = sum(dup['amount'] for dup in deletable_duplicates)
    print(f"\nTotal amount in deletable duplicates: ${total_deletable_amount:,.2f}")
    
    print("\nTop 20 deletable duplicates:")
    print(f"{'Refund ID':<10} {'Amount':<12} {'Date':<12} {'Reason':<50}")
    print("-" * 90)
    for dup in sorted(deletable_duplicates, key=lambda x: x['amount'], reverse=True)[:20]:
        reason_short = dup['reason'][:47] + '...' if len(dup['reason']) > 50 else dup['reason']
        print(f"{dup['refund_id']:<10} ${dup['amount']:<11,.2f} {dup['date']} {reason_short:<50}")

print("\n" + "=" * 80)
print("CAN BE LINKED (Instead of Deleted)")
print("=" * 80)
print(f"\nFound {len(linkable_duplicates)} unlinked refunds that can be linked:")

if linkable_duplicates:
    print("\nLinkable duplicates:")
    print(f"{'Refund ID':<10} {'Amount':<12} {'Date':<12} {'Link to Charter':<15}")
    print("-" * 60)
    for dup in sorted(linkable_duplicates, key=lambda x: x['amount'], reverse=True)[:20]:
        print(f"{dup['refund_id']:<10} ${dup['amount']:<11,.2f} {dup['date']} {dup['link_to_charter']:<15}")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("\n1. SAFE TO DELETE:")
print(f"   - {len([d for d in deletable_duplicates if 'Cross-source' in d['reason']])} cross-source import duplicates")
print(f"   - {len([d for d in deletable_duplicates if 'Same charter' in d['reason']])} same-charter duplicates")
print(f"   Total: {len(deletable_duplicates)} refunds can be safely deleted")

print("\n2. SHOULD BE LINKED (not deleted):")
print(f"   - {len(linkable_duplicates)} unlinked refunds have linked duplicates")
print(f"   - These should be linked to same charter, not deleted")

print("\n3. KEEP AS-IS:")
print(f"   - {category_counts['different_charter_linked']} clusters linked to DIFFERENT charters")
print(f"   - These are legitimate separate transactions, not duplicates")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("Create two scripts:")
print("  1. link_duplicate_refunds.py - Link unlinked duplicates to same charter")
print("  2. delete_true_duplicates.py - Delete cross-source and same-charter duplicates")

pg_cur.close()
pg_conn.close()
