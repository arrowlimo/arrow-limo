import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=" * 80)
print("MASTER_RELATIONSHIPS DATA INTEGRITY VERIFICATION")
print("=" * 80)
print()

# Check charter relationships
print("1. CHARTER RELATIONSHIPS:")
print("-" * 80)

cur.execute("""
    SELECT COUNT(DISTINCT source_id) 
    FROM master_relationships 
    WHERE source_table = 'charters'
""")
charter_refs = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charters")
total_charters = cur.fetchone()[0]

print(f"Charters referenced in relationships: {charter_refs:,}")
print(f"Total charters in database: {total_charters:,}")
print(f"Coverage: {(charter_refs/total_charters*100):.1f}%")

# Check for orphaned charter references
cur.execute("""
    SELECT COUNT(*) 
    FROM master_relationships mr
    WHERE mr.source_table = 'charters'
    AND NOT EXISTS (
        SELECT 1 FROM charters c 
        WHERE c.charter_id = mr.source_id
    )
""")
orphaned_charters = cur.fetchone()[0]
print(f"Orphaned charter references: {orphaned_charters:,}")

print()

# Check payment relationships
print("2. PAYMENT RELATIONSHIPS:")
print("-" * 80)

cur.execute("""
    SELECT COUNT(DISTINCT target_id) 
    FROM master_relationships 
    WHERE target_table = 'payments'
""")
payment_refs = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM payments")
total_payments = cur.fetchone()[0]

print(f"Payments referenced in relationships: {payment_refs:,}")
print(f"Total payments in database: {total_payments:,}")
print(f"Coverage: {(payment_refs/total_payments*100):.1f}%")

# Check for orphaned payment references
cur.execute("""
    SELECT COUNT(*) 
    FROM master_relationships mr
    WHERE mr.target_table = 'payments'
    AND NOT EXISTS (
        SELECT 1 FROM payments p 
        WHERE p.payment_id = mr.target_id
    )
""")
orphaned_payments = cur.fetchone()[0]
print(f"Orphaned payment references: {orphaned_payments:,}")

print()

# Check relationship types
print("3. RELATIONSHIP TYPE BREAKDOWN:")
print("-" * 80)

cur.execute("""
    SELECT relationship_type, COUNT(*) as cnt
    FROM master_relationships
    GROUP BY relationship_type
    ORDER BY cnt DESC
""")

for rel_type, cnt in cur.fetchall():
    print(f"  {rel_type:<40} {cnt:>10,}")

print()

# Check match methods
print("4. MATCH METHOD BREAKDOWN:")
print("-" * 80)

cur.execute("""
    SELECT match_method, COUNT(*) as cnt
    FROM master_relationships
    GROUP BY match_method
    ORDER BY cnt DESC
""")

for method, cnt in cur.fetchall():
    print(f"  {method:<40} {cnt:>10,}")

print()

# Check confidence levels
print("5. MATCH CONFIDENCE DISTRIBUTION:")
print("-" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN match_confidence = 1.00 THEN 'Perfect (1.00)'
            WHEN match_confidence >= 0.90 THEN 'High (0.90-0.99)'
            WHEN match_confidence >= 0.70 THEN 'Medium (0.70-0.89)'
            ELSE 'Low (<0.70)'
        END as confidence_level,
        COUNT(*) as cnt
    FROM master_relationships
    GROUP BY 
        CASE 
            WHEN match_confidence = 1.00 THEN 'Perfect (1.00)'
            WHEN match_confidence >= 0.90 THEN 'High (0.90-0.99)'
            WHEN match_confidence >= 0.70 THEN 'Medium (0.70-0.89)'
            ELSE 'Low (<0.70)'
        END
    ORDER BY 
        CASE 
            WHEN MIN(match_confidence) = 1.00 THEN 1
            WHEN MIN(match_confidence) >= 0.90 THEN 2
            WHEN MIN(match_confidence) >= 0.70 THEN 3
            ELSE 4
        END
""")

total_rels = 766565
for level, cnt in cur.fetchall():
    pct = (cnt / total_rels) * 100
    print(f"  {level:<30} {cnt:>10,} ({pct:>5.1f}%)")

print()
print("=" * 80)
print("INTEGRITY SUMMARY")
print("=" * 80)

if orphaned_charters == 0 and orphaned_payments == 0:
    print("✅ All relationships are valid - no orphaned references")
else:
    print(f"⚠️  Found issues:")
    if orphaned_charters > 0:
        print(f"   - {orphaned_charters:,} orphaned charter references")
    if orphaned_payments > 0:
        print(f"   - {orphaned_payments:,} orphaned payment references")

conn.close()
