"""
Identify duplicate clusters in charter_refunds.

Groups refunds by (amount, date) to find clusters with same values.
Useful for manual review to determine which are legitimate duplicates vs separate transactions.
"""

import psycopg2
from decimal import Decimal

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

print("=" * 80)
print("DUPLICATE CLUSTER ANALYSIS: charter_refunds")
print("=" * 80)

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

# Find groups with same amount and date
pg_cur.execute("""
    SELECT 
        refund_date,
        amount,
        COUNT(*) as refund_count,
        STRING_AGG(CAST(id AS TEXT), ', ' ORDER BY id) as refund_ids,
        STRING_AGG(COALESCE(reserve_number, 'NULL'), ', ' ORDER BY id) as reserves,
        STRING_AGG(COALESCE(CAST(charter_id AS TEXT), 'NULL'), ', ' ORDER BY id) as charter_ids,
        STRING_AGG(COALESCE(source_file, 'Unknown'), ' | ' ORDER BY id) as sources
    FROM charter_refunds
    GROUP BY refund_date, amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, amount DESC
""")

clusters = pg_cur.fetchall()

print(f"\nFound {len(clusters)} duplicate clusters (same amount + date)")
print(f"Total refunds in clusters: {sum(row[2] for row in clusters)}")

if clusters:
    print("\n" + "=" * 80)
    print("DUPLICATE CLUSTERS")
    print("=" * 80)
    
    for i, cluster in enumerate(clusters, 1):
        date, amount, count, ids, reserves, charter_ids, sources = cluster
        
        print(f"\n{'=' * 80}")
        print(f"Cluster #{i}: {count} refunds with same amount and date")
        print(f"{'=' * 80}")
        print(f"Date: {date}")
        print(f"Amount: ${float(amount):,.2f}")
        print(f"Refund IDs: {ids}")
        print(f"Reserve Numbers: {reserves}")
        print(f"Charter IDs: {charter_ids}")
        print(f"Sources: {sources[:100]}" + ('...' if len(sources) > 100 else ''))
        
        # Analyze cluster
        id_list = ids.split(', ')
        reserve_list = reserves.split(', ')
        charter_list = charter_ids.split(', ')
        
        # Count NULLs
        null_reserves = reserve_list.count('NULL')
        null_charters = charter_list.count('NULL')
        
        # Check if all point to same charter
        unique_charters = set([c for c in charter_list if c != 'NULL'])
        
        print(f"\nAnalysis:")
        print(f"  - {null_reserves}/{count} have NULL reserve_number")
        print(f"  - {null_charters}/{count} have NULL charter_id")
        if unique_charters:
            print(f"  - Linked to {len(unique_charters)} unique charter(s): {', '.join(unique_charters)}")
        else:
            print(f"  - None are linked to charters")
        
        # Recommendation
        print(f"\nRecommendation:")
        if null_reserves == 0 and null_charters == 0:
            if len(unique_charters) == 1:
                print(f"  [WARN]  All {count} refunds linked to SAME charter - likely true duplicates")
                print(f"  → Manual review needed - may want to keep only 1")
            else:
                print(f"  ✓ All {count} refunds linked to DIFFERENT charters - legitimate separate transactions")
        elif null_reserves == count and null_charters == count:
            print(f"  [WARN]  All {count} refunds are UNLINKED - need reserve numbers to determine if duplicates")
        else:
            print(f"  [WARN]  Mixed linked/unlinked - unlinked ones may be duplicates of linked ones")
            print(f"  → Check if unlinked refunds should use same charter_id as linked ones")

# Summary by cluster size
print("\n" + "=" * 80)
print("CLUSTER SIZE DISTRIBUTION")
print("=" * 80)

pg_cur.execute("""
    SELECT 
        cluster_size,
        COUNT(*) as cluster_count,
        SUM(cluster_size) as total_refunds
    FROM (
        SELECT COUNT(*) as cluster_size
        FROM charter_refunds
        GROUP BY refund_date, amount
        HAVING COUNT(*) > 1
    ) subq
    GROUP BY cluster_size
    ORDER BY cluster_size DESC
""")

distribution = pg_cur.fetchall()

if distribution:
    print(f"\n{'Cluster Size':<15} {'# of Clusters':<15} {'Total Refunds':<15}")
    print("-" * 50)
    for row in distribution:
        size, cluster_count, total_refunds = row
        print(f"{size:<15} {cluster_count:<15} {total_refunds:<15}")

# Check for specific high-value amounts
print("\n" + "=" * 80)
print("HIGH-VALUE DUPLICATE CLUSTERS (>$500)")
print("=" * 80)

high_value_clusters = [c for c in clusters if float(c[1]) > 500]

if high_value_clusters:
    print(f"\nFound {len(high_value_clusters)} high-value duplicate clusters:")
    for cluster in high_value_clusters[:10]:
        date, amount, count, ids, reserves, charter_ids, sources = cluster
        print(f"  ${float(amount):,.2f} x {count} on {date} (IDs: {ids})")
else:
    print("No high-value duplicate clusters found")

pg_cur.close()
pg_conn.close()

print("\n" + "=" * 80)
print("DUPLICATE CLUSTER ANALYSIS COMPLETE")
print("=" * 80)
print("\nNext steps:")
print("  1. Review clusters with ALL refunds linked to SAME charter (likely true duplicates)")
print("  2. Check mixed linked/unlinked clusters - unlinked may be duplicates")
print("  3. For unlinked clusters, use safe_link_lms_deposit_refunds.py to find reserve numbers")
print("  4. Manual review of high-value clusters (>$500)")
