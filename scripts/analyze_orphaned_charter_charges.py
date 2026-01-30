"""
Check if orphaned charter_charges are linked to CANCELLED charters.
If they are, they should be deleted (cancelled runs don't have charges).
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
conn.autocommit = False
cur = conn.cursor()

print("=" * 80)
print("CHARTER_CHARGES ORPHANED ANALYSIS")
print("=" * 80)

# Check orphaned charges by reserve_number
cur.execute("""
    SELECT 
        cc.reserve_number,
        c.cancelled,
        c.charter_date,
        COUNT(cc.charge_id) as charge_count,
        SUM(cc.amount) as total_charges
    FROM charter_charges cc
    LEFT JOIN charters c ON c.reserve_number = cc.reserve_number
    GROUP BY cc.reserve_number, c.cancelled, c.charter_date
    ORDER BY c.cancelled DESC NULLS FIRST, charge_count DESC
""")

results = cur.fetchall()

no_charter = []
cancelled_charter = []
active_charter = []

for reserve, cancelled, charter_date, count, total in results:
    if cancelled is None:
        no_charter.append((reserve, count, total))
    elif cancelled:
        cancelled_charter.append((reserve, count, total, charter_date))
    else:
        active_charter.append((reserve, count, total, charter_date))

print(f"\nCharter_charges breakdown:")
print(f"  Linked to NO charter: {len(no_charter)} reserves, {sum(x[1] for x in no_charter):,} charges")
print(f"  Linked to CANCELLED charters: {len(cancelled_charter)} reserves, {sum(x[1] for x in cancelled_charter):,} charges")
print(f"  Linked to ACTIVE charters: {len(active_charter)} reserves, {sum(x[1] for x in active_charter):,} charges")

# Show sample of charges linked to cancelled charters
if cancelled_charter:
    print(f"\n📋 Sample charges linked to CANCELLED charters (top 10):")
    for reserve, count, total, charter_date in cancelled_charter[:10]:
        print(f"  {reserve} ({charter_date}): {count} charges, ${total:.2f}")

# Show sample of charges with NO charter
if no_charter:
    print(f"\n📋 Sample charges with NO matching charter (top 10):")
    for reserve, count, total in no_charter[:10]:
        print(f"  {reserve}: {count} charges, ${total:.2f}")

# VERDICT
print("\n" + "=" * 80)
print("DELETION PLAN")
print("=" * 80)

if cancelled_charter:
    total_cancelled_charges = sum(x[1] for x in cancelled_charter)
    total_cancelled_amount = sum(x[2] for x in cancelled_charter)
    print(f"\n🔴 DELETE charges for CANCELLED charters:")
    print(f"   {total_cancelled_charges:,} charges totaling ${total_cancelled_amount:,.2f}")
    print(f"   Reason: Cancelled charters should have NO charges")
    
    # Count affected charge_ids
    cur.execute("""
        SELECT COUNT(cc.charge_id)
        FROM charter_charges cc
        JOIN charters c ON c.reserve_number = cc.reserve_number
        WHERE c.cancelled = TRUE
    """)
    charge_ids_to_delete = cur.fetchone()[0]
    print(f"   Charge IDs to delete: {charge_ids_to_delete:,}")

if no_charter:
    total_orphan_charges = sum(x[1] for x in no_charter)
    total_orphan_amount = sum(x[2] for x in no_charter)
    print(f"\n⚠️  REVIEW charges with NO charter:")
    print(f"   {total_orphan_charges:,} charges totaling ${total_orphan_amount:,.2f}")
    print(f"   Action: Check if these reserve_numbers exist with typos or were deleted")

# Ask for confirmation before deleting
if cancelled_charter:
    print("\n" + "=" * 80)
    print("READY TO DELETE")
    print("=" * 80)
    print(f"\nWould delete {charge_ids_to_delete:,} charges for cancelled charters")
    print("This script is in DRY-RUN mode - no changes made")
    print("\nTo execute deletion, run: python scripts/delete_cancelled_charter_charges.py --execute")

cur.close()
conn.close()
