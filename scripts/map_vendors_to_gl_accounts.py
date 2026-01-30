#!/usr/bin/env python3
"""
Map vendor canonical names to appropriate GL accounts based on business logic.
Uses the chart of accounts structure to suggest proper expense categorization.
"""

import psycopg2
import csv
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def load_chart_of_accounts():
    """Load GL account structure from database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT account_code, parent_account, account_name, account_type, 
               description, qb_account_type, account_level
        FROM chart_of_accounts
        WHERE is_active = true
        ORDER BY account_code
    """)
    
    accounts = {}
    for row in cur.fetchall():
        code, parent, name, acc_type, desc, qb_type, level = row
        accounts[code] = {
            'parent': parent,
            'name': name,
            'type': acc_type,
            'description': desc,
            'qb_type': qb_type,
            'level': level
        }
    
    cur.close()
    conn.close()
    return accounts

def get_vendor_categories():
    """Get all unique canonical vendors and their current categories."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COALESCE(canonical_vendor, vendor_name) AS vendor,
            category,
            COUNT(*) AS receipt_count,
            SUM(gross_amount) AS total_amount,
            MIN(receipt_date) AS first_date,
            MAX(receipt_date) AS last_date
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        GROUP BY COALESCE(canonical_vendor, vendor_name), category
        ORDER BY total_amount DESC
    """)
    
    vendors = []
    for row in cur.fetchall():
        vendors.append({
            'vendor': row[0],
            'category': row[1],
            'count': row[2],
            'total': row[3],
            'first': row[4],
            'last': row[5]
        })
    
    cur.close()
    conn.close()
    return vendors

