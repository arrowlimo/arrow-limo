#!/usr/bin/env python3
"""Auto-categorize remaining uncategorized receipts using smart pattern matching."""

import psycopg2
import re

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*80)
print("SMART CATEGORIZATION - REMAINING RECEIPTS")
print("="*80)

# Get uncategorized business receipts
cur.execute("""
    SELECT receipt_id, vendor_name, description, gross_amount, category
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    ORDER BY gross_amount DESC
""")

uncategorized = cur.fetchall()
print(f"\nFound {len(uncategorized):,} uncategorized receipts")

# Enhanced categorization patterns
PATTERNS = [
    # Fuel
    (r'(?i)(centex|fas gas|shell|esso|petro|husky|chevron|gas|fuel|diesel)', 'fuel', '5110'),
    # Vehicle maintenance
    (r'(?i)(tire|oil change|repair|midas|jiffy|canadian tire|car wash|tow)', 'maintenance', '5120'),
    # Insurance
    (r'(?i)(insurance|aviva|sgi|jevco|policy|premium)', 'insurance', '5130'),
    # Licenses & permits
    (r'(?i)(license|permit|registration|inspection|renewal)', 'government_fees', '5140'),
    # Bank fees
    (r'(?i)(bank fee|nsf|overdraft|service charge|account fee|atm fee)', 'bank_fees', '5150'),
    # Office supplies
    (r'(?i)(staples|office depot|paper|printer|ink|supplies)', 'office_supplies', '5430'),
    # Communication
    (r'(?i)(telus|rogers|bell|sasktel|phone|internet|cellular|wireless)', 'communication', '5210'),
    # Rent
    (r'(?i)(rent|lease|landlord|property|fibrenew)', 'rent', '5410'),
    # Utilities
    (r'(?i)(electric|gas bill|water|sewer|utility|power)', 'utilities', '5440'),
    # Meals & entertainment
    (r'(?i)(restaurant|tim horton|mcdon|burger|pizza|coffee|food|catering)', 'meals_entertainment', '5470'),
    # Advertising
    (r'(?i)(advertis|marketing|print|sign|website|social media)', 'advertising', '5480'),
    # Professional fees
    (r'(?i)(lawyer|legal|accountant|consulting|professional)', 'professional_fees', '5490'),
    # Equipment
    (r'(?i)(equipment|tool|hardware|heffner|vehicle purchase)', 'equipment_lease', '5420'),
    # Hospitality supplies
    (r'(?i)(liquor|beverage|bar|wine|alcohol)', 'hospitality_supplies', '5500'),
    # Cash withdrawal (asset account)
    (r'(?i)(abm withdrawal|atm withdrawal|cash withdrawal)', 'petty_cash', '1020'),
    # Deposits (asset account)
    (r'(?i)(^deposit$|bank deposit)', 'internal_transfer', '1010'),
    # Credit card payments
    (r'(?i)(mcc payment|credit card payment|visa payment|mastercard payment)', 'credit_card_payment', '2100'),
]

categorized_count = 0
by_category = {}

for receipt_id, vendor, description, amount, current_category in uncategorized:
    text = f"{vendor or ''} {description or ''}".lower()
    
    matched = False
    for pattern, category_name, gl_code in PATTERNS:
        if re.search(pattern, text):
            # Update receipt
            cur.execute("""
                UPDATE receipts
                SET category = %s,
                    gl_account_code = %s,
                    auto_categorized = TRUE
                WHERE receipt_id = %s
            """, (category_name, gl_code, receipt_id))
            
            categorized_count += 1
            by_category[category_name] = by_category.get(category_name, 0) + 1
            matched = True
            break
    
    # Progress indicator
    if categorized_count % 1000 == 0 and categorized_count > 0:
        print(f"  Processed {categorized_count:,} receipts...")

conn.commit()

print(f"\n✓ Categorized {categorized_count:,} receipts")
print("\nBreakdown by category:")
print("-"*80)
for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
    print(f"  {cat:30s}: {count:5,} receipts")

# Get final stats
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN gl_account_code IS NOT NULL THEN 1 END) as with_gl_code
    FROM receipts
    WHERE business_personal IS NULL OR business_personal != 'personal'
""")
row = cur.fetchone()
total = row[0]
with_gl = row[1]

print("\n" + "="*80)
print(f"FINAL STATUS: {with_gl:,}/{total:,} receipts categorized ({with_gl*100/total:.1f}%)")
print("="*80)

conn.close()
