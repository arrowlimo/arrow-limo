#!/usr/bin/env python3
"""Categorize the final 397 uncategorized receipts based on pattern analysis."""

import psycopg2
import sys

# Check for --write flag
DRY_RUN = '--write' not in sys.argv

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*120)
print("CATEGORIZING FINAL 397 UNCATEGORIZED RECEIPTS")
print("="*120)
print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE MODE'}\n")

categorization_plan = []

# 1. Gratuity Revenue → 4150 (Gratuity Income)
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (category = 'gratuity_revenue' 
         OR vendor_name LIKE 'Gratuity_%'
         OR description LIKE '%Gratuity Revenue%')
""")
gratuity = cur.fetchall()
if gratuity:
    categorization_plan.append(('Gratuity Revenue → 4150', gratuity, '4150'))
    print(f"✓ Gratuity Revenue: {len(gratuity)} receipts, ${sum(r[2] for r in gratuity):,.2f}")

# 2. Vehicle Lease (large amounts) → 5150
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%Ford E450%'
         OR vendor_name LIKE 'L-%'
         OR (category = 'equipment_lease' AND gross_amount > 10000))
""")
vehicle_lease = cur.fetchall()
if vehicle_lease:
    categorization_plan.append(('Vehicle Lease → 5150', vehicle_lease, '5150'))
    print(f"✓ Vehicle Lease: {len(vehicle_lease)} receipts, ${sum(r[2] for r in vehicle_lease):,.2f}")

# 3. Charter Charges (2013 imports) → 4100
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE 'Charter_Reserve_%'
         OR description LIKE '%Charter Charges%'
         OR (category = 'general_expense' AND description LIKE '%2013 Charter%'))
""")
charter_charges = cur.fetchall()
if charter_charges:
    categorization_plan.append(('Charter Revenue → 4100', charter_charges, '4100'))
    print(f"✓ Charter Revenue: {len(charter_charges)} receipts, ${sum(r[2] for r in charter_charges):,.2f}")

# 4. Bank fees and interest → 5150
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (category IN ('bank_fees', 'Banking - Credit Card Interest', 'Banking - Credit Card Member_Fee', 'Banking - Credit Card Fee', 'Bank Charges')
         OR vendor_name LIKE '%Capital One%'
         OR vendor_name LIKE '%Interest Charges%'
         OR vendor_name LIKE '%Member Fee%')
""")
bank_fees = cur.fetchall()
if bank_fees:
    categorization_plan.append(('Bank Fees → 5150', bank_fees, '5150'))
    print(f"✓ Bank Fees: {len(bank_fees)} receipts, ${sum(r[2] for r in bank_fees):,.2f}")

# 5. Merchant account cheques (need review but categorize as mixed for now) → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE 'CHEQUE %'
         AND description LIKE '%3648117%')
""")
merchant_cheques = cur.fetchall()
if merchant_cheques:
    categorization_plan.append(('Merchant Cheques → 5850', merchant_cheques, '5850'))
    print(f"✓ Merchant Cheques: {len(merchant_cheques)} receipts, ${sum(r[2] for r in merchant_cheques):,.2f}")

# 6. SBS Expense (accounting artifacts) → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND category = 'sbs_expense'
""")
sbs = cur.fetchall()
if sbs:
    categorization_plan.append(('SBS Accounting → 5850', sbs, '5850'))
    print(f"✓ SBS Accounting: {len(sbs)} receipts, ${sum(r[2] for r in sbs):,.2f}")

# 7. Numeric vendors (likely charter revenue) → 4100
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND vendor_name ~ '^[0-9]+$'
    AND vendor_name NOT LIKE '01000'
""")
numeric_vendors = cur.fetchall()
if numeric_vendors:
    categorization_plan.append(('Numeric Vendors (Charter) → 4100', numeric_vendors, '4100'))
    print(f"✓ Numeric Vendors: {len(numeric_vendors)} receipts, ${sum(r[2] for r in numeric_vendors):,.2f}")

# 8. Journal entries (PROMO & GST ADJ) → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (category = 'journal_entry' OR vendor_name LIKE 'JE_%')
""")
journal = cur.fetchall()
if journal:
    categorization_plan.append(('Journal Entries → 5850', journal, '5850'))
    print(f"✓ Journal Entries: {len(journal)} receipts, ${sum(r[2] for r in journal):,.2f}")