def suggest_gl_account(vendor_name, current_category):
    """Suggest GL account based on vendor name and current category."""
    vendor_upper = vendor_name.upper()
    cat_lower = (current_category or '').lower()
    
    # Fuel vendors → 5110 Fuel Expense
    if any(fuel in vendor_upper for fuel in ['CENTEX', 'FAS GAS', 'SHELL', 'ESSO', 'PETRO', 'HUSKY', 'CO-OP GAS', 'GAS BAR']):
        return '5110', 'Fuel Expense', 'Vehicle fuel purchases'
    
    # Liquor/beverage vendors (need to distinguish client vs business)
    if any(liq in vendor_upper for liq in ['LIQUOR', 'BEVERAGE', 'BAR', 'PLENTY OF LIQUOR', 'SOBEYS LIQUOR', 'ACE LIQUOR', 'CO-OP LIQUOR']):
        if 'hospitality' in cat_lower or 'client' in cat_lower:
            return '5310', 'Beverages - Customer Service', 'Water/pop/chips for limousine service'
        else:
            return '5315', 'Beverages - Business Entertainment', 'Bar/liquor for business meetings (50% deductible)'
    
    # Vehicle maintenance
    if any(maint in vendor_upper for maint in ['CANADIAN TIRE', 'MIDAS', 'JIFFY', 'AUTO', 'REPAIR']):
        return '5120', 'Vehicle Maintenance & Repairs', 'Oil changes, repairs, parts'
    
    # Insurance (handles FIRST INSURANCE, CMB, SGI, etc.)
    if any(ins in vendor_upper for ins in ['INSURANCE', 'SGI', 'AVIVA', 'JEVCO']):
        return '5130', 'Vehicle Insurance', 'Commercial vehicle insurance'
    
    # Vehicle financing (Heffner Auto Finance)
    if 'HEFFNER' in vendor_upper:
        if 'PREAUTHORIZED DEBIT' in vendor_upper:
            return '5150', 'Vehicle Lease Payments', 'Heffner vehicle financing'
        else:
            return '5120', 'Vehicle Maintenance & Repairs', 'Heffner service/parts'
    
    if 'LEASE' in vendor_upper or 'FINANCING' in vendor_upper:
        return '5150', 'Vehicle Lease Payments', 'Operating lease payments'
    
    # Telecommunications
    if any(tel in vendor_upper for tel in ['TELUS', 'ROGERS', 'BELL', 'SASKTEL', 'PHONE', 'INTERNET']):
        return '5430', 'Telephone & Internet', 'Phone and internet services'
    
    # Office supplies
    if any(off in vendor_upper for off in ['STAPLES', 'OFFICE DEPOT', 'OFFICE SUPPLIES']):
        return '5420', 'Office Supplies', 'Stationery, printer supplies'
    
    # Banking items
    if 'BANK' in vendor_upper or 'NSF' in vendor_upper or 'FEE' in vendor_upper:
        if 'NSF' in vendor_upper or 'FEE' in vendor_upper:
            return '5710', 'Bank Fees & Service Charges', 'Monthly fees, transaction fees'
        elif 'CREDIT CARD' in vendor_upper or 'MCC PAYMENT' in vendor_upper:
            return '5720', 'Credit Card Processing Fees', 'Merchant fees'
    
    # Cash withdrawals
    if 'CASH WITHDRAWAL' in vendor_upper or 'ATM' in vendor_upper:
        return '1015', 'Petty Cash', 'Cash box for driver floats'
    
    # Rent (USER CLARIFICATION: Mike Woodrow is usually rent, can be vehicle R&M)
    if 'RENT' in vendor_upper or 'LANDLORD' in vendor_upper or 'FIBRENEW' in vendor_upper:
        return '5410', 'Rent Expense', 'Office/garage rent'
    if 'MIKE WOODROW' in vendor_upper or 'MICHAEL WOODROW' in vendor_upper:
        if 'parking' in (current_category or '').lower() or 'rent' in (current_category or '').lower():
            return '5410', 'Rent Expense', 'Parking/shop rent payments'
        else:
            return '5120', 'Vehicle Maintenance & Repairs', 'Vehicle work by Mike Woodrow'
    
    # Driver Wages (USER CLARIFICATION: Richard Michael is driver pay)
    if 'RICHARD MICHAEL' in vendor_upper or 'MICHAEL RICHARD' in vendor_upper:
        return '5210', 'Driver Wages', 'Chauffeur wages - Michael Richard'
    
    # Meals
    if any(meal in vendor_upper for meal in ['RESTAURANT', 'FOOD', 'TIM HORTONS', 'MCDONALDS', 'A&W']):
        if 'driver' in cat_lower:
            return '5320', 'Driver Meals - On Duty', 'Meals during charter shifts'
        else:
            return '5325', 'Business Meals & Entertainment', 'Client dinners (50% deductible)'
    
    # WCB
    if 'WCB' in vendor_upper or 'WORKERS COMP' in vendor_upper:
        return '5250', 'WCB Premiums', 'Workers Compensation premiums'
    
    # CRA/Government
    if 'CRA' in vendor_upper or 'CANADA REVENUE' in vendor_upper or 'RECEIVER GENERAL' in vendor_upper:
        return '2330', 'Payroll Taxes Payable - Income Tax', 'Tax remittances'
    
    # E-transfers (need context)
    if 'E-TRANSFER' in vendor_upper or 'ETRANSFER' in vendor_upper:
        # Check amount patterns from earlier analysis
        return None, 'NEEDS_REVIEW', 'E-Transfer - check if driver float/shareholder loan/deposit'
    
    # David Richard
    if 'DAVID RICH' in vendor_upper:
        return '2020', 'Notes Payable - David (Shareholder Loan)', 'Shareholder loans'
    
    # E-transfers to contractors/service providers (from "Utilities" category investigation)
    if vendor_upper in ['JASON ROGERS', 'DAVE MUNDY', 'JACK CORNWALL', 'DARWIN MEYERS']:
        return '5500', 'Professional Services', 'Contractor/consultant payments'
    
    # Generic "Utilities" vendor needs reclassification based on description
    if vendor_upper == 'UTILITIES':
        if 'insurance' in cat_lower:
            return '5130', 'Vehicle Insurance', 'Insurance payment'
        elif 'fuel' in cat_lower:
            return '5110', 'Fuel Expense', 'Fuel purchase'
        elif 'communication' in cat_lower:
            return '5430', 'Telephone & Internet', 'Communication services'
        else:
            return '5440', 'Utilities', 'Electricity, gas, water'
    
    # Default: mixed-use/uncategorized
    if not current_category or 'uncategorized' in cat_lower:
        return '5850', 'Mixed-Use Expenses', 'Expenses needing allocation'
    
    return None, None, None

