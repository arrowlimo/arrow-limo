import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 80)
print("CHARTER_CHARGES TABLE RELATIONSHIPS")
print("=" * 80)

# Check foreign keys FROM charter_charges TO other tables
cur.execute("""
    SELECT
        tc.constraint_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'charter_charges'
""")

fks = cur.fetchall()
print("\nForeign keys FROM charter_charges:")
if fks:
    for constraint, column, foreign_table, foreign_column in fks:
        print(f"  {column} → {foreign_table}.{foreign_column} ({constraint})")
else:
    print("  ❌ NO FOREIGN KEYS - charter_charges is NOT linked to charters!")

# Check if charter_id actually links to charters
cur.execute("""
    SELECT COUNT(*) 
    FROM charter_charges cc
    LEFT JOIN charters c ON c.charter_id = cc.charter_id
    WHERE c.charter_id IS NULL
""")
orphaned_by_id = cur.fetchone()[0]

# Check if reserve_number links to charters
cur.execute("""
    SELECT COUNT(*) 
    FROM charter_charges cc
    LEFT JOIN charters c ON c.reserve_number = cc.reserve_number
    WHERE c.reserve_number IS NULL
""")
orphaned_by_reserve = cur.fetchone()[0]

print(f"\nOrphaned charges (no matching charter):")
print(f"  By charter_id: {orphaned_by_id:,}")
print(f"  By reserve_number: {orphaned_by_reserve:,}")

# Sample a few charter_charges to see structure
print("\n" + "=" * 80)
print("SAMPLE CHARTER_CHARGES RECORDS")
print("=" * 80)

cur.execute("""
    SELECT 
        cc.reserve_number,
        cc.charter_id,
        cc.description,
        cc.amount,
        cc.charge_type,
        c.total_amount_due
    FROM charter_charges cc
    LEFT JOIN charters c ON c.reserve_number = cc.reserve_number
    WHERE cc.amount > 0
    ORDER BY cc.created_at DESC
    LIMIT 5
""")

print("\nRecent charges:")
for reserve, charter_id, desc, amt, ctype, charter_total in cur.fetchall():
    print(f"  {reserve}: {desc} ${amt:.2f} ({ctype}) | Charter total: ${charter_total if charter_total else 0:.2f}")

# Check if a charter with charges has matching line items
print("\n" + "=" * 80)
print("EXAMPLE: Charter with charges breakdown")
print("=" * 80)

cur.execute("""
    SELECT c.reserve_number, c.total_amount_due, c.charter_date, COUNT(cc.charge_id) as charge_count, SUM(cc.amount) as charges_sum
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.reserve_number = c.reserve_number
    WHERE c.total_amount_due > 0
    AND c.cancelled = FALSE
    GROUP BY c.reserve_number, c.total_amount_due, c.charter_date
    HAVING COUNT(cc.charge_id) > 0
    ORDER BY c.charter_date DESC
    LIMIT 1
""")

result = cur.fetchone()
if result:
    reserve, total, charter_date, count, charges_sum = result
    print(f"\nReserve: {reserve}")
    print(f"  Charter total_amount_due: ${total:.2f}")
    print(f"  Charge line items: {count}")
    print(f"  Sum of charges: ${charges_sum:.2f}")
    print(f"  Match: {'✅ YES' if abs(total - (charges_sum or 0)) <= 0.01 else '❌ NO'}")
    
    # Show the line items
    cur.execute("""
        SELECT description, amount, charge_type
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY sequence
    """, (reserve,))
    
    print(f"\n  Line items:")
    for desc, amt, ctype in cur.fetchall():
        print(f"    - {desc}: ${amt:.2f} ({ctype})")

# VERDICT
print("\n" + "=" * 80)
print("VERDICT: Is charter_charges the invoice line item table?")
print("=" * 80)

if not fks:
    print("\n❌ NO FK CONSTRAINT - charter_charges is not properly linked!")
    print("   Without FK, this table is unreliable for invoice line items")

if orphaned_by_reserve > 0:
    print(f"\n❌ {orphaned_by_reserve:,} orphaned charges (no matching charter)")

if result and abs(total - (charges_sum or 0)) > 0.01:
    print(f"\n❌ Charter totals DON'T match charge line items")
    print("   This table does NOT represent actual invoice charges")
else:
    print(f"\n✅ Charter totals MATCH charge line items")
    print("   This table DOES represent invoice line items")
    print("   BUT: Check if it's complete (some charters may have $0 in charges)")

cur.close()
conn.close()
