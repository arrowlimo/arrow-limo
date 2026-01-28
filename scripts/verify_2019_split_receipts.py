#!/usr/bin/env python3
"""
Verify 2019 split receipts - parent/child relationships and totals.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("2019 SPLIT RECEIPTS VERIFICATION")
print("=" * 100)

# Overall split receipt stats for 2019
cur.execute("""
    SELECT 
        COUNT(*) as total_split_receipts,
        COUNT(CASE WHEN parent_receipt_id IS NULL THEN 1 END) as parents,
        COUNT(CASE WHEN parent_receipt_id IS NOT NULL THEN 1 END) as children,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
    AND is_split_receipt = TRUE
    AND exclude_from_reports = FALSE
""")

total_split, parents, children, total_amt = cur.fetchone()

print(f"\n2019 SPLIT RECEIPT SUMMARY:")
print(f"  Total split receipts: {total_split}")
print(f"  Parent receipts: {parents}")
print(f"  Child receipts: {children}")
print(f"  Total amount: ${total_amt:,.2f}")

if parents + children == total_split:
    print(f"  ✅ Parent + Children = Total ({parents} + {children} = {total_split})")
else:
    print(f"  ⚠️  Mismatch: {parents} + {children} ≠ {total_split}")

# Verify each parent has correct children
print("\n" + "=" * 100)
print("PARENT-CHILD RELATIONSHIP VERIFICATION")
print("=" * 100)

cur.execute("""
    SELECT 
        p.receipt_id as parent_id,
        p.receipt_date,
        p.vendor_name,
        p.gross_amount as parent_amount,
        p.split_group_total,
        COUNT(c.receipt_id) as child_count,
        SUM(c.gross_amount) as children_total
    FROM receipts p
    LEFT JOIN receipts c ON c.parent_receipt_id = p.receipt_id
    WHERE p.is_split_receipt = TRUE
    AND p.parent_receipt_id IS NULL
    AND EXTRACT(YEAR FROM p.receipt_date) = 2019
    AND p.exclude_from_reports = FALSE
    GROUP BY p.receipt_id, p.receipt_date, p.vendor_name, p.gross_amount, p.split_group_total
    ORDER BY p.receipt_date, p.split_group_total
""")

parents_data = cur.fetchall()

print(f"\nFound {len(parents_data)} parent receipts\n")

issues = 0
for parent_id, date, vendor, parent_amt, split_total, child_count, children_total in parents_data:
    calculated_total = parent_amt + (children_total or 0)
    match = "✓" if abs(calculated_total - split_total) < 0.01 else "✗"
    
    if abs(calculated_total - split_total) >= 0.01:
        issues += 1
        print(f"{match} Parent #{parent_id} | {date} | {vendor}")
        print(f"    Split total: ${split_total:.2f}")
        print(f"    Parent: ${parent_amt:.2f} + Children ({child_count}): ${children_total:.2f} = ${calculated_total:.2f}")
        print(f"    ⚠️  MISMATCH: ${abs(calculated_total - split_total):.2f} difference")
        print()

if issues == 0:
    print("✅ All parent-child totals match split_group_total")
else:
    print(f"⚠️  Found {issues} mismatches")

# Show sample split receipt groups
print("\n" + "=" * 100)
print("SAMPLE SPLIT RECEIPT GROUPS (First 10)")
print("=" * 100)

cur.execute("""
    WITH parent_groups AS (
        SELECT 
            p.receipt_id as parent_id,
            p.receipt_date,
            p.vendor_name,
            p.gross_amount as parent_amount,
            p.split_group_total,
            p.split_key,
            p.description as parent_desc
        FROM receipts p
        WHERE p.is_split_receipt = TRUE
        AND p.parent_receipt_id IS NULL
        AND EXTRACT(YEAR FROM p.receipt_date) = 2019
        AND p.exclude_from_reports = FALSE
        ORDER BY p.receipt_date
        LIMIT 10
    )
    SELECT 
        pg.parent_id,
        pg.receipt_date,
        pg.vendor_name,
        pg.parent_amount,
        pg.split_group_total,
        pg.parent_desc,
        c.receipt_id as child_id,
        c.gross_amount as child_amount,
        c.description as child_desc
    FROM parent_groups pg
    LEFT JOIN receipts c ON c.parent_receipt_id = pg.parent_id
    ORDER BY pg.receipt_date, pg.parent_id, c.receipt_id
