#!/usr/bin/env python3
"""
Categorize e-transfers based on known recipient/sender patterns.

Categories:
- David Richard: Loan/Loan payments
- Drayden Insurance: Auto insurance
- Jason Rogers: Pay/Reimbursements (or shop furnace repair)
- Vanessa Thomas / Heffner: Auto lease payments
- Jeannie: Driver pay
- Mike Woodrow: Rent (or vehicle repairs)

Usage:
    python categorize_etransfer_by_name.py --dry-run
    python categorize_etransfer_by_name.py --write
"""

import os
import sys
import psycopg2
import re

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

DRY_RUN = '--write' not in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

# Categorization rules based on name patterns
CATEGORY_RULES = {
    'loan_payment': {
        'patterns': ['david richard', 'david w richard', 'davidrichard'],
        'description': 'Loan/Loan payments'
    },
    'auto_insurance': {
        'patterns': ['drayden', 'insurance'],
        'description': 'Auto insurance'
    },
    'employee_pay_reimbursement': {
        'patterns': ['jason rogers', 'jasonrogers', 'armor heatco'],
        'description': 'Employee pay/reimbursements (or shop furnace repair)'
    },
    'auto_lease_payment': {
        'patterns': ['vanessa thomas', 'vanessathomas', 'heffner', 'will heffner', 'willheffner'],
        'description': 'Auto lease payments'
    },
    'driver_pay': {
        'patterns': ['jeannie', 'jeannie shillington'],
        'description': 'Driver pay'
    },
    'rent_vehicle_repairs': {
        'patterns': ['mike woodrow', 'mikewoodrow'],
        'description': 'Rent (or vehicle repairs)'
    },
    'hospitality_supplies': {
        'patterns': ['liquor', 'the liquor hutc', 'liquor hutc', 'bar', 'beverage'],
        'description': 'Hospitality supplies (liquor/beverages for charters)'
    },
    'bookkeeping_services': {
        'patterns': ['serena', 'serena book keeper', 'bookkeeper', 'book keeper'],
        'description': 'Bookkeeping services'
    },
    'telecommunications': {
        'patterns': ['telus', 'shaw', 'rogers telecom', 'bell', 'sasktel'],
        'description': 'Telecommunications (phone/internet)'
    },
    'office_rent': {
        'patterns': ['fibrenew office', 'office rent'],
        'description': 'Office rent'
    },
    'vehicle_storage': {
        'patterns': ['shop rent', 'parking rent', 'storage rent'],
        'description': 'Vehicle storage/parking rent'
    },
    'banking_fees': {
        'patterns': ['bank charge', 'service charge', 'account fee', 'overdraft', 'nsf'],
        'description': 'Banking fees and service charges'
    },
    'check_cashing': {
        'patterns': ['money mart', 'moneymart'],
        'description': 'Check cashing fees'
    },
    'fuel': {
        'patterns': ['604 - lb', '604-lb', 'run n on empty', 'runn on empty', 'mohawk', 
                    'shell', 'esso', 'petro', 'centex', 'fas gas', 'husky', 'co-op', 'chevron'],
        'description': 'Fuel purchases'
    }
}

def categorize_by_description(description):
    """Return category based on description pattern matching."""
    if not description:
        return None, None
    
    desc_lower = description.lower()
    
    for category, rules in CATEGORY_RULES.items():
        for pattern in rules['patterns']:
            if pattern in desc_lower:
                return category, rules['description']
    
    return None, None

