"""
Categorize Personal Expenses for Paul's Personal Tax Reporting
Standardizes categories and creates tax-deductible expense reports
"""

import psycopg2
from datetime import datetime
from collections import defaultdict

# Connect to database
conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***',
    host='localhost'
)

# Tax-relevant category mappings for Canadian personal income tax
TAX_CATEGORY_MAPPINGS = {
    # Vehicle/Auto Expenses (if used for business purposes)
    'VehicleMaintenance': {
        'tax_category': 'Motor Vehicle Expenses',
        'cra_code': 'T2125_9281',  # Motor vehicle expenses
        'description': 'Vehicle maintenance and repairs',
        'deductible': True,
        'requires_business_percentage': True
    },
    'AutoMaintenance': {
        'tax_category': 'Motor Vehicle Expenses',
        'cra_code': 'T2125_9281',
        'description': 'Auto maintenance and repairs',
        'deductible': True,
        'requires_business_percentage': True
    },
    'Fuel': {
        'tax_category': 'Motor Vehicle Expenses - Fuel',
        'cra_code': 'T2125_9281',
        'description': 'Vehicle fuel costs',
        'deductible': True,
        'requires_business_percentage': True
    },
    'fuel': {
        'tax_category': 'Motor Vehicle Expenses - Fuel',
        'cra_code': 'T2125_9281',
        'description': 'Vehicle fuel costs',
        'deductible': True,
        'requires_business_percentage': True
    },
    
    # Office/Business Expenses
    'Internet': {
        'tax_category': 'Office Expenses - Internet',
        'cra_code': 'T2125_8810',  # Office expenses
        'description': 'Internet service for business',
        'deductible': True,
        'requires_business_percentage': True
    },
    'Telecom': {
        'tax_category': 'Telephone and Utilities',
        'cra_code': 'T2125_9220',  # Telephone and utilities
        'description': 'Telephone and telecom services',
        'deductible': True,
        'requires_business_percentage': True
    },
    'office_supplies': {
        'tax_category': 'Office Expenses - Supplies',
        'cra_code': 'T2125_8810',
        'description': 'Office supplies',
        'deductible': True,
        'requires_business_percentage': False
    },
    'Supplies': {
        'tax_category': 'Office Expenses - Supplies',
        'cra_code': 'T2125_8810',
        'description': 'Business supplies',
        'deductible': True,
        'requires_business_percentage': False
    },
    'supplies': {
        'tax_category': 'Office Expenses - Supplies',
        'cra_code': 'T2125_8810',
        'description': 'Business supplies',
        'deductible': True,
        'requires_business_percentage': False
    },
    
    # Tools and Equipment
    'ToolsEquipment': {
        'tax_category': 'Tools - Under $500',
        'cra_code': 'T2125_9270',  # Tools under $500
        'description': 'Tools and small equipment',
        'deductible': True,
        'requires_business_percentage': False
    },
    'Equipment': {
        'tax_category': 'Capital Equipment',
        'cra_code': 'CCA_Class_8',  # May require capital cost allowance
        'description': 'Business equipment',
        'deductible': True,
        'requires_business_percentage': False
    },
    
    # Materials and Building
    'Materials': {
        'tax_category': 'Materials and Supplies',
        'cra_code': 'T2125_MATERIALS',
        'description': 'Materials for business use',
        'deductible': True,
        'requires_business_percentage': False
    },
    'BuildingMaterials': {
        'tax_category': 'Building Materials',
        'cra_code': 'T2125_BUILDING',
        'description': 'Building and construction materials',
        'deductible': True,
        'requires_business_percentage': False
    },
    
    # Business Services
    'BusinessServices': {
        'tax_category': 'Professional Fees',
        'cra_code': 'T2125_8862',  # Legal/accounting/professional fees
        'description': 'Professional and business services',
        'deductible': True,
        'requires_business_percentage': False
    },
    'Software': {
        'tax_category': 'Office Expenses - Software',
        'cra_code': 'T2125_8810',
        'description': 'Software subscriptions and licenses',
        'deductible': True,
        'requires_business_percentage': False
    },
    
    # Client and Entertainment
    'ClientHospitality': {
        'tax_category': 'Meals and Entertainment',
        'cra_code': 'T2125_8523',  # Meals and entertainment (50% deductible)
        'description': 'Client meals and entertainment',
        'deductible': True,
        'deduction_percentage': 50,  # CRA allows only 50%
        'requires_business_percentage': False
    },
    'meals': {
        'tax_category': 'Meals and Entertainment',
        'cra_code': 'T2125_8523',
        'description': 'Business meals',
        'deductible': True,
        'deduction_percentage': 50,
        'requires_business_percentage': False
    },
    
    # Other Business Expenses
    'Fees': {
        'tax_category': 'Business Fees',
        'cra_code': 'T2125_OTHER',
        'description': 'Various business fees',
        'deductible': True,
        'requires_business_percentage': False
    },
    'LicensesPermits': {
        'tax_category': 'Licenses and Permits',
        'cra_code': 'T2125_8860',
        'description': 'Business licenses and permits',
        'deductible': True,
        'requires_business_percentage': False
    },
    'maintenance': {
        'tax_category': 'Maintenance and Repairs',
        'cra_code': 'T2125_8960',
        'description': 'Maintenance expenses',
        'deductible': True,
        'requires_business_percentage': False
    },
    'Electronics': {
        'tax_category': 'Office Equipment',
        'cra_code': 'CCA_Class_50',  # Computer equipment - 55% CCA
        'description': 'Electronic equipment',
        'deductible': True,
        'requires_business_percentage': False
    },
    'Security': {
        'tax_category': 'Insurance and Security',
        'cra_code': 'T2125_9804',
        'description': 'Security services',
        'deductible': True,
        'requires_business_percentage': False
    },
    
    # Non-Deductible Personal
    'PersonalUse': {
        'tax_category': 'Personal - Not Deductible',
        'cra_code': 'N/A',
        'description': 'Personal use items',
        'deductible': False,
        'requires_business_percentage': False
    },
    
    # Special Categories
    'RefundAdjustment': {
        'tax_category': 'Adjustment/Refund',
        'cra_code': 'N/A',
        'description': 'Refunds or adjustments',
        'deductible': False,
        'requires_business_percentage': False
    },
    'CreditCardPayment': {
        'tax_category': 'Debt Payment',
        'cra_code': 'N/A',
        'description': 'Credit card payments',
        'deductible': False,
        'requires_business_percentage': False
    },
}

