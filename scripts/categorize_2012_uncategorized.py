#!/usr/bin/env python3
"""
Categorize all uncategorized 2012 receipts using smart patterns.
Focus on the 4,331 receipts ($3.98M) that have no GL codes.
"""

import psycopg2
import re
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def normalize_vendor(vendor):
    """Normalize vendor names for pattern matching."""
    if not vendor:
        return ""
    
    vendor = vendor.upper().strip()
    
    # Remove location codes
    vendor = re.sub(r'\b(RED DEER|LETHBRIDGE|CALGARY|EDMONTON)\s+(AB|ALBERTA)\b', '', vendor)
    
    # Remove store numbers
    vendor = re.sub(r'#\d+', '', vendor)
    vendor = re.sub(r'\d{4}\*+\d{3,4}', '', vendor)
    
    # Normalize gas stations
    if 'CENTEX' in vendor or 'FAS GAS' in vendor:
        return 'FUEL_STATION'
    if 'SHELL' in vendor or 'ESSO' in vendor or 'PETRO' in vendor or 'HUSKY' in vendor:
        return 'FUEL_STATION'
    
    # Normalize restaurants
    if any(word in vendor for word in ['RESTAURANT', 'CAFE', 'COFFEE', 'TIM HORTONS', 'A&W', 'MCDONALDS']):
        return 'RESTAURANT'
    
    return vendor.strip()

