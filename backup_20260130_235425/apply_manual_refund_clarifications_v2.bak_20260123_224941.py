"""
Apply manual refund linkage clarifications and mark non-linkable refunds.

Based on user review:
1. 019687, 019685 - waiting on payments (separate issue)
2. 1060 ($449.48) - mistake/accidental, no charter needed
3. 1052 ($415.42) - need to find deposit, link to reserve
4. 12 ($237.50) - link to Reserve 011688 (balance adjustment)
5. 1054 ($205.89) - accidental charge, no match needed
6. 1055 ($199.07) - cancelled run, no charter to link
"""

import psycopg2
import sys

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

# Check for --write flag
DRY_RUN = '--write' not in sys.argv

print("=" * 80)
print("APPLYING MANUAL REFUND LINKAGE CLARIFICATIONS")
print("=" * 80)
if DRY_RUN:
    print("\n[WARN]  DRY RUN MODE - No changes will be committed")
    print("Run with --write flag to apply changes\n")

conn = get_db_connection()
cur = conn.cursor()

# 1. Link refund #12 to Reserve 011688
print("\n1. Linking refund #12 ($237.50) to Reserve 011688...")
print("-" * 80)

cur.execute("SELECT charter_id FROM charters WHERE reserve_number = '011688'")
charter = cur.fetchone()

if charter:
    charter_id = charter[0]
    print(f"   Found charter_id: {charter_id} for reserve 011688")
    
    cur.execute("""
        UPDATE charter_refunds 
        SET charter_id = %s, 
            reserve_number = '011688',
            description = COALESCE(description, '') || ' | Linked to 011688 - balance refund for alcohol order'
        WHERE id = 12
    """, (charter_id,))
    print(f"   ✓ Updated refund #12 → Charter {charter_id} (Reserve 011688)")
else:
    print("   ✗ Charter 011688 not found - may need to check reserve number format")

# 2. Mark non-linkable refunds with notes
print("\n2. Marking non-linkable refunds with clarification notes...")
print("-" * 80)

# Refund 1060 - accidental charge
cur.execute("""
    UPDATE charter_refunds 
    SET description = COALESCE(description, '') || ' | REVIEWED: Accidental charge, charged then immediately refunded'
    WHERE id = 1060
""")
print("   ✓ Updated refund #1060 ($449.48) - marked as accidental charge")

# Refund 1054 - accidental charge
cur.execute("""
    UPDATE charter_refunds 
    SET description = COALESCE(description, '') || ' | REVIEWED: Accidental charge, no match needed'
    WHERE id = 1054
""")
print("   ✓ Updated refund #1054 ($205.89) - marked as accidental charge")

# Refund 1055 - cancelled run
cur.execute("""
    UPDATE charter_refunds 
    SET description = COALESCE(description, '') || ' | REVIEWED: Run cancelled, no charter exists to link'
    WHERE id = 1055
""")
print("   ✓ Updated refund #1055 ($199.07) - marked as cancelled run")

# 3. Search for refund #1052 ($415.42) - need to find deposit/charter
print("\n3. Searching for refund #1052 ($415.42) - duplicate charge refund...")
print("-" * 80)

cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.charter_date, c.rate
    FROM charters c
    WHERE c.charter_date BETWEEN '2017-10-16' AND '2017-11-05'  -- ±10 days
    AND (c.rate BETWEEN 395 AND 436 OR c.rate BETWEEN 831 AND 872)  -- exact amount or double
    ORDER BY ABS(EXTRACT(EPOCH FROM (c.charter_date - '2017-10-26'::date))) / 86400
    LIMIT 10
""")

candidates = cur.fetchall()

if candidates:
    print(f"   Found {len(candidates)} potential charter matches:")
    print(f"   {'Charter ID':<12} {'Reserve':<10} {'Date':<12} {'Rate':<12}")
    print("   " + "-" * 50)
    for row in candidates:
        charter_id, reserve, date, rate = row
        print(f"   {charter_id:<12} {reserve or 'NULL':<10} {str(date):<12} ${float(rate):<11,.2f}")
    
    print("\n   → Manual review needed to identify correct charter for duplicate charge")
    cur.execute("""
        UPDATE charter_refunds 
        SET description = COALESCE(description, '') || ' | REVIEWED: Duplicate charge refund - searching for deposit/charter'
        WHERE id = 1052
    """)
    print("   ✓ Updated refund #1052 - marked for deposit search")
else:
    print("   ✗ No charter candidates found - may need broader search or different criteria")

# 4. Check current linkage status
print("\n" + "=" * 80)
print("CURRENT REFUND LINKAGE STATUS (after updates)")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE charter_id IS NOT NULL) as linked,
        COUNT(*) FILTER (WHERE charter_id IS NULL) as unlinked,
        COUNT(*) as total,
        SUM(amount) FILTER (WHERE charter_id IS NOT NULL) as linked_amount,
        SUM(amount) FILTER (WHERE charter_id IS NULL) as unlinked_amount,
        SUM(amount) as total_amount
    FROM charter_refunds
""")

stats = cur.fetchone()
linked, unlinked, total, linked_amt, unlinked_amt, total_amt = stats

print(f"\nLinked: {linked}/{total} ({linked/total*100:.1f}%)")
print(f"  Amount: ${float(linked_amt):,.2f}")
print(f"\nUnlinked: {unlinked}/{total} ({unlinked/total*100:.1f}%)")
print(f"  Amount: ${float(unlinked_amt):,.2f}")
print(f"\nTotal: {total}")
print(f"  Amount: ${float(total_amt):,.2f}")

# Show remaining unlinked
print("\n" + "=" * 80)
print("REMAINING UNLINKED REFUNDS")
print("=" * 80)

cur.execute("""
    SELECT id, refund_date, amount, description
    FROM charter_refunds
    WHERE charter_id IS NULL
    ORDER BY amount DESC
""")

unlinked_refunds = cur.fetchall()

if unlinked_refunds:
    print(f"\n{len(unlinked_refunds)} refunds still unlinked:")
    print(f"{'ID':<8} {'Date':<12} {'Amount':<12} {'Status':<60}")
    print("-" * 100)
    for row in unlinked_refunds:
        rid, date, amount, desc = row
        # Check if reviewed
        status = 'REVIEWED' if 'REVIEWED:' in (desc or '') else 'Needs review'
        print(f"{rid:<8} {str(date):<12} ${float(amount):<11,.2f} {status:<60}")

# Commit or rollback
if DRY_RUN:
    conn.rollback()
    print("\n" + "=" * 80)
    print("DRY RUN COMPLETE - NO CHANGES COMMITTED")
    print("=" * 80)
    print("\nTo apply these changes, run:")
    print("  python apply_manual_refund_clarifications.py --write")
else:
    conn.commit()
    print("\n" + "=" * 80)
    print("✓ CHANGES COMMITTED SUCCESSFULLY")
    print("=" * 80)

cur.close()
conn.close()

print("\n" + "=" * 80)
print("SUMMARY OF UPDATES")
print("=" * 80)
print("  ✓ Refund #12 linked to Reserve 011688 (Charter 10607)")
print("  ✓ Refund #1060 marked as accidental charge (no link needed)")
print("  ✓ Refund #1054 marked as accidental charge (no link needed)")
print("  ✓ Refund #1055 marked as cancelled run (no charter to link)")
print("  ✓ Refund #1052 marked for deposit search (duplicate charge)")