def main():
    print("\n" + "="*100)
    print("E-TRANSFER CATEGORIZATION BY RECIPIENT/SENDER NAME")
    print("="*100)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Add category column if it doesn't exist
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'etransfer_transactions' 
            AND column_name = 'category'
        """)
        
        if not cur.fetchone():
            print("\n1. Adding 'category' column to etransfer_transactions...")
            cur.execute("""
                ALTER TABLE etransfer_transactions 
                ADD COLUMN category VARCHAR(50),
                ADD COLUMN category_description TEXT
            """)
            print("   ✓ Column added")
        else:
            print("\n1. Category column already exists")
        
        # Get all e-transfers with banking descriptions
        print("\n2. Fetching e-transfers with banking transaction links...")
        cur.execute("""
            SELECT 
                et.etransfer_id,
                et.direction,
                et.transaction_date,
                et.amount,
                bt.description
            FROM etransfer_transactions et
            JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
            WHERE bt.description IS NOT NULL
            ORDER BY et.amount DESC
        """)
        
        etransfers = cur.fetchall()
        print(f"   Found {len(etransfers):,} e-transfers with banking descriptions")
        
        # Categorize each
        print("\n3. Categorizing e-transfers...")
        categorized = {
            'loan_payment': [],
            'auto_insurance': [],
            'employee_pay_reimbursement': [],
            'auto_lease_payment': [],
            'driver_pay': [],
            'rent_vehicle_repairs': [],
            'hospitality_supplies': [],
            'bookkeeping_services': [],
            'telecommunications': [],
            'office_rent': [],
            'vehicle_storage': [],
            'banking_fees': [],
            'check_cashing': [],
            'fuel': [],
            'uncategorized': []
        }
        
        for etrans_id, direction, tdate, amount, description in etransfers:
            category, cat_desc = categorize_by_description(description)
            
            if category:
                categorized[category].append({
                    'id': etrans_id,
                    'direction': direction,
                    'date': tdate,
                    'amount': amount,
                    'description': description
                })
                
                if not DRY_RUN:
                    cur.execute("""
                        UPDATE etransfer_transactions
                        SET category = %s,
                            category_description = %s
                        WHERE etransfer_id = %s
                    """, (category, cat_desc, etrans_id))
            else:
                categorized['uncategorized'].append({
                    'id': etrans_id,
                    'direction': direction,
                    'date': tdate,
                    'amount': amount,
                    'description': description
                })
        
        # Print summary
        print("\n" + "="*100)
        print("CATEGORIZATION SUMMARY")
        print("="*100)
        
        for category in ['loan_payment', 'auto_insurance', 'employee_pay_reimbursement', 
                        'auto_lease_payment', 'driver_pay', 'rent_vehicle_repairs']:
            items = categorized[category]
            if items:
                total = sum(item['amount'] for item in items)
                print(f"\n{CATEGORY_RULES[category]['description']}:")
                print(f"  Count: {len(items):,}")
                print(f"  Total: ${total:,.2f}")
                print(f"  Samples (top 5):")
                for i, item in enumerate(items[:5]):
                    print(f"    {item['date']} | {item['direction']:3} | ${item['amount']:>10,.2f} | {item['description'][:60]}")
        
        # Uncategorized
        uncat = categorized['uncategorized']
        if uncat:
            total = sum(item['amount'] for item in uncat)
            print(f"\nUncategorized:")
            print(f"  Count: {len(uncat):,}")
            print(f"  Total: ${total:,.2f}")
        
        # Generate detailed report by category
        print("\n" + "="*100)
        print("DETAILED BREAKDOWN BY CATEGORY")
        print("="*100)
        
        for category in ['loan_payment', 'auto_insurance', 'employee_pay_reimbursement', 
                        'auto_lease_payment', 'driver_pay', 'rent_vehicle_repairs']:
            items = categorized[category]
            if not items:
                continue
            
            print(f"\n{CATEGORY_RULES[category]['description'].upper()} ({len(items):,} transactions)")
            print("-" * 100)
            
            # Group by direction
            incoming = [x for x in items if x['direction'] == 'IN']
            outgoing = [x for x in items if x['direction'] == 'OUT']
            
            if incoming:
                total_in = sum(x['amount'] for x in incoming)
                print(f"  INCOMING: {len(incoming):,} transactions, ${total_in:,.2f}")
                for item in incoming[:10]:
                    print(f"    {item['date']} | ${item['amount']:>10,.2f} | {item['description'][:65]}")
            
            if outgoing:
                total_out = sum(x['amount'] for x in outgoing)
                print(f"  OUTGOING: {len(outgoing):,} transactions, ${total_out:,.2f}")
                for item in outgoing[:10]:
                    print(f"    {item['date']} | ${item['amount']:>10,.2f} | {item['description'][:65]}")
        
        if DRY_RUN:
            conn.rollback()
            print("\n[DRY RUN] No changes saved to database.")
            print("Run with --write to apply categorizations.")
        else:
            conn.commit()
            print("\n[SUCCESS] Categorizations committed to database.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "="*100)

if __name__ == '__main__':
    main()
