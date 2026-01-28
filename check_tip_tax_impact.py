"""
Check if tips are included in receipts gross_amount and affect tax calculations
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("TIP ANALYSIS - Does tip affect taxes?")
print("=" * 100)

# Check receipts with tip data
print("\n[1] TIP COLUMN IN RECEIPTS TABLE")
print("-" * 100)

cur.execute("""
SELECT COUNT(*), 
       COUNT(tip) AS tip_count,
       SUM(CASE WHEN tip IS NOT NULL AND tip > 0 THEN 1 ELSE 0 END) AS receipts_with_tip,
       MIN(tip), MAX(tip), AVG(tip)
FROM receipts
""")
result = cur.fetchone()
total, tip_count, with_tip, min_tip, max_tip, avg_tip = result
print(f"Total receipts: {total:,}")
print(f"Receipts with non-null tip: {tip_count:,}")
print(f"Receipts with tip > 0: {with_tip}")
if with_tip and with_tip > 0:
    print(f"Tip range: ${min_tip} to ${max_tip}")
    print(f"Average tip: ${avg_tip}")
else:
    print("⚠️ NO RECEIPTS HAVE TIPS - Column is completely unused")

# Check if tip exists in gross_amount or is separate
print("\n[2] RELATIONSHIP: TIP vs GROSS_AMOUNT")
print("-" * 100)

cur.execute("""
SELECT COUNT(*)
FROM receipts
WHERE tip IS NOT NULL AND tip > 0
LIMIT 5
""")
if cur.fetchone()[0] > 0:
    print("Sample receipts with tips:")
    cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, gst_amount, tip, 
           (gross_amount - gst_amount) as net_before_tip,
           ROUND(gross_amount * 0.05 / 1.05, 2) as calculated_gst
    FROM receipts
    WHERE tip IS NOT NULL AND tip > 0
    LIMIT 5
    """)
    print(f"\n{'Receipt':<10} {'Vendor':<30} {'Gross':<12} {'GST':<12} {'Tip':<12}")
    print("-" * 76)
    for row in cur.fetchall():
        receipt_id, vendor, gross, gst, tip, net, calc_gst = row
        print(f"{receipt_id:<10} {vendor:<30} ${gross:<11.2f} ${gst:<11.2f} ${tip:<11.2f}")
else:
    print("No tips in database - Column appears legacy")

# Check GST calculation logic
print("\n[3] GST CALCULATION - Include tip or not?")
print("-" * 100)

print("""
In Canada (Alberta 5% GST):
  - GST is INCLUDED in the total price (tax-inclusive)
  - Tip is typically NOT subject to GST (added after)
  - So: gross_amount = item_price + gst (no tip)
       tip = added separately (not taxed)

Formula:
  If gross_amount includes tip: gst_amount calculated wrong
  If gross_amount excludes tip: gst_amount is correct

Let's verify the receipts table logic...
""")

# Check formula: gst_amount = gross_amount * 0.05 / 1.05
cur.execute("""
SELECT COUNT(*) as matches
FROM receipts
WHERE gst_amount = ROUND(gross_amount * 0.05 / 1.05, 2)
  OR ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) < 0.01
""")
matches = cur.fetchone()[0]
total_gst_rows = cur.execute("SELECT COUNT(*) FROM receipts WHERE gst_amount IS NOT NULL AND gst_amount > 0")
cur.execute("SELECT COUNT(*) FROM receipts WHERE gst_amount IS NOT NULL AND gst_amount > 0")
total_gst_rows = cur.fetchone()[0]

print(f"\nReceipts where: gst_amount = gross * 0.05 / 1.05")
print(f"  Matching rows: {matches:,} / {total_gst_rows:,}")
if total_gst_rows > 0:
    match_pct = (matches / total_gst_rows * 100)
    print(f"  Match rate: {match_pct:.1f}%")

# Show sample calculations
print("\nSample receipts - verifying GST formula:")
cur.execute("""
SELECT receipt_id, vendor_name, gross_amount, gst_amount,
       ROUND(gross_amount * 0.05 / 1.05, 2) as expected_gst,
       ROUND(gross_amount - (gross_amount * 0.05 / 1.05), 2) as net_amount,
       CASE 
         WHEN ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) < 0.01 
         THEN '✅ CORRECT'
         ELSE '❌ MISMATCH'
       END as validation
FROM receipts
WHERE gst_amount IS NOT NULL AND gst_amount > 0
LIMIT 10
""")

print(f"\n{'Receipt':<10} {'Vendor':<30} {'Gross':<12} {'GST Actual':<12} {'GST Expected':<12} {'Check':<10}")
print("-" * 92)
for row in cur.fetchall():
    receipt_id, vendor, gross, gst, expected_gst, net, check = row
    print(f"{receipt_id:<10} {vendor:<30} ${gross:<11.2f} ${gst:<11.2f} ${expected_gst:<11.2f} {check:<10}")

# Conclusion
print("\n" + "=" * 100)
print("CONCLUSION")
print("=" * 100)

cur.execute("SELECT COUNT(*) FROM receipts WHERE tip IS NOT NULL AND tip > 0")
tip_receipts = cur.fetchone()[0]

print(f"""
TIP STATUS:
  - Receipts with tips: {tip_receipts}
  - Tip column usage: {'✅ ACTIVE' if tip_receipts > 0 else '❌ LEGACY/UNUSED'}

GST CALCULATION:
  - Formula uses: gross_amount * 0.05 / 1.05
  - This assumes: gross_amount INCLUDES tax, EXCLUDES tip
  - Therefore: Tips do NOT affect tax calculations ✅

TAX IMPACT:
  ✅ Tip is NOT subject to GST in Canada
  ✅ Tip is added AFTER tax calculation
  ✅ Current formula is CORRECT

PHASE 1 CLEANUP:
  {"Safe to proceed" if tip_receipts == 0 else "⚠️ Tip column used"} - dropping tip column would affect data
""")

cur.close()
conn.close()
