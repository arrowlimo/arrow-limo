#!/usr/bin/env python3
"""
Smart Expense Categorization System
Intelligently categorizes receipts and banking transactions into proper GL accounts.
Handles grey-area expenses by matching patterns to similar legitimate business categories.
Tracks beverage cost recovery, entertainment deductions, promotional expenses, etc.

"Color just outside the lines" approach - if a similar business category exists,
classify borderline items there rather than personal (with proper documentation).
"""

import psycopg2
from datetime import datetime
import argparse
import re
from collections import defaultdict

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

# Intelligent categorization rules with business justification
CATEGORY_RULES = {
    # Customer Service - Beverages (5310)
    'customer_beverages': {
        'account': '5310',
        'patterns': [
            r'COSTCO.*WATER|WATER.*COSTCO',  # Bulk water for customers
            r'7-?ELEVEN.*DRINKS?|POP|SODA|SOFT DRINK',
            r'WALMART.*BEVERAGE|BEVERAGE.*WALMART',
            r'CHIPS?|SNACKS?|CANDY',  # Customer amenities
            r'ICE.*COOLER|COOLER.*ICE',  # Ice for beverages
        ],
        'justification': 'Provided to customers during charter service',
        'recoverable': True,  # Track if charged to customer (compare to 4115)
    },
    
    # Business Entertainment - Beverages (5315)
    'entertainment_beverages': {
        'account': '5315',
        'patterns': [
            r'LIQUOR|BAR|PUB|TAVERN',
            r'WINE|BEER|SPIRITS?|VODKA|WHISKEY',
            r'HOSPITALITY',
        ],
        'justification': 'Client entertainment, business meetings at bars/restaurants (50% deductible)',
        'tax_note': '50% deductible per CRA rules',
    },
    
    # Driver Meals - On Duty (5320)
    'driver_meals': {
        'account': '5320',
        'patterns': [
            r'TIM HORTONS?|TIMS',
            r'MCDONALDS?',
            r'SUBWAY',
            r'A&W',
            r'BURGER KING',
            r'COFFEE|DONUT',
        ],
        'conditions': {
            'time_range': (5, 23),  # 5am-11pm (driver shift times)
            'max_amount': 25.00,  # Reasonable meal amount
        },
        'justification': 'Meal during charter shift (employer-provided working conditions)',
    },
    
    # Business Meals & Entertainment (5325)
    'business_meals': {
        'account': '5325',
        'patterns': [
            r'RESTAURANT',
            r'STEAKHOUSE|STEAK HOUSE',
            r'DINER|CAFE|BISTRO',
            r'DINING',
        ],
        'conditions': {
            'min_amount': 25.00,  # Too expensive for driver meal
            'description_keywords': ['CLIENT', 'MEETING', 'BUSINESS'],
        },
        'justification': 'Client meeting, prospect entertainment, business networking (50% deductible)',
        'tax_note': '50% deductible per CRA rules - document attendees',
    },
    
    # Vehicle Fuel (5110)
    'fuel': {
        'account': '5110',
        'patterns': [
            r'FAS GAS|FASGAS',
            r'CENTEX|CENTX',
            r'SHELL',
            r'ESSO',
            r'PETRO[- ]?CAN',
            r'HUSKY',
            r'CO-?OP.*GAS|GAS.*CO-?OP',
            r'CANADIAN TIRE.*GAS',
            r'\bFUEL\b',
        ],
        'justification': 'Fleet vehicle fuel - 100% business use',
    },
    
    # Vehicle Maintenance (5120)
    'maintenance': {
        'account': '5120',
        'patterns': [
            r'CANADIAN TIRE(?!.*GAS)',  # Canadian Tire but NOT gas
            r'JIFFY LUBE',
            r'MIDAS',
            r'TIRE|WHEEL',
            r'AUTO.*PARTS?|PARTS?.*AUTO',
            r'CAR WASH|WASH.*CAR',
            r'OIL CHANGE',
            r'BRAKE|REPAIR',
        ],
        'justification': 'Vehicle maintenance - 100% business use',
    },
    
    # Promotional Gifts (5640)
    'promotional': {
        'account': '5640',
        'patterns': [
            r'GIFT|GIVEAWAY',
            r'PROMOTIONAL',
            r'CLIENT.*GIFT',
            r'REFERRAL.*BONUS',
        ],
        'conditions': {
            'max_amount': 200.00,  # Reasonable gift amount
        },
        'justification': 'Client appreciation, referral incentives, promotional items',
    },
    
    # Charitable Donations (5650)
    'charity': {
        'account': '5650',
        'patterns': [
            r'CHARITY|CHARITABLE',
            r'DONATION',
            r'SPONSOR',
            r'FUNDRAISER',
            r'NON-?PROFIT',
        ],
        'justification': 'Community relations, event sponsorships (requires tax receipt)',
        'tax_note': 'Verify registered charity for tax credit',
    },
    
    # Trade of Services (5660)
    'trade': {
        'account': '5660',
        'patterns': [
            r'FIBRENEW',  # Known trade arrangement
            r'TRADE.*SERVICE|SERVICE.*TRADE',
            r'BARTER',
        ],
        'justification': 'Services traded at fair market value (e.g., Fibrenew rent for charter service)',
        'tax_note': 'Record FMV as both income (4135) and expense (5660)',
    },
    
    # Business Development (5840)
    'business_dev': {
        'account': '5840',
        'patterns': [
            r'CONFERENCE|CONVENTION',
            r'NETWORKING',
            r'TRADE SHOW',
            r'SEMINAR|WORKSHOP',
            r'CHAMBER.*COMMERCE',
            r'BUSINESS.*ASSOCIATION',
        ],
        'justification': 'Industry events, networking, business relationship building',
    },
    
    # Mixed-Use Expenses (5850) - Grey Area Category
    'mixed_use': {
        'account': '5850',
        'patterns': [
            r'COSTCO(?!.*WATER)',  # Costco but NOT water (could be personal + business)
            r'WALMART(?!.*BEVERAGE)',  # Walmart but NOT beverages
            r'AMAZON',  # Could be business or personal
            r'PHONE.*UPGRADE|UPGRADE.*PHONE',  # New phone (personal + business use)
            r'LAPTOP|COMPUTER(?!.*REPAIR)',  # New computer (track allocation)
        ],
        'conditions': {
            'requires_review': True,
            'allocation_required': True,
        },
        'justification': 'Mixed personal/business use - track allocation percentage',
        'tax_note': 'Document business use % (e.g., 80% business, 20% personal)',
    },
    
    # Office Supplies (5420)
    'office': {
        'account': '5420',
        'patterns': [
            r'STAPLES',
            r'OFFICE DEPOT',
            r'PAPER|PRINTER|INK|TONER',
            r'PENS?|PENCILS?|MARKERS?',
        ],
        'justification': 'Office supplies for business operations',
    },
    
    # Communication (5430)
    'communication': {
        'account': '5430',
        'patterns': [
            r'TELUS|ROGERS|BELL|SASKTEL',
            r'PHONE.*BILL|CELL.*BILL',
            r'INTERNET.*BILL',
        ],
        'justification': 'Business phone, internet for operations',
    },
    
    # Insurance (5130)
    'insurance': {
        'account': '5130',
        'patterns': [
            r'INSURANCE',
            r'SGI',
            r'AVIVA',
            r'JEVCO',
        ],
        'justification': 'Vehicle/business insurance - 100% deductible',
    },
    
    # General Business Supplies (5860)
    'general_supplies': {
        'account': '5860',
        'patterns': [
            r'CLEANING.*SUPPL|SUPPL.*CLEANING',
            r'TOOLS?',
            r'HARDWARE',
            r'SUPPLIES?',
        ],
        'justification': 'General business supplies - cleaning, tools, equipment',
    },
    
    # Banking Fees (5710)
    'banking': {
        'account': '5710',
        'patterns': [
            r'\bFEE\b|FEES\b',
            r'BANK.*CHARGE|CHARGE.*BANK',
            r'NSF',
            r'OVERDRAFT',
            r'SERVICE CHARGE',
        ],
        'justification': 'Bank fees, transaction charges - 100% business',
    },
}

