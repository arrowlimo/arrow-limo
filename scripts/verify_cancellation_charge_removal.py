#!/usr/bin/env python3
"""
Verify if the "missing charges" in almsdata are actually correct removals for cancelled/closed charters.

For each reserve with missing charges:
1. Check if adding LMS charges would make almsdata balance = 0 (cancelled correctly)
2. Check if current almsdata balance = -(payment total) (charges removed, payments remain)
3. Categorize: properly cancelled vs truly missing charges
"""

import os
import csv
import psycopg2
from decimal import Decimal

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def analyze_reserve_cancellation(reserve_number, lms_charges, lms_balance, alms_charges, alms_balance, alms_payments, alms_status):
    """
    Determine if missing charges are due to proper cancellation.
    
    Patterns:
    1. PROPERLY_CANCELLED: alms_charges = 0, alms_balance = -payments (charges removed)
    2. PARTIAL_CANCELLATION: some charges remain but not all
    3. TRULY_MISSING: charges should exist but don't
    """
    
    # If almsdata has 0 charges and negative balance = payments, charges were removed
    if alms_charges == 0 and alms_payments > 0:
        if abs(alms_balance + alms_payments) < 0.01:  # balance = -payments
            return {
                'category': 'PROPERLY_CANCELLED',
                'reason': f'Charges removed, payments retained (balance = -${alms_payments:.2f})',
                'action': 'No import needed - correctly cancelled',
                'lms_shows_balance': lms_balance,
                'adding_charges_would_balance': abs(lms_balance) < 1.0  # LMS balanced or near-zero
            }
    
    # If LMS balance is 0 or very small, and almsdata has negative balance
    if abs(lms_balance) < 1.0 and alms_balance < -1.0:
        # LMS is balanced (charges = payments), almsdata is unbalanced (missing charges)
        # Adding LMS charges would bring almsdata to balance
        return {
            'category': 'MISSING_CHARGES_CONFIRMED',
            'reason': f'LMS balanced (${lms_balance:.2f}), almsdata unbalanced (${alms_balance:.2f})',
            'action': 'Import charges to balance',
            'lms_shows_balance': lms_balance,
            'adding_charges_would_balance': True
        }
    
    # If both have charges but different amounts
    if alms_charges > 0 and lms_charges > alms_charges:
        return {
            'category': 'PARTIAL_CHARGES',
            'reason': f'Some charges exist ({alms_charges:.2f}) but LMS has more ({lms_charges:.2f})',
            'action': 'Review - may need additional charges',
            'lms_shows_balance': lms_balance,
            'adding_charges_would_balance': abs(lms_balance) < abs(alms_balance)
        }
    
    # Status-based categorization
    if alms_status and 'cancel' in alms_status.lower():
        return {
            'category': 'CANCELLED_STATUS',
            'reason': f'Status is {alms_status}, charges may be intentionally removed',
            'action': 'Review manually - cancelled booking',
            'lms_shows_balance': lms_balance,
            'adding_charges_would_balance': abs(lms_balance) < abs(alms_balance)
        }
    
    return {
        'category': 'UNCLEAR',
        'reason': 'Pattern unclear - manual review needed',
        'action': 'Manual review',
        'lms_shows_balance': lms_balance,
        'adding_charges_would_balance': abs(lms_balance) < abs(alms_balance)
    }

def main():
    # Read comparison results
    comparison_file = r'L:\limo\reports\LMS_UPDATES_BALANCE_COMPARISON.csv'
    
    print("Analyzing missing charge patterns...")
    print()
    
    results = []
    categories = {}
    
    with open(comparison_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['benefit'] != 'MISSING_CHARGES':
                continue
            
            reserve_number = row['reserve_number']
            lms_charges = float(row['lms_charges'])
            lms_balance = float(row['lms_balance'])
            alms_charges = float(row['alms_charges'])
            alms_balance = float(row['alms_balance'])
            alms_payments = float(row['alms_payments'])
            alms_status = row['alms_status']
            
            analysis = analyze_reserve_cancellation(
                reserve_number, lms_charges, lms_balance, 
                alms_charges, alms_balance, alms_payments, alms_status
            )
            
            result = {
                'reserve_number': reserve_number,
                'category': analysis['category'],
                'reason': analysis['reason'],
                'action': analysis['action'],
                'alms_status': alms_status,
                'alms_charges': alms_charges,
                'alms_payments': alms_payments,
                'alms_balance': alms_balance,
                'lms_charges': lms_charges,
                'lms_balance': lms_balance,
                'charge_diff': lms_charges - alms_charges,
                'would_balance_if_imported': analysis['adding_charges_would_balance']
            }
            
            results.append(result)
            
            # Categorize
            cat = analysis['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)
    
    # Write detailed CSV
    output_csv = r'L:\limo\reports\CANCELLATION_VERIFICATION.csv'
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'reserve_number', 'category', 'reason', 'action', 'alms_status',
            'alms_charges', 'alms_payments', 'alms_balance',
            'lms_charges', 'lms_balance', 'charge_diff', 'would_balance_if_imported'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    
    # Print summary
    print("=" * 80)
    print("CANCELLATION VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    
    for category, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        count = len(items)
        total_charge_diff = sum(r['charge_diff'] for r in items)
        would_balance_count = sum(1 for r in items if r['would_balance_if_imported'])
        
        print(f"{category}: {count} reserves")
        print(f"  Total charges that would be added: ${total_charge_diff:,.2f}")
        print(f"  Would balance if imported: {would_balance_count}/{count}")
        
        if items:
            print(f"  Sample: {items[0]['reserve_number']}")
            print(f"    Status: {items[0]['alms_status']}")
            print(f"    Alms: ${items[0]['alms_charges']:.2f} charges, ${items[0]['alms_payments']:.2f} payments, ${items[0]['alms_balance']:.2f} balance")
            print(f"    LMS:  ${items[0]['lms_charges']:.2f} charges, ${items[0]['lms_balance']:.2f} balance")
            print(f"    Reason: {items[0]['reason']}")
        print()
    
    # Generate recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    if 'PROPERLY_CANCELLED' in categories:
        count = len(categories['PROPERLY_CANCELLED'])
        print(f"✓ {count} reserves properly cancelled - charges correctly removed")
        print(f"  → No action needed")
        print()
    
    if 'MISSING_CHARGES_CONFIRMED' in categories:
        count = len(categories['MISSING_CHARGES_CONFIRMED'])
        total = sum(r['charge_diff'] for r in categories['MISSING_CHARGES_CONFIRMED'])
        print(f"⚠ {count} reserves with truly missing charges")
        print(f"  → Import ${total:,.2f} in charges to balance these reserves")
        print()
    
    if 'CANCELLED_STATUS' in categories:
        count = len(categories['CANCELLED_STATUS'])
        print(f"? {count} reserves marked cancelled but pattern unclear")
        print(f"  → Manual review recommended")
        print()
    
    print(f"Details: {output_csv}")

if __name__ == '__main__':
    main()
