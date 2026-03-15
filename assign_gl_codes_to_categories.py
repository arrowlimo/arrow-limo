"""
Assign GL Account Codes to Categorized Receipts
Maps categories to appropriate GL codes from chart of accounts
Flags for review when multiple GL codes could apply
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

print("="*80)
print("ASSIGN GL CODES TO CATEGORIZED RECEIPTS")
print("="*80)

# Category to GL Code mapping
# Based on typical limousine/transportation business chart of accounts
# Format: 'Category': ('primary_gl_code', 'alternate_gl_codes_if_any', needs_review_flag)
CATEGORY_GL_MAPPING = {
    'Fuel': ('5100', None, False),  # Vehicle Fuel
    'FUEL': ('5100', None, False),
    'fuel': ('5100', None, False),
    
    'Vehicle Maintenance': ('5200', None, False),  # Vehicle Repairs & Maintenance
    'Vehicle Rental/Maintenance': ('5200', '5300', True),  # Could be rental OR maintenance
    'maintenance': ('5200', None, False),
    
    'Vehicle Financing': ('5300', None, False),  # Vehicle Lease/Finance Payments
    'Vehicle Lease': ('5300', None, False),
    
    'Insurance': ('5400', None, False),  # Insurance Expense
    'Insurance - Vehicle Liability': ('5400', None, False),
    'Insurance - Claim Recovery': ('5400', '1100', True),  # Could be A/R recovery
    'insurance': ('5400', None, False),
    
    'Driver Expense': ('5500', '6400', True),  # Could be wages OR contract labor
    'Driver Pay': ('5500', None, False),
    
    'Rent': ('5600', None, False),  # Rent/Lease Expense
    'rent': ('5600', None, False),
    
    'Telecommunications': ('5700', None, False),  # Phone/Internet
    'communication': ('5700', None, False),
    
    'Office Supplies': ('5800', None, False),  # Office Supplies & Equipment
    'Supplies': ('5800', '6400', True),  # Could be office OR general business
    'office_supplies': ('5800', None, False),
    'SUPPLIES': ('5800', None, False),
    'Office supplies': ('5800', None, False),
    
    'Bank Fees': ('5900', None, False),  # Bank Charges & Fees
    'Bank Charges': ('5900', None, False),
    'bank_fees': ('5900', None, False),
    
    'Meals & Entertainment': ('6100', None, False),  # Meals & Entertainment (50% deductible)
    'meals_entertainment': ('6100', None, False),
    'Client Entertainment': ('6100', '6200', True),  # Could be meals OR hospitality
    'Food - Personal': ('6100', '6900', True),  # Could be business OR personal
    
    'Client Beverages': ('6200', None, False),  # Client Hospitality/Beverages
    'entertainment_beverages': ('6200', None, False),
    'hospitality_supplies': ('6200', None, False),
    
    'Government Fees': ('6300', None, False),  # Licenses, Permits, Registrations
    'government_fees': ('6300', None, False),
    'licenses': ('6300', None, False),
    '6950 - WCB': ('6950', None, False),
    'WCB': ('6950', None, False),
    
    'Advertising': ('6000', None, False),  # Advertising & Marketing
    '6000 - Advertising': ('6000', None, False),
    '5610 - Advertising': ('6000', None, False),
    'advertising': ('6000', None, False),
    
    'Business expense': ('6400', None, False),  # General Business Expenses
    'Administrative': ('6400', None, False),
    'Contract Labor': ('6400', '5500', True),  # Could be contract OR driver wages
    
    'Merchant Services': ('5900', None, False),  # Merchant/Payment Processing Fees
    
    'Groceries - Personal': ('6900', '6200', True),  # Could be personal OR client service
    'Cash Withdrawal': ('6900', '1000', True),  # Personal OR owner draw
    'Travel': ('6100', None, False),
    
    'Internet Bill Payment': ('5700', None, False),
    
    'Prepaid Card Load': ('1200', None, False),  # Asset - Prepaid
    
    'CRA': ('6300', '2100', True),  # Could be fees OR tax payable
    
    'Vehicle Rental': ('5200', '5300', True),  # Could be maintenance OR lease
    
    'Cheque': ('6900', None, True),  # Needs review
    
    'utilities': ('5750', None, False),  # Utilities
    
    'equipment_lease': ('5850', None, False),  # Equipment lease
    
    'mixed_use': ('6900', None, True),  # Mixed use - needs review
    
    'Needs Review': ('6900', None, True),  # Temporary holding
    
    'uncategorized_expenses': ('6900', None, True),  # Needs categorization
    
    'Internal_transfer': ('1000', None, True),  # Balance sheet - needs review
    'internal_transfer': ('1000', None, True),
    
    'credit': ('1000', None, True),  # Balance sheet - needs review
    
    'LOANS': ('2000', None, False),  # Liability - Loans
    'Loan Payment': ('2000', '5900', True),  # Principal OR interest
    
    'NSF - Business Checks': ('1100', None, False),  # A/R - NSF recovery
    
    'Banking Transaction': ('6900', None, True),  # Needs review
    
    'Unknown': ('6900', None, True),  # Holding account for manual review
    
    'revenue': ('4000', None, True),  # Revenue (shouldn't be in receipts)
    'Income - Other': ('4000', None, True),
    'Income - Card Payments': ('4000', None, True),
}

try:
    # Ensure needs_review column exists
    print("\nEnsuring needs_review column exists...")
    cur.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'receipts' AND column_name = 'needs_review'
            ) THEN
                ALTER TABLE receipts ADD COLUMN needs_review BOOLEAN DEFAULT FALSE;
            END IF;
        END $$;
    """)
    print("✅ needs_review column ready")
    
    # Ensure alternate_gl_code column exists
    print("Ensuring alternate_gl_code column exists...")
    cur.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'receipts' AND column_name = 'alternate_gl_code'
            ) THEN
                ALTER TABLE receipts ADD COLUMN alternate_gl_code VARCHAR(20);
            END IF;
        END $$;
    """)
    print("✅ alternate_gl_code column ready")
    
    # Show current state
    print("\nChecking receipts without GL codes...")
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE gl_account_code IS NULL OR gl_account_code = ''
    """)
    
    no_gl_count, no_gl_amount = cur.fetchone()
    print(f"Receipts without GL codes: {no_gl_count:,} (${no_gl_amount:,.2f})")
    
    print("\n" + "="*80)
    print("ASSIGNING GL CODES BY CATEGORY")
    print("="*80)
    
    total_updated = 0
    total_flagged = 0
    
    for category, mapping_info in sorted(CATEGORY_GL_MAPPING.items()):
        primary_gl, alternate_gl, needs_review = mapping_info
        
        # Build GL code display
        gl_display = primary_gl
        if alternate_gl:
            gl_display = f"{primary_gl}/{alternate_gl}"
        
        # Update query
        cur.execute("""
            UPDATE receipts
            SET 
                gl_account_code = %s,
                alternate_gl_code = %s,
                needs_review = %s,
                updated_at = NOW()
            WHERE category = %s
              AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code != %s)
        """, (primary_gl, alternate_gl, needs_review, category, primary_gl))
        
        count = cur.rowcount
        if count > 0:
            total_updated += count
            if needs_review:
                total_flagged += count
                flag = "🚩"
            else:
                flag = "  "
            print(f"{flag} {category:40} → {gl_display:<12}  ({count:,} receipts)")
    
    print(f"\n📊 TOTAL UPDATED: {total_updated:,} receipts")
    print(f"🚩 FLAGGED FOR REVIEW: {total_flagged:,} receipts")
    
    # Check what's left without GL codes
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE gl_account_code IS NULL OR gl_account_code = ''
    """)
    
    still_no_gl, still_no_gl_amt = cur.fetchone()
    still_no_gl_amt = still_no_gl_amt or 0
    print(f"\nStill without GL codes: {still_no_gl:,} (${still_no_gl_amt:,.2f})")
    
    # Show categories without mapping
    if still_no_gl > 0:
        print("\n" + "="*80)
        print("CATEGORIES WITHOUT GL CODE MAPPING")
        print("="*80)
        
        cur.execute("""
            SELECT category, COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE gl_account_code IS NULL OR gl_account_code = ''
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)
        
        print(f"\n{'Category':<40} {'Count':>6}  {'Amount':>14}")
        print("-" * 64)
        
        for cat, count, amount in cur.fetchall():
            cat_name = cat or 'NULL'
            amt_str = f"${amount:,.2f}" if amount else "$0.00"
            print(f"{cat_name:<40} {count:>6,}  {amt_str:>14}")
    
    # GL Code summary
    print("\n" + "="*80)
    print("GL CODE SUMMARY (TOP 20)")
    print("="*80)
    
    cur.execute("""
        SELECT 
            gl_account_code,
            COUNT(*) as count,
            SUM(gross_amount) as total,
            SUM(CASE WHEN needs_review THEN 1 ELSE 0 END) as review_count
        FROM receipts
        WHERE gl_account_code IS NOT NULL AND gl_account_code != ''
        GROUP BY gl_account_code
        ORDER BY count DESC
        LIMIT 20
    """)
    
    print(f"\n{'GL Code':<12} {'Count':>6}  {'Amount':>14}  {'Flagged':>8}")
    print("-" * 46)
    
    for gl, count, amount, review_cnt in cur.fetchall():
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        flag = f"{review_cnt:,}" if review_cnt > 0 else "-"
        print(f"{gl:<12} {count:>6,}  {amt_str:>14}  {flag:>8}")
    
    # Show flagged items summary
    print("\n" + "="*80)
    print("ITEMS FLAGGED FOR REVIEW")
    print("="*80)
    
    cur.execute("""
        SELECT 
            category,
            gl_account_code,
            alternate_gl_code,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE needs_review = TRUE
        GROUP BY category, gl_account_code, alternate_gl_code
        ORDER BY count DESC
    """)
    
    print(f"\n{'Category':<35} {'GL Codes':<20} {'Count':>6}  {'Amount':>14}")
    print("-" * 79)
    
    for cat, gl, alt_gl, count, amount in cur.fetchall():
        gl_codes = gl
        if alt_gl:
            gl_codes = f"{gl}/{alt_gl}"
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{cat:<35} {gl_codes:<20} {count:>6,}  {amt_str:>14}")
    
    # Overall stats
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
    total_recs, total_amt = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE gl_account_code IS NOT NULL AND gl_account_code != ''
    """)
    
    with_gl, with_gl_amt = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE needs_review = TRUE
    """)
    
    review_count, review_amt = cur.fetchone()
    
    print("\n" + "="*80)
    print("OVERALL STATUS")
    print("="*80)
    print(f"\nTotal receipts: {total_recs:,} (${total_amt:,.2f})")
    print(f"With GL codes: {with_gl:,} ({with_gl/total_recs*100:.1f}%)")
    print(f"Without GL codes: {still_no_gl:,} ({still_no_gl/total_recs*100:.1f}%)")
    print(f"🚩 Flagged for review: {review_count:,} ({review_count/total_recs*100:.1f}%) - ${review_amt:,.2f}")
    
    response = input("\n✋ COMMIT these GL code assignments? (yes/no): ").strip().lower()
    
    if response == 'yes':
        conn.commit()
        print("\n✅ GL codes COMMITTED")
    else:
        conn.rollback()
        print("\n❌ Changes ROLLED BACK")
        
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise
    
finally:
    cur.close()
    conn.close()
