#!/usr/bin/env python3
"""
CHARTER CHARGE MATCHING ENGINE
==============================

Uses the charter_charges table to match and categorize extra charges
across charters, payments, and receipts for complete financial tracking.
"""

import os
import psycopg2
from datetime import datetime
import re

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_charge_patterns():
    """Analyze existing charge patterns for matching rules."""
    
    print("📊 CHARTER CHARGE PATTERN ANALYSIS")
    print("=" * 35)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get detailed charge breakdown with amounts
    cur.execute("""
        SELECT 
            charge_type,
            description,
            COUNT(*) as frequency,
            ROUND(AVG(amount), 2) as avg_amount,
            ROUND(MIN(amount), 2) as min_amount,
            ROUND(MAX(amount), 2) as max_amount,
            ROUND(SUM(amount), 2) as total_amount
        FROM charter_charges 
        WHERE amount IS NOT NULL AND amount != 0
        GROUP BY charge_type, description
        ORDER BY frequency DESC, total_amount DESC
        LIMIT 20
    """)
    
    patterns = cur.fetchall()
    
    print("🔍 TOP CHARGE PATTERNS:")
    print(f"{'Description':<25} {'Freq':<6} {'Avg $':<8} {'Total $':<12}")
    print("-" * 60)
    
    for charge_type, desc, freq, avg_amt, min_amt, max_amt, total_amt in patterns:
        desc_short = (desc[:22] + '...') if desc and len(desc) > 22 else (desc or 'No desc')
        print(f"{desc_short:<25} {freq:<6} ${avg_amt:<7} ${total_amt:<11,.2f}")
    
    # Analyze charge categories
    print(f"\n📋 CHARGE CATEGORIES:")
    
    charge_categories = {
        'Service Fees': ['Service Fee', 'Misc Fee', 'Misc Charges'],
        'Taxes': ['G.S.T.', 'GST', 'Tax'],
        'Gratuities': ['Gratuity', 'Extra Gratuity', 'Driver tip', 'Customer gratuity'],
        'Fuel': ['Fuel Surcharge', 'Gas Surcharge'],
        'Beverages': ['Beverage Order', 'Beverage Charge'],
        'Transportation': ['Airport Fee', 'Extra Stops', 'Wait / Travel Time', 'Parking Fee'],
        'Cleaning': ['Clean Up Fee', 'Broken Glass'],
        'Discounts': ['Discount Flat', 'Discount']
    }
    
    for category, keywords in charge_categories.items():
        cur.execute("""
            SELECT COUNT(*), ROUND(SUM(amount), 2)
            FROM charter_charges 
            WHERE description = ANY(%s)
            AND amount IS NOT NULL
        """, (keywords,))
        
        count, total = cur.fetchone()
        if count and count > 0:
            print(f"   • {category}: {count:,} charges, ${total:,.2f} total")
    
    cur.close()
    conn.close()

def create_charge_matching_rules():
    """Create standardized charge matching rules."""
    
    print(f"\n🔧 CHARGE MATCHING RULES")
    print("-" * 24)
    
    # Define matching rules with patterns and categories
    matching_rules = {
        'airport_fee': {
            'patterns': ['airport', 'yeg', 'yvr', 'yyc', 'departure', 'arrival'],
            'category': 'Transportation',
            'typical_range': (10.0, 100.0),
            'description_templates': ['Airport Fee', 'Airport Surcharge', 'Departure Fee']
        },
        'beverage_service': {
            'patterns': ['beverage', 'drink', 'alcohol', 'champagne', 'wine', 'beer'],
            'category': 'Beverages', 
            'typical_range': (5.0, 500.0),
            'description_templates': ['Beverage Order', 'Beverage Charge', 'Alcohol Service']
        },
        'fuel_surcharge': {
            'patterns': ['fuel', 'gas', 'surcharge', 'distance'],
            'category': 'Fuel',
            'typical_range': (5.0, 200.0),
            'description_templates': ['Fuel Surcharge', 'Distance Surcharge']
        },
        'gratuity': {
            'patterns': ['tip', 'gratuity', 'service charge'],
            'category': 'Gratuities',
            'typical_range': (5.0, 1000.0),
            'description_templates': ['Gratuity', 'Extra Gratuity', 'Service Tip']
        },
        'extra_stops': {
            'patterns': ['stop', 'pickup', 'dropoff', 'detour', 'additional'],
            'category': 'Transportation',
            'typical_range': (10.0, 100.0),
            'description_templates': ['Extra Stops', 'Additional Pickup', 'Extra Destination']
        },
        'wait_time': {
            'patterns': ['wait', 'delay', 'overtime', 'extended'],
            'category': 'Transportation',
            'typical_range': (15.0, 300.0),
            'description_templates': ['Wait / Travel Time', 'Extended Service', 'Overtime']
        },
        'parking': {
            'patterns': ['park', 'valet', 'lot'],
            'category': 'Transportation',
            'typical_range': (5.0, 50.0),
            'description_templates': ['Parking Fee', 'Valet Service']
        },
        'cleaning': {
            'patterns': ['clean', 'damage', 'broken', 'spill'],
            'category': 'Cleaning',
            'typical_range': (25.0, 500.0),
            'description_templates': ['Clean Up Fee', 'Damage Fee', 'Broken Glass']
        },
        'gst_hst': {
            'patterns': ['gst', 'hst', 'tax'],
            'category': 'Taxes',
            'typical_range': (1.0, 1000.0),
            'description_templates': ['G.S.T.', 'HST', 'Tax']
        }
    }
    
    for rule_name, rule_data in matching_rules.items():
        patterns_str = ', '.join(rule_data['patterns'][:3]) + '...'
        range_str = f"${rule_data['typical_range'][0]} - ${rule_data['typical_range'][1]}"
        print(f"   • {rule_name}: {patterns_str} ({range_str})")
    
    return matching_rules

