import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("="*80)
print("COMPREHENSIVE CLEANUP SUMMARY - Phases 1, 2A, 2B, 2C, 2D")
print("="*80)

# Overall statistics
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
total_count, total_amount = cur.fetchone()
print(f"\nCurrent receipts: {total_count:,} (${total_amount:,.2f})")

# Employee transfers (known good)
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE 'EMAIL TRANSFER%'
""")
emp_count, emp_amount = cur.fetchone()
print(f"Employee transfers: {emp_count:,} (${emp_amount:,.2f})")

# All backup tables
print("\n" + "="*80)
print("BACKUP TABLES (Full Recovery Available)")
print("="*80)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE 'receipts_backup_%'
    ORDER BY table_name
""")

total_backed_up = 0
total_backed_up_amount = 0

for (table_name,) in cur.fetchall():
    cur.execute(f"SELECT COUNT(*), SUM(gross_amount) FROM {table_name}")
    count, amount = cur.fetchone()
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{table_name}: {count:,} ({amount_str})")
    total_backed_up += count
    if amount:
        total_backed_up_amount += amount

print(f"\nTotal backed up: {total_backed_up:,} receipts (${total_backed_up_amount:,.2f})")

# Cleanup phases summary
print("\n" + "="*80)
print("CLEANUP PHASES COMPLETED")
print("="*80)

# Get counts from backup tables
phases = [
    ("Phase 1", "receipts_backup_phase1_cleanup_20260214_095706", "Payment processor settlements + duplicates"),
    ("Phase 2A", "receipts_backup_phase2a_interaccount_20260214_100939", "Inter-account transfers"),
    ("Phase 2B", "receipts_backup_phase2b_nonexpenses_20260214_102308", "Cash withdrawals + NSF fees"),
    ("Phase 2C", "receipts_backup_phase2c_misc_20260214_102840", "Additional withdrawals/deposits/CC payments"),
    ("Phase 2D", "receipts_backup_phase2d_ownerdraws_20260214_104516", "Owner draws + loan payments")
]

print(f"\n{'Phase':<10} {'Count':>8} {'Amount':>15} {'Description'}")
print("-"*80)

total_deleted = 0
total_deleted_amount = 0

for phase_name, table_name, description in phases:
    try:
        cur.execute(f"SELECT COUNT(*), SUM(gross_amount) FROM {table_name}")
        count, amount = cur.fetchone()
        amount_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{phase_name:<10} {count:>8,} {amount_str:>14} {description}")
        total_deleted += count
        if amount:
            total_deleted_amount += amount
    except:
        print(f"{phase_name:<10} {'N/A':>8} {'N/A':>14} {description}")

print("-"*80)
print(f"{'TOTAL':<10} {total_deleted:>8,} ${total_deleted_amount:>13,.2f}")

# Top vendors in current data
print("\n" + "="*80)
print("TOP 25 VENDORS (Current Data)")
print("="*80)

cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC NULLS LAST
    LIMIT 25
""")

print(f"\n{'Vendor':<50} {'Count':>6} {'Amount':>15}")
print("-"*80)

for vendor, count, amount in cur.fetchall():
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    vendor_short = vendor[:48] if len(vendor) > 48 else vendor
    print(f"{vendor_short:<50} {count:>6,} {amount_str:>14}")

# Categories breakdown
print("\n" + "="*80)
print("CATEGORIES BREAKDOWN")
print("="*80)

cur.execute("""
    SELECT 
        CASE 
            WHEN category IS NULL THEN 'None'
            ELSE category
        END as cat,
        COUNT(*), 
        SUM(gross_amount)
    FROM receipts
    GROUP BY category
    ORDER BY SUM(gross_amount) DESC NULLS LAST
    LIMIT 20
""")

print(f"\n{'Category':<40} {'Count':>6} {'Amount':>15}")
print("-"*80)

for category, count, amount in cur.fetchall():
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{category:<40} {count:>6,} {amount_str:>14}")

# Next steps
print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)

print("\n1. UNCATEGORIZED RECEIPTS (~12,500 receipts)")
print("   - None category: ~4,167 receipts ($1.2M)")
print("   - Unknown category: ~1,933 receipts ($1.1M)")
print("   - BANKING category: ~3,515 receipts ($1.3M)")
print("   - TRANSFERS category: ~2,783 receipts ($353K)")
print("   Action: Categorize as legitimate vendor expenses")

print("\n2. MERCHANT FEES (~34 receipts, ~$23K)")
print("   - GLOBAL MERCHANT FEES")
print("   - MASTERCARD/VISA MERCHANT FEE")
print("   Question: Are these service fees (expense) or settlements (not expense)?")

print("\n3. REVENUE STRUCTURE")
print("   - Move charter_charges data to income tracking")
print("   - Build A/R aging report (invoiced vs paid)")
print("   - Create payment processor reconciliation dashboard")

print("\n4. FINAL GOAL")
print("   Receipts table should contain ONLY:")
print("   - Vendor expenses (HEFFNER, ERLES, WOODRIDGE FORD, etc.)")
print("   - Employee reimbursements (EMAIL TRANSFER entries)")
print("   - Operating expenses (insurance, fuel, maintenance, beverages)")

conn.close()
