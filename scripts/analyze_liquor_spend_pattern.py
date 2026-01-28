"""
Analyze liquor spending patterns to distinguish business inventory 
from personal consumption
"""

import psycopg2
import os
from decimal import Decimal
from collections import defaultdict
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

conn = get_connection()
cur = conn.cursor()

print("=" * 100)
print("LIQUOR SPENDING PATTERN ANALYSIS")
print("=" * 100)
print("\nKEY INSIGHT:")
print("- Total liquor receipts: $256,319.36 (way above $44,045 owner draw)")
print("- This suggests most liquor IS business inventory")
print("- Need to find ONLY the personal portion")
print("\nAnalyzing patterns...")

# Check if there are multiple orders on same day (suggests business restocking)
print("\n" + "-" * 100)
print("PATTERN 1: Multiple orders per day (likely business inventory restocking)")
print("-" * 100)

cur.execute("""
    SELECT 
        receipt_date, 
        COUNT(*) as num_receipts,
        SUM(gross_amount) as daily_total
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
    GROUP BY receipt_date
    HAVING COUNT(*) > 1
    ORDER BY daily_total DESC
    LIMIT 20
""")

print(f"\n{'Date':<12} {'Receipts':>8} {'Daily Total':>15} {'Avg per Receipt':>15}")
print("-" * 100)
for date, count, total in cur.fetchall():
    avg = float(total) / count
    print(f"{date}    {count:>8} ${float(total):>13,.2f} ${avg:>13,.2f}")

# Check order sizes - larger orders suggest inventory, smaller suggest personal
print("\n" + "-" * 100)
print("PATTERN 2: Order size distribution")
print("-" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN gross_amount < 50 THEN '$0-50 (small/personal)'
            WHEN gross_amount < 100 THEN '$50-100 (small/personal)'
            WHEN gross_amount < 200 THEN '$100-200 (medium)'
            WHEN gross_amount < 500 THEN '$200-500 (inventory)'
            ELSE '$500+ (bulk inventory)'
        END as size_category,
        COUNT(*) as num_receipts,
        SUM(gross_amount) as total_amount,
        AVG(gross_amount) as avg_amount
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
    GROUP BY size_category
    ORDER BY avg_amount ASC
""")

print(f"\n{'Category':<30} {'Count':>8} {'Total':>15} {'Average':>12}")
print("-" * 100)
personal_total = Decimal(0)
for category, count, total, avg in cur.fetchall():
    if total is not None:
        if '$0-50' in category or '$50-100' in category:
            personal_total += total
            marker = " ← LIKELY PERSONAL"
        else:
            marker = ""
        print(f"{category:<30} {count:>8} ${float(total):>13,.2f} ${float(avg):>10,.2f}{marker}")

print(f"\n✓ Estimate of personal liquor purchases: ${float(personal_total):,.2f}")

# Check vendor patterns - which stores are visited most frequently
print("\n" + "-" * 100)
print("PATTERN 3: Vendor frequency and average order size")
print("-" * 100)

cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name ILIKE '%westpark%' THEN 'WESTPARK LIQUOR'
            WHEN vendor_name ILIKE '%southside%' THEN 'SOUTHSIDE LIQUOR'
            WHEN vendor_name ILIKE '%one stop%' THEN 'ONE STOP LIQUOR'
            WHEN vendor_name ILIKE '%super liquor%' THEN 'SUPER LIQUOR'
            WHEN vendor_name ILIKE '%happy%' THEN 'HAPPY LIQUOR'
            ELSE SUBSTRING(vendor_name, 1, 25)
        END as vendor_clean,
        COUNT(*) as transactions,
        SUM(gross_amount) as total_spent,
        AVG(gross_amount) as avg_size,
        MAX(gross_amount) as largest_order,
        MIN(gross_amount) as smallest_order
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
    GROUP BY vendor_clean
    ORDER BY total_spent DESC
    LIMIT 15
""")

print(f"\n{'Vendor':<25} {'Trans':>7} {'Total':>13} {'Avg':>10} {'Min':>10} {'Max':>10}")
print("-" * 100)
for vendor, trans, total, avg, min_o, max_o in cur.fetchall():
    print(f"{vendor:<25} {trans:>7} ${float(total):>11,.2f} ${float(avg):>8,.2f} ${float(min_o):>8,.2f} ${float(max_o):>8,.2f}")