def match_unmatched_charges(matching_rules, dry_run=True):
    """Match unmatched charges using the defined rules."""
    
    print(f"\n🔍 MATCHING UNMATCHED CHARGES")
    print("-" * 27)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find potential unmatched charges (receipts, payments without clear categorization)
    cur.execute("""
        SELECT 
            'receipts' as source_table,
            receipt_id as source_id,
            vendor_name,
            description,
            gross_amount as amount,
            receipt_date as transaction_date
        FROM receipts 
        WHERE category IS NULL OR category = 'uncategorized'
        AND gross_amount > 5.00
        
        UNION ALL
        
        SELECT 
            'payments' as source_table,
            payment_id as source_id,
            last_updated_by as vendor_name,
            notes as description, 
            amount,
            payment_date as transaction_date
        FROM payments 
        WHERE notes ILIKE '%charge%' OR notes ILIKE '%fee%'
        AND amount > 5.00
        
        ORDER BY amount DESC
        LIMIT 50
    """)
    
    unmatched_items = cur.fetchall()
    
    if not unmatched_items:
        print("   [OK] No unmatched charges found")
        cur.close()
        conn.close()
        return
    
    print(f"   📊 Found {len(unmatched_items):,} potential unmatched charges")
    
    matches_found = 0
    
    for source_table, source_id, vendor, description, amount, trans_date in unmatched_items:
        
        # Combine vendor and description for matching
        search_text = f"{vendor or ''} {description or ''}".lower()
        
        matched_rule = None
        confidence = 0
        
        # Try to match against rules
        for rule_name, rule_data in matching_rules.items():
            rule_confidence = 0
            
            # Check pattern matches
            for pattern in rule_data['patterns']:
                if pattern.lower() in search_text:
                    rule_confidence += 1
            
            # Check amount range
            if rule_data['typical_range'][0] <= amount <= rule_data['typical_range'][1]:
                rule_confidence += 0.5
            
            if rule_confidence > confidence:
                confidence = rule_confidence
                matched_rule = rule_name
        
        if matched_rule and confidence >= 1.0:  # At least one pattern match
            matches_found += 1
            
            rule_data = matching_rules[matched_rule]
            suggested_desc = rule_data['description_templates'][0]
            
            print(f"   🎯 Match #{matches_found}:")
            print(f"      Source: {source_table}[{source_id}] - ${amount}")
            print(f"      Text: '{search_text[:50]}...'")
            print(f"      Rule: {matched_rule} ({rule_data['category']})")
            print(f"      Suggested: '{suggested_desc}'")
            print(f"      Confidence: {confidence:.1f}")
            
            if not dry_run:
                # Apply the match (update the source record)
                if source_table == 'receipts':
                    cur.execute("""
                        UPDATE receipts 
                        SET category = %s,
                            notes = COALESCE(notes, '') || %s
                        WHERE receipt_id = %s
                    """, (
                        rule_data['category'].lower(),
                        f" [Auto-matched: {matched_rule}]",
                        source_id
                    ))
                elif source_table == 'payments':
                    cur.execute("""
                        UPDATE payments 
                        SET notes = COALESCE(notes, '') || %s
                        WHERE payment_id = %s
                    """, (
                        f" [Charge Category: {rule_data['category']}]",
                        source_id
                    ))
    
    print(f"\n   📊 Matching Results: {matches_found:,} matches found")
    
    if not dry_run and matches_found > 0:
        conn.commit()
        print(f"   [OK] Applied {matches_found:,} charge matches")
    elif dry_run:
        print(f"   📋 DRY RUN: Would apply {matches_found:,} matches")
    
    cur.close()
    conn.close()