def categorize_by_description(vendor, description, amount):
    """Smart categorization based on vendor and description patterns."""
    
    vendor_norm = normalize_vendor(vendor)
    desc_upper = (description or '').upper()
    combined = f"{vendor_norm} {desc_upper}"
    
    # Fuel - 5110
    if any(word in combined for word in ['FUEL', 'GAS', 'DIESEL', 'PETROL', 'FUEL_STATION', 'CENTEX', 'FAS GAS', 'SHELL']):
        return ('5110', 'fuel', 90)
    
    # Vehicle maintenance - 5120
    if any(word in combined for word in ['REPAIR', 'MAINTENANCE', 'TIRE', 'OIL CHANGE', 'MIDAS', 'JIFFY', 'AUTO', 'PARTS']):
        return ('5120', 'maintenance', 85)
    
    # Insurance - 5130
    if any(word in combined for word in ['INSURANCE', 'SGI', 'AVIVA', 'JEVCO', 'POLICY', 'PREMIUM']):
        return ('5130', 'insurance', 95)
    
    # Licenses/Permits - 5140
    if any(word in combined for word in ['LICENSE', 'PERMIT', 'REGISTRATION', 'RENEWAL']):
        return ('5140', 'licenses', 90)
    
    # Payroll - 5210
    if any(word in combined for word in ['PAYROLL', 'WAGES', 'SALARY', 'EMPLOYEE', 'DRIVER PAY']):
        return ('5210', 'payroll', 95)
    
    # Driver meals - 5320
    if 'RESTAURANT' in vendor_norm and amount < 50:
        return ('5320', 'driver_meals', 80)
    
    # Business meals - 5325
    if 'RESTAURANT' in vendor_norm and amount >= 50:
        return ('5325', 'business_meals', 75)
    
    # Rent - 5410
    if any(word in combined for word in ['RENT', 'LEASE PAYMENT', 'LANDLORD']):
        return ('5410', 'rent', 95)
    
    # Office supplies - 5420
    if any(word in combined for word in ['STAPLES', 'OFFICE', 'SUPPLIES', 'PAPER', 'PRINTER']):
        return ('5420', 'office', 85)
    
    # Communication - 5430
    if any(word in combined for word in ['TELUS', 'ROGERS', 'BELL', 'SASKTEL', 'PHONE', 'INTERNET', 'WIRELESS']):
        return ('5430', 'communication', 90)
    
    # Utilities - 5440
    if any(word in combined for word in ['ENMAX', 'ATCO', 'EPCOR', 'ELECTRIC', 'WATER', 'UTILITIES', 'GAS BILL']):
        return ('5440', 'utilities', 90)
    
    # Professional fees - 5510
    if any(word in combined for word in ['ACCOUNTANT', 'LAWYER', 'LEGAL', 'PROFESSIONAL', 'CONSULTANT']):
        return ('5510', 'professional', 85)
    
    # Advertising - 5610
    if any(word in combined for word in ['ADVERTISING', 'MARKETING', 'PROMOTION', 'YELLOW PAGES', 'AD']):
        return ('5610', 'advertising', 85)
    
    # Bank charges - 5710
    if any(word in combined for word in ['BANK', 'SERVICE CHARGE', 'FEE', 'NSF', 'OVERDRAFT']):
        return ('5710', 'bank_charges', 95)
    
    # Credit card fees - 5720
    if any(word in combined for word in ['MCC PAYMENT', 'MERCHANT', 'PROCESSING FEE', 'AMEX', 'VISA FEE']):
        return ('5720', 'cc_fees', 90)
    
    # Equipment rental - 5820
    if any(word in combined for word in ['RENTAL', 'LEASE EQUIPMENT', 'TOOL RENTAL']):
        return ('5820', 'equipment_rental', 85)
    
    # Vehicle loan payments - 2210
    if any(word in combined for word in ['HEFFNER', 'AUTO FINANCE', 'VEHICLE LOAN', 'CAR LOAN', 'AARON MACHINE']):
        return ('2210', 'vehicle_loan', 95)
    
    # Uncategorized - 5850
    return ('5850', 'mixed_use', 50)

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("CATEGORIZING 2012 UNCATEGORIZED RECEIPTS")
    print("="*80)
    
    # Get uncategorized receipts from 2012
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            description,
            gross_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND (gl_account_code IS NULL OR gl_account_code = '')
        ORDER BY gross_amount DESC
    """)
    
    receipts = cur.fetchall()
    
    print(f"\nFound {len(receipts):,} uncategorized receipts")
    print("\nCategorizing...")
    
    # Categorize each receipt
    results = {}
    for receipt in receipts:
        receipt_id = receipt[0]
        date = receipt[1]
        vendor = receipt[2]
        description = receipt[3]
        amount = float(receipt[4]) if receipt[4] else 0
        
        gl_code, category, confidence = categorize_by_description(vendor, description, amount)
        
        if gl_code not in results:
            results[gl_code] = {'count': 0, 'amount': 0, 'items': []}
        
        results[gl_code]['count'] += 1
        results[gl_code]['amount'] += amount
        results[gl_code]['items'].append({
            'receipt_id': receipt_id,
            'vendor': vendor,
            'amount': amount,
            'category': category,
            'confidence': confidence
        })
    
    # Show results
    print("\n" + "="*80)
    print("CATEGORIZATION RESULTS")
    print("="*80)
    
    total_amount = 0
    for gl_code in sorted(results.keys()):
        count = results[gl_code]['count']
        amount = results[gl_code]['amount']
        total_amount += amount
        
        avg_confidence = sum(item['confidence'] for item in results[gl_code]['items']) / count
        
        print(f"\n{gl_code}: {count:5d} receipts = ${amount:12,.2f} (avg confidence {avg_confidence:.0f}%)")
        
        # Show top 3 vendors per category
        items_sorted = sorted(results[gl_code]['items'], key=lambda x: x['amount'], reverse=True)[:3]
        for item in items_sorted:
            vendor = (item['vendor'] or 'Unknown')[:40]
            print(f"  • {vendor:40s} ${item['amount']:10,.2f}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {len(receipts):,} receipts = ${total_amount:,.2f}")
    print(f"{'='*80}")
    
    # Ask for confirmation
    print("\nApply these categorizations? (yes/no): ", end='')
    response = input().strip().lower()
    
    if response != 'yes':
        print("Cancelled - no changes made")
        conn.close()
        return
    
    # Apply updates
    print("\nApplying updates...")
    updated = 0
    
    for gl_code, data in results.items():
        for item in data['items']:
            cur.execute("""
                UPDATE receipts
                SET gl_account_code = %s,
                    category = %s,
                    auto_categorized = TRUE
                WHERE receipt_id = %s
            """, (gl_code, item['category'], item['receipt_id']))
            updated += 1
    
    conn.commit()
    
    print(f"✓ Updated {updated:,} receipts")
    
    # Show new expense totals
    print("\n" + "="*80)
    print("UPDATED 2012 EXPENSE ANALYSIS")
    print("="*80)
    
    cur.execute("""
        SELECT 
            SUM(gross_amount) as total_expenses
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^5'
    """)
    
    expenses = float(cur.fetchone()[0] or 0)
    
    print(f"\nTotal categorized expenses: ${expenses:,.2f}")
    print(f"Previous (only payroll): $130,244.32")
    print(f"Increase: ${expenses - 130244.32:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