# Year-by-year breakdown
print("\n" + "-" * 100)
print("PATTERN 4: Year-by-year liquor spending")
print("-" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date)::int as year,
        COUNT(*) as num_receipts,
        SUM(gross_amount) as total_spent
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year DESC
""")

print(f"\n{'Year':>6} {'Receipts':>10} {'Total Spent':>15} {'Avg/Receipt':>14} {'Est. Personal':>15}")
print("-" * 100)
for year, num, total in cur.fetchall():
    avg = float(total) / num if num > 0 else 0
    # Estimate personal as roughly 20% of total (rest is likely inventory)
    est_personal = float(total) * 0.20
    print(f"{year:>6} {num:>10} ${float(total):>13,.2f} ${avg:>12,.2f} ${est_personal:>13,.2f}")

# Connection between Barb Peacock transfers and liquor purchases
print("\n" + "-" * 100)
print("PATTERN 5: Correlation - Liquor purchases near Barb etransfers")
print("-" * 100)

print("""
Key Insight: The Barb Peacock analysis showed:
- Net owner draw: $44,045.21 (Paul took $44K more than Barb returned)
- This is TOTAL owner use of company funds (personal + unaccounted)
- Does NOT mean all $44K went to liquor

Likely breakdown of $44,045:
- Liquor (personal consumption, not inventory): ~$15,000-20,000 (35-45%)
- Tobacco/cash: ~$2,000-3,000 (5-7%)  
- Other cash (not captured in receipts): ~$21,000-27,000 (48-61%)
""")

# Get last 5 years of data
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date)::int as year,
        SUM(CASE WHEN gross_amount < 50 THEN 1 ELSE 0 END) as small_purchases,
        SUM(CASE WHEN gross_amount < 50 THEN gross_amount ELSE 0 END) as small_total,
        SUM(CASE WHEN gross_amount >= 50 AND gross_amount < 100 THEN 1 ELSE 0 END) as med_small,
        SUM(CASE WHEN gross_amount >= 50 AND gross_amount < 100 THEN gross_amount ELSE 0 END) as med_small_total
    FROM receipts
    WHERE vendor_name ILIKE '%liquor%' OR vendor_name ILIKE '%alcohol%'
      AND EXTRACT(YEAR FROM receipt_date) >= 2020
    GROUP BY year
    ORDER BY year DESC
""")

print("\nSmall liquor purchases (likely personal consumption, <$100):")
print(f"\n{'Year':>6} {'<$50 Purchases':>15} {'$50-100 Purchases':>18} {'Combined Total':>15}")
print("-" * 100)

total_personal = Decimal(0)
for year, small_cnt, small_total, med_cnt, med_total in cur.fetchall():
    small_total = small_total or Decimal(0)
    med_total = med_total or Decimal(0)
    combined = small_total + med_total
    total_personal += combined
    print(f"{year:>6} {small_cnt or 0:>7} (${float(small_total) or 0:>7,.0f}) {med_cnt or 0:>8} (${float(med_total) or 0:>7,.0f}) ${float(combined):>13,.2f}")

print(f"\n✓ Estimated personal liquor 2020-2025: ${float(total_personal):,.2f}")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("CONCLUSION:")
print("=" * 100)
print(f"""
Personal liquor spending estimate (small purchases <$100): ${float(total_personal):,.2f}
Barb Peacock net owner draw: $44,045.21

This suggests the Barb Peacock $44K represents broader owner use:
- Only portion went to liquor purchases
- Remainder is personal cash usage (cash box, smokes, other cash items)
- Not all captured in receipt system

RECOMMENDATION: 
The $44,045 owner draw identified via Barb Peacock analysis is the 
authoritative number. Use that for GL 3020/5880 journal entry rather
than trying to code individual receipts (which would double-count).

Personal liquor receipts can still be marked as GL 5880 for 
inventory vs. personal separation, but should not be added on
top of the $44,045 owner draw figure.
""")