# Personal expense indicators (move to 5880 Owner Personal)
PERSONAL_INDICATORS = [
    r'GROCERY(?!.*WATER|.*BEVERAGE)',  # Grocery shopping (not business supplies)
    r'CLOTHING(?!.*UNIFORM)',  # Clothing (not uniforms)
    r'PERSONAL',
    r'BARBER|HAIRCUT|SALON',
    r'PHARMACY(?!.*FIRST AID)',  # Pharmacy (not first aid kit)
    r'FURNITURE(?!.*OFFICE)',  # Furniture (not office furniture)
    r'ENTERTAINMENT(?!.*BUSINESS|.*CLIENT)',  # Personal entertainment
    r'VACATION|HOLIDAY(?!.*BUSINESS)',
    r'GYM|FITNESS(?!.*DRIVER)',  # Personal fitness
]

def smart_categorize(description, amount, transaction_date, notes=''):
    """
    Intelligently categorize expense with business justification.
    Returns: (account_code, category_name, confidence, justification, tax_note)
    """
    description_upper = description.upper()
    notes_upper = notes.upper() if notes else ''
    combined = f"{description_upper} {notes_upper}"
    
    # Check if clearly personal first
    for pattern in PERSONAL_INDICATORS:
        if re.search(pattern, combined):
            return ('5880', 'personal', 100, 'Clearly personal expense', 'Non-deductible - move to Owner Draw 3020')
    
    # Try to match business categories
    matches = []
    
    for category_name, rules in CATEGORY_RULES.items():
        confidence = 0
        
        # Check pattern matching
        for pattern in rules['patterns']:
            if re.search(pattern, combined):
                confidence = 80  # Base confidence for pattern match
                break
        
        if confidence == 0:
            continue  # No pattern match
        
        # Check conditions if they exist
        if 'conditions' in rules:
            conditions = rules['conditions']
            
            # Time range check (for driver meals)
            if 'time_range' in conditions:
                hour = transaction_date.hour if hasattr(transaction_date, 'hour') else 12
                time_range = conditions['time_range']
                if hour < time_range[0] or hour > time_range[1]:
                    confidence -= 20  # Outside typical shift hours
            
            # Amount checks
            if 'max_amount' in conditions and amount > conditions['max_amount']:
                confidence -= 30  # Exceeds reasonable amount
            
            if 'min_amount' in conditions and amount < conditions['min_amount']:
                confidence -= 20  # Below threshold
            
            # Keyword checks
            if 'description_keywords' in conditions:
                has_keyword = any(kw in combined for kw in conditions['description_keywords'])
                if has_keyword:
                    confidence += 15  # Boost confidence
        
        # Boost confidence if description is very clear
        if category_name in description_upper:
            confidence += 10
        
        matches.append((
            rules['account'],
            category_name,
            min(confidence, 100),
            rules['justification'],
            rules.get('tax_note', '')
        ))
    
    if not matches:
        # No clear match - categorize as mixed-use for review
        return ('5850', 'mixed_use', 50, 'Unclear business purpose - requires review', 
                'Review and document business use or move to Owner Draw')
    
    # Return best match
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches[0]