# 9. CIBC Branch withdrawals → 1020 (Petty Cash)
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%CIBC Branch%' OR category = 'Cash Withdrawal')
    AND description LIKE '%WITHDRAWAL%'
""")
cash_withdrawal = cur.fetchall()
if cash_withdrawal:
    categorization_plan.append(('Cash Withdrawals → 1020', cash_withdrawal, '1020'))
    print(f"✓ Cash Withdrawals: {len(cash_withdrawal)} receipts, ${sum(r[2] for r in cash_withdrawal):,.2f}")

# 10. Vehicle maintenance vendors → 5120
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%NORTHLAND RADIATOR%'
         OR vendor_name LIKE '%Kipp Scott GMC%'
         OR vendor_name LIKE '%Red Deer Toyota%'
         OR vendor_name LIKE '%WOW Windshields%'
         OR category = 'vehicle_expense')
""")
vehicle_maint = cur.fetchall()
if vehicle_maint:
    categorization_plan.append(('Vehicle Maintenance → 5120', vehicle_maint, '5120'))
    print(f"✓ Vehicle Maintenance: {len(vehicle_maint)} receipts, ${sum(r[2] for r in vehicle_maint):,.2f}")

# 11. Fuel vendors → 5110
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%Run''n On Empty%'
         OR vendor_name LIKE '%Burnt Lake Store%')
""")
fuel = cur.fetchall()
if fuel:
    categorization_plan.append(('Fuel → 5110', fuel, '5110'))
    print(f"✓ Fuel: {len(fuel)} receipts, ${sum(r[2] for r in fuel):,.2f}")

# 12. Meals & Entertainment → 5810
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%The Keg%'
         OR vendor_name LIKE '%CORONATION RESTAURAUNT%'
         OR vendor_name LIKE '%George''s%')
""")
meals = cur.fetchall()
if meals:
    categorization_plan.append(('Meals & Entertainment → 5810', meals, '5810'))
    print(f"✓ Meals: {len(meals)} receipts, ${sum(r[2] for r in meals):,.2f}")

# 13. Office supplies → 5430
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%Copies Now%'
         OR vendor_name LIKE '%Home Depot%'
         OR vendor_name LIKE '%Bed Bath & Beyond%')
""")
office = cur.fetchall()
if office:
    categorization_plan.append(('Office Supplies → 5430', office, '5430'))
    print(f"✓ Office Supplies: {len(office)} receipts, ${sum(r[2] for r in office):,.2f}")

# 14. Groceries/supplies (Safeway, Walmart, Wholesale Club, Sobeys) → 5430
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%Safeway%'
         OR vendor_name LIKE '%walmart%'
         OR vendor_name LIKE '%WHOLESALE CLUB%'
         OR vendor_name LIKE '%Sobeys%'
         OR vendor_name LIKE '%Shoppers Drug Mart%')
""")
groceries = cur.fetchall()
if groceries:
    categorization_plan.append(('Groceries/Supplies → 5430', groceries, '5430'))
    print(f"✓ Groceries/Supplies: {len(groceries)} receipts, ${sum(r[2] for r in groceries):,.2f}")

# 15. WCB Alberta → 5630 (Workers Comp)
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND vendor_name LIKE '%WCB Alberta%'
""")
wcb = cur.fetchall()
if wcb:
    categorization_plan.append(('WCB → 5630', wcb, '5630'))
    print(f"✓ WCB: {len(wcb)} receipts, ${sum(r[2] for r in wcb):,.2f}")

# 16. Court fees → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND vendor_name LIKE '%Provincial Court%'
""")
court = cur.fetchall()
if court:
    categorization_plan.append(('Court Fees → 5850', court, '5850'))
    print(f"✓ Court Fees: {len(court)} receipts, ${sum(r[2] for r in court):,.2f}")

# 17. Milano For Men, HOT TUB WHOLESALE → 5850 (personal/misc)
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%Milano For Men%'
         OR vendor_name LIKE '%HOT TUB%')