def add_tax_categorization_columns():
    """Add columns for tax categorization"""
    cur = conn.cursor()
    
    # Check if columns exist
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'personal_expenses' 
        AND column_name = 'tax_category'
    """)
    
    if not cur.fetchone():
        cur.execute("""
            ALTER TABLE personal_expenses 
            ADD COLUMN tax_category VARCHAR(100),
            ADD COLUMN cra_code VARCHAR(50),
            ADD COLUMN is_tax_deductible BOOLEAN DEFAULT false,
            ADD COLUMN deduction_percentage INTEGER DEFAULT 100,
            ADD COLUMN calculated_deduction NUMERIC(10,2),
            ADD COLUMN tax_notes TEXT
        """)
        conn.commit()
        print("✓ Added tax categorization columns")
    else:
        print("✓ Tax categorization columns already exist")

def apply_tax_categories():
    """Apply tax categories to personal expenses"""
    cur = conn.cursor()
    
    total_updated = 0
    
    for category, tax_info in TAX_CATEGORY_MAPPINGS.items():
        # Calculate deduction amount
        deduction_pct = tax_info.get('deduction_percentage', 100)
        
        # Build tax notes
        notes_parts = [tax_info['description']]
        if tax_info.get('requires_business_percentage'):
            notes_parts.append("Requires business use percentage")
        if deduction_pct < 100:
            notes_parts.append(f"{deduction_pct}% deductible per CRA")
        
        tax_notes = "; ".join(notes_parts)
        
        cur.execute("""
            UPDATE personal_expenses
            SET 
                tax_category = %s,
                cra_code = %s,
                is_tax_deductible = %s,
                deduction_percentage = %s,
                calculated_deduction = CASE 
                    WHEN business_percentage IS NOT NULL THEN 
                        amount * (business_percentage / 100.0) * (%s / 100.0)
                    ELSE 
                        amount * (%s / 100.0)
                END,
                tax_notes = %s
            WHERE category = %s
        """, (
            tax_info['tax_category'],
            tax_info['cra_code'],
            tax_info['deductible'],
            deduction_pct,
            deduction_pct,
            deduction_pct,
            tax_notes,
            category
        ))
        
        count = cur.rowcount
        total_updated += count
        if count > 0:
            print(f"  ✓ {category:30} → {tax_info['tax_category']:40} ({count:3} items)")
    
    conn.commit()
    print(f"\n✓ Applied tax categories to {total_updated:,} personal expense items")
    return total_updated

def generate_tax_report():
    """Generate comprehensive tax deduction report"""
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("PAUL'S PERSONAL EXPENSES - TAX DEDUCTION REPORT")
    print("="*100)
    
    # Overall summary
    cur.execute("""
        SELECT 
            COUNT(*) as total_items,
            SUM(amount) as total_amount,
            SUM(CASE WHEN is_tax_deductible THEN 1 ELSE 0 END) as deductible_items,
            SUM(calculated_deduction) as total_deductions
        FROM personal_expenses
    """)
    
    total_items, total_amount, deductible_items, total_deductions = cur.fetchone()
    
    print(f"\nOVERALL SUMMARY:")
    print(f"  Total personal expenses:          {total_items:6,} items    ${total_amount:>12,.2f}")
    print(f"  Tax-deductible items:             {deductible_items:6,} items")
    print(f"  Non-deductible items:             {total_items - deductible_items:6,} items")
    print(f"  Total potential tax deductions:                    ${total_deductions:>12,.2f}")
    
    # By tax year
    print(f"\nBY TAX YEAR:")
    print("-" * 100)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM date) as tax_year,
            COUNT(*) as items,
            SUM(amount) as total,
            SUM(CASE WHEN is_tax_deductible THEN 1 ELSE 0 END) as deductible_items,
            SUM(calculated_deduction) as deductions
        FROM personal_expenses
        GROUP BY EXTRACT(YEAR FROM date)
        ORDER BY tax_year
    """)
    
    for year, items, total, ded_items, deductions in cur.fetchall():
        if year:
            pct = (deductions / total * 100) if total > 0 else 0
            print(f"  {int(year):4}:  {items:4} items  Total: ${total:>10,.2f}  "
                  f"Deductible: {ded_items:4} items (${deductions:>10,.2f} - {pct:.1f}%)")
    
    # By CRA tax category
    print(f"\nBY CRA TAX CATEGORY:")
    print("-" * 100)
    cur.execute("""
        SELECT 
            tax_category,
            cra_code,
            COUNT(*) as items,
            SUM(amount) as total_spent,
            SUM(calculated_deduction) as total_deduction,
            is_tax_deductible
        FROM personal_expenses
        WHERE tax_category IS NOT NULL
        GROUP BY tax_category, cra_code, is_tax_deductible
        ORDER BY total_deduction DESC NULLS LAST
    """)
    
    deductible_total = 0
    non_deductible_total = 0
    
    for tax_cat, cra_code, items, spent, deduction, deductible in cur.fetchall():
        if deductible:
            marker = "✓"
            deductible_total += float(deduction or 0)
            pct = (deduction / spent * 100) if spent and deduction else 0
            print(f"  {marker} {cra_code:20} {tax_cat:45} {items:4} items  "
                  f"${spent:>10,.2f} → ${deduction:>10,.2f} ({pct:.0f}%)")
        else:
            marker = "✗"
            non_deductible_total += float(spent or 0)
            print(f"  {marker} {cra_code:20} {tax_cat:45} {items:4} items  "
                  f"${spent:>10,.2f} (Not deductible)")
    
    print(f"\n  {'TOTALS:':68} Deductible: ${deductible_total:>10,.2f}")
    print(f"  {'':68} Non-deductible: ${non_deductible_total:>10,.2f}")
    
    # Items requiring business percentage
    print(f"\nITEMS REQUIRING BUSINESS USE PERCENTAGE:")
    print("-" * 100)
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as items,
            SUM(amount) as total,
            AVG(business_percentage) as avg_business_pct,
            SUM(calculated_deduction) as deductions
        FROM personal_expenses
        WHERE tax_notes LIKE '%business use percentage%'
        GROUP BY category
        ORDER BY total DESC
    """)
    
    results = cur.fetchall()
    if results:
        for cat, items, total, avg_pct, deductions in results:
            avg_pct_display = f"{avg_pct:.0f}%" if avg_pct else "NOT SET"
            print(f"  ⚠ {cat:30} {items:4} items  ${total:>10,.2f}  "
                  f"Avg Business%: {avg_pct_display:>6}  Deduction: ${deductions:>10,.2f}")
    else:
        print("  (None)")
    
    # Items with special deduction rules
    print(f"\nITEMS WITH SPECIAL DEDUCTION RULES:")
    print("-" * 100)
    cur.execute("""
        SELECT 
            tax_category,
            deduction_percentage,
            COUNT(*) as items,
            SUM(amount) as total,
            SUM(calculated_deduction) as deductions
        FROM personal_expenses
        WHERE deduction_percentage < 100
        GROUP BY tax_category, deduction_percentage
        ORDER BY total DESC
    """)
    
    results = cur.fetchall()
    if results:
        for cat, pct, items, total, deductions in results:
            print(f"  ⚠ {cat:50} {pct}% deductible  "
                  f"{items:4} items  ${total:>10,.2f} → ${deductions:>10,.2f}")
    else:
        print("  (None)")

def generate_yearly_tax_summary(year):
    """Generate detailed tax summary for a specific year"""
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print(f"TAX YEAR {year} - DETAILED PERSONAL EXPENSE BREAKDOWN")
    print("="*100)
    
    cur.execute("""
        SELECT 
            cra_code,
            tax_category,
            COUNT(*) as items,
            SUM(amount) as total_spent,
            SUM(calculated_deduction) as total_deduction,
            STRING_AGG(DISTINCT payment_method, ', ') as payment_methods
        FROM personal_expenses
        WHERE EXTRACT(YEAR FROM date) = %s
        AND is_tax_deductible = true
        GROUP BY cra_code, tax_category
        ORDER BY total_deduction DESC
    """, (year,))
    
    results = cur.fetchall()
    
    if not results:
        print(f"\nNo tax-deductible expenses found for year {year}")
        return
    
    grand_total = 0
    
    for cra_code, tax_cat, items, spent, deduction, methods in results:
        grand_total += float(deduction or 0)
        print(f"\n{cra_code} - {tax_cat}")
        print(f"  Items: {items:4}  Spent: ${spent:>10,.2f}  Deduction: ${deduction:>10,.2f}")
        print(f"  Payment methods: {methods}")
        
        # Get detail records
        cur.execute("""
            SELECT date, description, amount, calculated_deduction, business_percentage
            FROM personal_expenses
            WHERE EXTRACT(YEAR FROM date) = %s
            AND cra_code = %s
            ORDER BY date
            LIMIT 5
        """, (year, cra_code))
        
        detail = cur.fetchall()
        if detail:
            print(f"  Sample transactions:")
            for dt, desc, amt, ded, biz_pct in detail:
                biz_note = f" ({biz_pct}% business)" if biz_pct else ""
                print(f"    {dt}  ${amt:>8,.2f} → ${ded:>8,.2f}{biz_note}  {desc[:50]}")
    
    print("\n" + "-"*100)
    print(f"TOTAL DEDUCTIONS FOR {year}: ${grand_total:,.2f}")
    print("="*100)

def main():
    print("Categorizing Personal Expenses for Paul's Tax Reporting...")
    print("="*100)
    
    add_tax_categorization_columns()
    
    print("\nApplying Tax Categories:")
    print("-" * 100)
    apply_tax_categories()
    
    generate_tax_report()
    
    # Generate detailed reports for recent years
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM personal_expenses ORDER BY year DESC LIMIT 3")
    recent_years = [int(row[0]) for row in cur.fetchall() if row[0]]
    
    for year in recent_years:
        generate_yearly_tax_summary(year)
    
    print("\n" + "="*100)
    print("TAX CATEGORIZATION COMPLETE!")
    print("="*100)
    print("\nNext Steps:")
    print("1. Review items marked with ⚠ (require business use percentage)")
    print("2. Set business_percentage for vehicle and home office expenses")
    print("3. Export data for tax preparation software or accountant")
    print("4. Keep receipts for all deductible expenses for CRA audit")
    print("="*100)
    
    conn.close()

if __name__ == '__main__':
    main()