def analyze_receipts(conn, dry_run=True):
    """Analyze and categorize all receipts."""
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("SMART EXPENSE CATEGORIZATION - Receipt Analysis")
    print("="*80)
    
    # Get uncategorized receipts (no account_code or account_code is NULL)
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts 
        WHERE (gl_account_code IS NULL OR gl_account_code = '')
        AND (business_personal IS NULL OR business_personal != 'personal')
        ORDER BY receipt_date DESC
        LIMIT 500
    """)
    
    uncategorized = cur.fetchall()
    print(f"\nFound {len(uncategorized)} uncategorized business receipts")
    
    if len(uncategorized) == 0:
        print("No uncategorized receipts found!")
        return
    
    # Categorize each receipt
    results = defaultdict(list)
    high_confidence = 0
    needs_review = 0
    personal_flagged = 0
    
    for receipt_id, date, vendor, amount, desc in uncategorized:
        account, category, confidence, justification, tax_note = smart_categorize(
            f"{vendor} {desc or ''}",
            amount,
            date,
            ''  # notes field doesn't exist yet
        )
        
        results[account].append({
            'receipt_id': receipt_id,
            'date': date,
            'vendor': vendor,
            'amount': amount,
            'category': category,
            'confidence': confidence,
            'justification': justification,
            'tax_note': tax_note
        })
        
        if confidence >= 80:
            high_confidence += 1
        elif confidence < 70:
            needs_review += 1
        
        if account == '5880':
            personal_flagged += 1
    
    # Print summary
    print(f"\nCategorization Results:")
    print(f"  High Confidence (>=80%): {high_confidence}")
    print(f"  Needs Review (<70%): {needs_review}")
    print(f"  Personal Flagged: {personal_flagged}")
    
    print(f"\nBreakdown by Account:")
    for account in sorted(results.keys()):
        items = results[account]
        total = sum(item['amount'] for item in items)
        print(f"  {account}: {len(items)} receipts (${total:,.2f})")
        
        # Show samples
        for item in items[:3]:
            print(f"    • {item['vendor'][:30]:30} ${item['amount']:7.2f} ({item['confidence']}%) - {item['justification']}")
        
        if len(items) > 3:
            print(f"    ... and {len(items)-3} more")
    
    # Apply updates if not dry run
    if not dry_run:
        print(f"\n{'='*80}")
        print("APPLYING CATEGORIZATIONS...")
        updated = 0
        
        for account, items in results.items():
            for item in items:
                cur.execute("""
                    UPDATE receipts
                    SET gl_account_code = %s,
                        category = %s,
                        auto_categorized = TRUE
                    WHERE receipt_id = %s
                """, (
                    account,
                    item['category'],
                    item['receipt_id']
                ))
                updated += 1
        
        conn.commit()
        print(f"✓ Updated {updated} receipts")
    else:
        print(f"\n{'='*80}")
        print("DRY RUN - No changes made. Use --write to apply categorizations.")
    
    cur.close()

def generate_beverage_recovery_report(conn):
    """Compare beverage costs (5310) to beverage revenue (4115)."""
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("BEVERAGE COST RECOVERY ANALYSIS")
    print("="*80)
    
    # Get beverage costs
    cur.execute("""
        SELECT EXTRACT(YEAR FROM receipt_date) as year,
               COUNT(*) as receipt_count,
               SUM(gross_amount) as total_cost
        FROM receipts
        WHERE account_code = '5310'
        AND receipt_date >= '2012-01-01'
        GROUP BY year
        ORDER BY year DESC
    """)
    costs = cur.fetchall()
    
    # Get beverage revenue
    cur.execute("""
        SELECT EXTRACT(YEAR FROM charter_date) as year,
               COUNT(*) as charter_count,
               SUM(beverage_charges) as total_revenue
        FROM charters
        WHERE beverage_charges > 0
        AND charter_date >= '2012-01-01'
        GROUP BY year
        ORDER BY year DESC
    """)
    revenue = cur.fetchall()
    
    print(f"\n{'Year':>6} {'Receipts':>10} {'Cost':>12} {'Charters':>10} {'Revenue':>12} {'Net':>12} {'Recovery %':>12}")
    print("-" * 80)
    
    cost_dict = {int(year): (count, cost) for year, count, cost in costs}
    rev_dict = {int(year): (count, rev) for year, count, rev in revenue} if revenue else {}
    
    for year in sorted(cost_dict.keys(), reverse=True):
        count_cost, total_cost = cost_dict[year]
        count_rev, total_rev = rev_dict.get(year, (0, 0))
        
        net = (total_rev or 0) - (total_cost or 0)
        recovery_pct = ((total_rev or 0) / (total_cost or 0) * 100) if total_cost else 0
        
        print(f"{year:6} {count_cost:10} ${total_cost:11,.2f} {count_rev:10} ${total_rev or 0:11,.2f} ${net:11,.2f} {recovery_pct:11.1f}%")
    
    print("\nNote: Negative net = losing money on beverages (undercharging customers)")
    print("      Recovery % < 100% = not fully recovering costs")
    
    cur.close()

def main():
    parser = argparse.ArgumentParser(description='Smart expense categorization system')
    parser.add_argument('--write', action='store_true', help='Apply categorizations (default: dry-run)')
    parser.add_argument('--beverage-report', action='store_true', help='Generate beverage cost recovery report')
    args = parser.parse_args()
    
    conn = get_db_connection()
    
    try:
        if args.beverage_report:
            generate_beverage_recovery_report(conn)
        else:
            analyze_receipts(conn, dry_run=not args.write)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
