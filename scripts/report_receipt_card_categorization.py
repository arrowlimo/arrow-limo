"""
Report on receipts with card data - now categorized by payment method and card.
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost",
    port="5432"
)

cur = conn.cursor()

print("=" * 80)
print("RECEIPT CARD DATA CATEGORIZATION REPORT")
print("=" * 80)

# Overview
print("\n1. RECEIPTS WITH CARD DATA")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(gross_amount) as total_amount,
        COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card,
        SUM(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN gross_amount ELSE 0 END) as card_amount,
        COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay_method,
        SUM(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN gross_amount ELSE 0 END) as pay_method_amount
    FROM receipts
    WHERE created_from_banking IS NULL OR created_from_banking = FALSE
""")

row = cur.fetchone()
total, total_amt, has_card, card_amt, has_pm, pm_amt = row
print(f"Non-banking receipts:               {total:6,}  ${total_amt:15,.2f}")
print(f"  With card_number:                 {has_card:6,}  ${card_amt:15,.2f}")
print(f"  With pay_method:                  {has_pm:6,}  ${pm_amt:15,.2f}")

# Payment method breakdown
print("\n2. PAYMENT METHOD BREAKDOWN")
print("-" * 80)

cur.execute("""
    SELECT 
        pay_method,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE (created_from_banking IS NULL OR created_from_banking = FALSE)
      AND pay_method IS NOT NULL
      AND pay_method != ''
    GROUP BY pay_method
    ORDER BY total_amount DESC
""")

results = cur.fetchall()
if results:
    print(f"{'Payment Method':20} {'Count':>10} {'Total Amount':>20}")
    print("-" * 55)
    for row in results:
        pm, count, amount = row
        print(f"{pm:20} {count:10,}  ${amount:18,.2f}")

# Card number breakdown
print("\n3. CARD NUMBER BREAKDOWN")
print("-" * 80)

cur.execute("""
    SELECT 
        card_number,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE (created_from_banking IS NULL OR created_from_banking = FALSE)
      AND card_number IS NOT NULL
      AND card_number != ''
    GROUP BY card_number
    ORDER BY count DESC
""")

results = cur.fetchall()
if results:
    print(f"{'Card Number':15} {'Count':>10} {'Total Amount':>20} {'Description'}")
    print("-" * 80)
    descriptions = {
        '3265': 'CIBC business debit (primary)',
        '9206': 'Driver card (reimbursement)',
        '3559': 'Driver card (reimbursement)',
        '8547': 'Driver card (reimbursement)',
        '6817': 'Driver card (reimbursement)',
        '0853': 'Money Mart location'
    }
    for row in results:
        card, count, amount = row
        desc = descriptions.get(card, 'Driver/other card')
        print(f"{card:15} {count:10,}  ${amount:18,.2f}  {desc}")

# CIBC debit card (3265) detail
print("\n4. CIBC DEBIT CARD (3265) - PRIMARY BUSINESS CARD")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total,
        pay_method,
        COUNT(*) as method_count
    FROM receipts
    WHERE card_number = '3265'
      AND (created_from_banking IS NULL OR created_from_banking = FALSE)
    GROUP BY pay_method
    ORDER BY method_count DESC
""")

results = cur.fetchall()
if results:
    print(f"Card 3265 transactions by payment method:")
    print(f"{'Pay Method':20} {'Count':>10} {'Total Amount':>20}")
    print("-" * 55)
    for row in results:
        count, amount, pm, mcount = row
        print(f"{pm or 'NULL':20} {mcount:10,}  ${amount:18,.2f}")

# Cash receipts
print("\n5. CASH RECEIPTS")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE pay_method = 'Cash'
      AND (created_from_banking IS NULL OR created_from_banking = FALSE)
""")

row = cur.fetchone()
if row:
    count, amount = row
    print(f"Cash receipts:  {count:6,}  ${amount:15,.2f}")

# Sample cash receipts
cur.execute("""
    SELECT 
        id,
        receipt_date,
        vendor_name,
        gross_amount,
        description
    FROM receipts
    WHERE pay_method = 'Cash'
      AND (created_from_banking IS NULL OR created_from_banking = FALSE)
    ORDER BY receipt_date DESC
    LIMIT 10
""")

results = cur.fetchall()
if results:
    print(f"\nSample cash receipts:")
    print(f"{'ID':6} {'Date':12} {'Vendor':30} {'Amount':12} {'Description':30}")
    print("-" * 100)
    for row in results:
        rid, date, vendor, amount, desc = row
        vendor = (vendor or '')[:29]
        desc = (desc or '')[:29]
        print(f"{rid:6} {str(date):12} {vendor:30} ${amount:10,.2f} {desc:30}")

# Debit receipts
print("\n6. DEBIT RECEIPTS")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE pay_method = 'Debit'
      AND (created_from_banking IS NULL OR created_from_banking = FALSE)
""")

row = cur.fetchone()
if row:
    count, amount = row
    print(f"Debit receipts: {count:6,}  ${amount:15,.2f}")

# Remaining receipts without card data
print("\n7. RECEIPTS STILL MISSING CARD/PAYMENT DATA")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE (created_from_banking IS NULL OR created_from_banking = FALSE)
      AND (pay_method IS NULL OR pay_method = '')
""")

row = cur.fetchone()
if row:
    count, amount = row
    print(f"Receipts without pay_method: {count:6,}  ${amount:15,.2f}")
    print("\nThese receipts were either:")
    print("  - Not in the staging table (imported from different source)")
    print("  - Could not be matched (vendor/date/amount mismatch)")
    print("  - Had empty pay_method in original CSV")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("REPORT COMPLETE!")
print("=" * 80)
print("\nNEXT STEPS:")
print("1. Review cash vs debit categorization")
print("2. Identify receipts where card 3265 = CIBC business debit")
print("3. Flag driver cards (9206, 3559, 8547, etc.) for reimbursement tracking")
print("4. Link receipts to GL accounts based on payment method")
print("=" * 80)