""")
personal = cur.fetchall()
if personal:
    categorization_plan.append(('Personal/Misc → 5850', personal, '5850'))
    print(f"✓ Personal/Misc: {len(personal)} receipts, ${sum(r[2] for r in personal):,.2f}")

# 18. Money mart, convenience stores → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name LIKE '%MONEY MART%'
         OR vendor_name LIKE '%7-11%')
    AND NOT (UPPER(description) LIKE '%PREPAID%'
             OR UPPER(description) LIKE '%RELOAD%'
             OR UPPER(description) LIKE '%VISA%'
             OR UPPER(description) LIKE '%CARD%')
""")
convenience = cur.fetchall()
if convenience:
    categorization_plan.append(('Convenience/Money Mart → 5850', convenience, '5850'))
    print(f"✓ Convenience: {len(convenience)} receipts, ${sum(r[2] for r in convenience):,.2f}")

# 19. Arrow Limousine (internal) → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND vendor_name = 'Arrow Limousine'
""")
internal = cur.fetchall()
if internal:
    categorization_plan.append(('Internal Transfers → 5850', internal, '5850'))
    print(f"✓ Internal: {len(internal)} receipts, ${sum(r[2] for r in internal):,.2f}")

# 20. Travel/lodging → 5440
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (category = 'Business Travel - Lodging'
         OR description LIKE '%TRAVEL%')
""")
travel = cur.fetchall()
if travel:
    categorization_plan.append(('Travel → 5440', travel, '5440'))
    print(f"✓ Travel: {len(travel)} receipts, ${sum(r[2] for r in travel):,.2f}")

# 21. Remaining with 'expense', 'Business Expense', 'expense_reclass' → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND category IN ('expense', 'Business Expense', 'expense_reclass')
""")
generic_expense = cur.fetchall()
if generic_expense:
    categorization_plan.append(('Generic Expenses → 5850', generic_expense, '5850'))
    print(f"✓ Generic Expenses: {len(generic_expense)} receipts, ${sum(r[2] for r in generic_expense):,.2f}")

# 22. Remaining cheque payments → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (category = 'cheque_payment'
         OR vendor_name LIKE 'Cheque #%')
""")
cheques = cur.fetchall()
if cheques:
    categorization_plan.append(('Cheque Payments → 5850', cheques, '5850'))
    print(f"✓ Cheques: {len(cheques)} receipts, ${sum(r[2] for r in cheques):,.2f}")

# 23. Unknown vendor → 5850
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND (vendor_name = 'unknown' OR vendor_name IS NULL)
""")
unknown = cur.fetchall()
if unknown:
    categorization_plan.append(('Unknown → 5850', unknown, '5850'))
    print(f"✓ Unknown: {len(unknown)} receipts, ${sum(r[2] for r in unknown):,.2f}")

# Calculate total
total_receipts = sum(len(plan[1]) for plan in categorization_plan)
total_amount = sum(sum(r[2] for r in plan[1]) for plan in categorization_plan)

print("\n" + "="*120)
print(f"TOTAL TO CATEGORIZE: {total_receipts} receipts, ${total_amount:,.2f}")
print("="*120)

if DRY_RUN:
    print("\n⚠️  DRY RUN MODE - No changes made")
    print("Run with --write flag to apply changes")
else:
    print("\n✍️  APPLYING CHANGES...")
    
    for label, receipts, gl_code in categorization_plan:
        if receipts:
            receipt_ids = [r[0] for r in receipts]
            cur.execute("""
                UPDATE receipts
                SET gl_account_code = %s,
                    auto_categorized = TRUE
                WHERE receipt_id = ANY(%s)
            """, (gl_code, receipt_ids))
            print(f"  ✓ {label}: {len(receipts)} receipts updated")
    
    conn.commit()
    print("\n✅ ALL CHANGES COMMITTED")
    
    # Final verification
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE (business_personal IS NULL OR business_personal != 'personal')
        AND gl_account_code IS NULL
    """)
    remaining = cur.fetchone()[0]
    print(f"\n📊 REMAINING UNCATEGORIZED: {remaining} receipts")

conn.close()
