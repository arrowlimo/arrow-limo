#!/usr/bin/env python3
"""
Verify 2012 expense recovery and calculate updated tax impact.
"""

import os
import psycopg2
from decimal import Decimal

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)

cur = conn.cursor()

print("2012 EXPENSE RECOVERY VERIFICATION")
print("=" * 50)

# Total 2012 receipts
cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        SUM(gross_amount) as total_amount
    FROM receipts 
    WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
""")

total_data = cur.fetchone()
total_receipts = total_data[0]
total_amount = total_data[1] or Decimal('0')

# Excel imported receipts
cur.execute("""
    SELECT 
        COUNT(*) as excel_receipts,
        SUM(gross_amount) as excel_amount
    FROM receipts 
    WHERE source_reference LIKE '2012_Excel_%'
""")

excel_data = cur.fetchone()
excel_receipts = excel_data[0]
excel_amount = excel_data[1] or Decimal('0')

# Category breakdown of Excel imports
cur.execute("""
    SELECT 
        category,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as category_total
    FROM receipts 
    WHERE source_reference LIKE '2012_Excel_%'
    GROUP BY category
    ORDER BY category_total DESC
""")

categories = cur.fetchall()

# Show results
print(f"Total 2012 receipts: {total_receipts:,}")
print(f"Total 2012 amount: ${total_amount:,.2f}")
print(f"\nExcel recovered: {excel_receipts:,} receipts")
print(f"Excel amount: ${excel_amount:,.2f}")

recovery_percentage = (excel_amount / total_amount * 100) if total_amount > 0 else 0
print(f"Recovery percentage: {recovery_percentage:.1f}% of total receipts")

# Calculate tax impact
tax_benefit = excel_amount * Decimal('0.14')
print(f"\n💰 TAX IMPACT:")
print(f"Additional deductions: ${excel_amount:,.2f}")
print(f"Tax savings (14%): ${tax_benefit:,.2f}")

print(f"\n📋 RECOVERED EXPENSE CATEGORIES:")
print("-" * 40)

for category, count, amount in categories:
    category_name = category or 'Uncategorized'
    print(f"{category_name:<25} ${amount:>10,.2f} ({count:>3} receipts)")

# Compare with previous analysis
print(f"\n🔍 COMPARISON WITH PREVIOUS 2012 ANALYSIS:")
print(f"Previous net tax owing: $23,711")
print(f"Additional deductions: ${excel_amount:,.2f}")
print(f"Tax reduction (14%): ${tax_benefit:,.2f}")
print(f"New estimated tax owing: ${23711 - float(tax_benefit):,.2f}")

cur.close()
conn.close()

print(f"\n[OK] EXPENSE RECOVERY COMPLETE!")
print(f"Successfully recovered ${excel_amount:,.2f} in missing business expenses")
print(f"Next step: Apply same methodology to 2013+ Excel files")