""")

current_parent = None
for row in cur.fetchall():
    parent_id, date, vendor, parent_amt, split_total, parent_desc, child_id, child_amt, child_desc = row
    
    if parent_id != current_parent:
        if current_parent is not None:
            print()
        print(f"\n{date} | {vendor} | SPLIT/${split_total}")
        print(f"  Parent #{parent_id}: ${parent_amt:.2f}")
        if parent_desc and 'SPLIT/' in parent_desc:
            print(f"    Description: {parent_desc}")
        current_parent = parent_id
    
    if child_id:
        print(f"    Child #{child_id}: ${child_amt:.2f}")
        if child_desc and 'SPLIT/' in child_desc:
            print(f"      Description: {child_desc}")

# Check for orphaned children (children without valid parent)
print("\n" + "=" * 100)
print("ORPHANED CHILDREN CHECK")
print("=" * 100)

cur.execute("""
    SELECT 
        c.receipt_id,
        c.receipt_date,
        c.vendor_name,
        c.gross_amount,
        c.parent_receipt_id,
        c.description
    FROM receipts c
    LEFT JOIN receipts p ON p.receipt_id = c.parent_receipt_id
    WHERE c.parent_receipt_id IS NOT NULL
    AND EXTRACT(YEAR FROM c.receipt_date) = 2019
    AND c.exclude_from_reports = FALSE
    AND p.receipt_id IS NULL
""")

orphans = cur.fetchall()

if orphans:
    print(f"\n⚠️  Found {len(orphans)} orphaned children (parent doesn't exist):")
    for receipt_id, date, vendor, amount, parent_id, desc in orphans:
        print(f"  #{receipt_id} | {date} | {vendor} | ${amount:.2f}")
        print(f"    Points to non-existent parent #{parent_id}")
else:
    print("\n✅ No orphaned children - all parent_receipt_ids are valid")

# Banking linkage for split receipts
print("\n" + "=" * 100)
print("BANKING LINKAGE FOR SPLIT RECEIPTS")
print("=" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN parent_receipt_id IS NULL THEN 'Parent'
            ELSE 'Child'
        END as receipt_type,
        COUNT(*) as total,
        COUNT(banking_transaction_id) as with_banking,
        COUNT(*) - COUNT(banking_transaction_id) as without_banking
    FROM receipts
    WHERE is_split_receipt = TRUE
    AND EXTRACT(YEAR FROM receipt_date) = 2019
    AND exclude_from_reports = FALSE
    GROUP BY CASE WHEN parent_receipt_id IS NULL THEN 'Parent' ELSE 'Child' END
""")

banking_stats = cur.fetchall()

print(f"\n{'Type':<10} {'Total':<10} {'With Banking':<15} {'Without Banking':<15}")
print("-" * 50)
for receipt_type, total, with_bank, without_bank in banking_stats:
    print(f"{receipt_type:<10} {total:<10} {with_bank:<15} {without_bank:<15}")

print("\nℹ️  Children typically don't have banking_transaction_id (manual split entries)")
print("   Only the parent should link to the banking transaction")

# Final summary
print("\n" + "=" * 100)
print("FINAL VERIFICATION")
print("=" * 100)

cur.execute("""
    SELECT COUNT(DISTINCT split_key) 
    FROM receipts 
    WHERE is_split_receipt = TRUE 
    AND EXTRACT(YEAR FROM receipt_date) = 2019
    AND exclude_from_reports = FALSE
""")

unique_groups = cur.fetchone()[0]

print(f"\n✅ 2019 Split Receipt Summary:")
print(f"   {total_split} total split receipts")
print(f"   {parents} physical receipts (parent records)")
print(f"   {children} component breakdowns (child records)")
print(f"   {unique_groups} unique split groups")
print(f"   Total value: ${total_amt:,.2f}")

if parents == children and parents == unique_groups:
    print(f"\n✅ PERFECT: {parents} parents = {children} children = {unique_groups} groups")
else:
    print(f"\n⚠️  Structure: {parents} parents, {children} children, {unique_groups} groups")

cur.close()
conn.close()

print("\n" + "=" * 100)