def main():
    print("="*80)
    print("VENDOR TO GL ACCOUNT MAPPING ANALYSIS")
    print("="*80)
    
    # Load chart of accounts
    print("\nLoading chart of accounts...")
    accounts = load_chart_of_accounts()
    print(f"✅ Loaded {len(accounts)} active GL accounts")
    
    # Get vendor categories
    print("\nLoading 2019 vendors...")
    vendors = get_vendor_categories()
    print(f"✅ Found {len(vendors)} unique vendor-category combinations")
    
    # Analyze and suggest mappings
    print("\n" + "="*80)
    print("VENDOR GL ACCOUNT SUGGESTIONS")
    print("="*80)
    
    mappings = []
    needs_review = []
    
    for v in vendors:
        gl_code, gl_name, reason = suggest_gl_account(v['vendor'], v['category'])
        
        if gl_code:
            mappings.append({
                'vendor': v['vendor'],
                'current_category': v['category'],
                'suggested_gl_code': gl_code,
                'suggested_gl_name': gl_name,
                'reason': reason,
                'receipt_count': v['count'],
                'total_amount': v['total']
            })
        else:
            needs_review.append({
                'vendor': v['vendor'],
                'current_category': v['category'],
                'reason': reason or 'No matching pattern',
                'receipt_count': v['count'],
                'total_amount': v['total']
            })
    
    # Sort by total amount
    mappings.sort(key=lambda x: x['total_amount'], reverse=True)
    needs_review.sort(key=lambda x: x['total_amount'], reverse=True)
    
    # Display top suggestions
    print(f"\n✅ AUTO-MAPPED: {len(mappings)} vendors with suggested GL accounts")
    print("\nTop 30 by Amount:")
    print("-"*80)
    for m in mappings[:30]:
        print(f"{m['suggested_gl_code']} | {m['vendor'][:35]:35} | ${m['total_amount']:>10,.2f} | {m['receipt_count']:3} receipts")
        print(f"       {m['suggested_gl_name']}: {m['reason']}")
        print()
    
    print(f"\n⚠️ NEEDS REVIEW: {len(needs_review)} vendors without auto-mapping")
    print("\nTop 20 by Amount:")
    print("-"*80)
    for n in needs_review[:20]:
        print(f"??? | {n['vendor'][:35]:35} | ${n['total_amount']:>10,.2f} | {n['receipt_count']:3} receipts")
        print(f"      Current: {n['current_category']} | Reason: {n['reason']}")
        print()
    
    # Export to CSV
    print("\n" + "="*80)
    print("EXPORTING RESULTS")
    print("="*80)
    
    with open('l:/limo/data/vendor_gl_mapping_suggestions.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Vendor', 'Current_Category', 'Suggested_GL_Code', 'Suggested_GL_Name', 
                        'Reason', 'Receipt_Count', 'Total_Amount', 'Status'])
        
        for m in mappings:
            writer.writerow([
                m['vendor'], m['current_category'], m['suggested_gl_code'],
                m['suggested_gl_name'], m['reason'], m['receipt_count'],
                f"{m['total_amount']:.2f}", 'AUTO_MAPPED'
            ])
        
        for n in needs_review:
            writer.writerow([
                n['vendor'], n['current_category'], '', '',
                n['reason'], n['receipt_count'], f"{n['total_amount']:.2f}", 'NEEDS_REVIEW'
            ])
    
    print("✅ Exported to: l:/limo/data/vendor_gl_mapping_suggestions.csv")
    
    # Summary by GL account
    print("\n" + "="*80)
    print("SUMMARY BY GL ACCOUNT")
    print("="*80)
    
    gl_summary = defaultdict(lambda: {'count': 0, 'amount': 0.0, 'vendors': []})
    for m in mappings:
        gl = m['suggested_gl_code']
        gl_summary[gl]['count'] += m['receipt_count']
        gl_summary[gl]['amount'] += float(m['total_amount'])
        gl_summary[gl]['vendors'].append(m['vendor'])
        gl_summary[gl]['name'] = m['suggested_gl_name']
    
    for gl_code in sorted(gl_summary.keys()):
        s = gl_summary[gl_code]
        print(f"\n{gl_code} - {s['name']}")
        print(f"  {s['count']} receipts | ${s['amount']:,.2f} | {len(s['vendors'])} vendors")
        print(f"  Vendors: {', '.join(s['vendors'][:5])}")
        if len(s['vendors']) > 5:
            print(f"           ... and {len(s['vendors'])-5} more")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ {len(mappings)} vendors auto-mapped ({sum(m['receipt_count'] for m in mappings)} receipts, ${sum(m['total_amount'] for m in mappings):,.2f})")
    print(f"⚠️ {len(needs_review)} vendors need review ({sum(n['receipt_count'] for n in needs_review)} receipts, ${sum(n['total_amount'] for n in needs_review):,.2f})")
    print(f"📊 {len(gl_summary)} unique GL accounts used")

if __name__ == '__main__':
    main()