def create_charge_lookup_table():
    """Create a standardized charge lookup table for future matching."""
    
    print(f"\n📋 CREATING CHARGE LOOKUP TABLE")
    print("-" * 31)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Create charge lookup table
        cur.execute("""
            DROP TABLE IF EXISTS charge_lookup;
            CREATE TABLE charge_lookup (
                lookup_id SERIAL PRIMARY KEY,
                charge_code VARCHAR(50) NOT NULL UNIQUE,
                charge_name VARCHAR(200) NOT NULL,
                category VARCHAR(100) NOT NULL,
                typical_min_amount DECIMAL(10,2),
                typical_max_amount DECIMAL(10,2),
                search_patterns TEXT[],
                description_templates TEXT[],
                is_taxable BOOLEAN DEFAULT true,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert standard charges
        standard_charges = [
            ('airport_fee', 'Airport Fee', 'Transportation', 10.00, 100.00, 
             ['airport', 'yeg', 'yvr', 'yyc'], ['Airport Fee', 'Airport Surcharge'], True),
            ('beverage_service', 'Beverage Service', 'Beverages', 5.00, 500.00,
             ['beverage', 'drink', 'alcohol'], ['Beverage Order', 'Beverage Charge'], True),
            ('fuel_surcharge', 'Fuel Surcharge', 'Fuel', 5.00, 200.00,
             ['fuel', 'gas', 'surcharge'], ['Fuel Surcharge', 'Distance Surcharge'], True),
            ('gratuity', 'Gratuity', 'Gratuities', 5.00, 1000.00,
             ['tip', 'gratuity'], ['Gratuity', 'Extra Gratuity'], False),
            ('extra_stops', 'Extra Stops', 'Transportation', 10.00, 100.00,
             ['stop', 'pickup', 'additional'], ['Extra Stops', 'Additional Pickup'], True),
            ('wait_time', 'Wait Time', 'Transportation', 15.00, 300.00,
             ['wait', 'delay', 'overtime'], ['Wait / Travel Time', 'Extended Service'], True),
            ('parking_fee', 'Parking Fee', 'Transportation', 5.00, 50.00,
             ['park', 'valet'], ['Parking Fee', 'Valet Service'], True),
            ('cleaning_fee', 'Cleaning Fee', 'Cleaning', 25.00, 500.00,
             ['clean', 'damage', 'broken'], ['Clean Up Fee', 'Damage Fee'], True),
            ('gst_tax', 'GST/HST', 'Taxes', 1.00, 1000.00,
             ['gst', 'hst', 'tax'], ['G.S.T.', 'HST'], False)
        ]
        
        for charge_data in standard_charges:
            cur.execute("""
                INSERT INTO charge_lookup (
                    charge_code, charge_name, category, typical_min_amount, 
                    typical_max_amount, search_patterns, description_templates, is_taxable
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, charge_data)
        
        conn.commit()
        print(f"   [OK] Created charge lookup table with {len(standard_charges)} entries")
        
        # Show the lookup table
        cur.execute("""
            SELECT charge_code, charge_name, category, 
                   typical_min_amount, typical_max_amount
            FROM charge_lookup
            ORDER BY category, charge_name
        """)
        
        lookup_entries = cur.fetchall()
        print(f"\n   📋 Charge Lookup Entries:")
        for code, name, category, min_amt, max_amt in lookup_entries:
            print(f"      • {code}: {name} ({category}) ${min_amt}-${max_amt}")
        
    except Exception as e:
        print(f"   [FAIL] Error creating lookup table: {str(e)}")
        conn.rollback()
    
    cur.close()
    conn.close()

def main():
    """Main charge matching analysis and setup."""
    
    print("🎯 CHARTER CHARGE MATCHING ENGINE")
    print("=" * 34)
    
    # Step 1: Analyze existing patterns
    analyze_charge_patterns()
    
    # Step 2: Create matching rules
    matching_rules = create_charge_matching_rules()
    
    # Step 3: Find and match unmatched charges (dry run)
    match_unmatched_charges(matching_rules, dry_run=True)
    
    # Step 4: Create lookup table for future matching
    create_charge_lookup_table()
    
    print(f"\n[OK] CHARGE MATCHING SYSTEM READY")
    print("-" * 29)
    print("• Analyzed existing charge patterns")
    print("• Created matching rules for 9 charge types") 
    print("• Identified potential matches (dry run)")
    print("• Created standardized lookup table")
    print("\nTo apply matches: Run with --apply flag")
    print("To match specific items: Use the lookup table queries")

if __name__ == "__main__":
    import sys
    
    # Set database environment
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata' 
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    main()