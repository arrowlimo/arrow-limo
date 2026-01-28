#!/usr/bin/env python3
"""
Comprehensive audit of banking transactions vs employee names to identify:
1. E-transfers/payments that match employee names (for pay vs expense classification)
2. Drivers with name variants (Mike=Michael, etc.)
3. Special cases: David Richard = loan, Matthew Donat Richard = business expenses
4. Distinguish: pay, float, reimbursement, loan, business expense

Outputs:
- exports/driver_audit/banking_employee_matches.csv (all matches with classification)
- exports/driver_audit/employee_name_variants.csv (name mapping table)
- exports/driver_audit/etransfer_classification_summary.csv (by employee and type)
"""

import psycopg2
import csv
from pathlib import Path
from collections import defaultdict
import re

DB = dict(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
EXPORT_DIR = Path(__file__).parent.parent / 'exports' / 'driver_audit'


def connect():
    return psycopg2.connect(**DB)


# Known name variants and special cases
# Use banking etransfer names as canonical (how they appear in banking descriptions)
NAME_VARIANTS = {
    'mike richard': ['michael richard'],  # Driver - banking uses "Mike"
    'matthew donat richard': ['matthew donat', 'matthew richard'],  # Owner - business expenses
    'richard gursky': ['gursky', 'richard g'],  # Driver
    'paul richard': ['paul d richard'],  # Owner - appears as "Paul Richard" in banking
    'paul mansell': [],  # Driver - separate person from Paul Richard
    'matt kapustinsky': [],  # Driver - separate person from Matthew Richard
    'david richard': ['david w richard'],  # Loan provider
}

SPECIAL_CLASSIFICATIONS = {
    # David Richard = loan transactions only
    'david richard': 'LOAN',
    'david w richard': 'LOAN',
    'david': 'LOAN',  # Default David references to loan unless proven otherwise
    
    # Matthew Donat Richard = business expenses (fuel, alcohol for vehicles)
    'matthew donat richard': 'BUSINESS_EXPENSE',
    'matthew donat': 'BUSINESS_EXPENSE',
    'matthew richard': 'BUSINESS_EXPENSE',
    
    # Paul Richard (owner) = deferred wages
    'paul richard': 'DEFERRED_WAGES',
    'paul d richard': 'DEFERRED_WAGES',
    
    # Drivers (actual pay) - no special classification, use etransfer default
    'mike richard': None,  # Driver - normal pay
    'michael richard': None,  # Driver - normal pay
    'paul mansell': None,  # Driver - normal pay (NOT Paul Richard)
    'matt kapustinsky': None,  # Driver - normal pay (NOT Matthew Richard)
    'richard gursky': None,  # Driver - normal pay
}


def normalize_name(name):
    """Lowercase, strip, collapse whitespace."""
    return ' '.join(name.lower().strip().split())


def load_employees(cur):
    """Load all employees with name normalization."""
    cur.execute("""
        SELECT employee_id, employee_number, 
               COALESCE(full_name, first_name || ' ' || last_name) AS name,
               first_name, last_name
        FROM employees
    """)
    employees = []
    for row in cur.fetchall():
        emp_id, emp_no, name, first, last = row
        if name:
            employees.append({
                'employee_id': emp_id,
                'employee_number': emp_no,
                'full_name': name,
                'first_name': first,
                'last_name': last,
                'normalized_name': normalize_name(name),
                'normalized_first': normalize_name(first or ''),
                'normalized_last': normalize_name(last or ''),
            })
    return employees


def classify_transaction_type(description, amount):
    """
    Classify banking transaction based on description keywords.
    Returns: (type, confidence)
    Types: PAY, FLOAT, REIMBURSEMENT, LOAN_PAYMENT, LOAN_RECEIPT, BUSINESS_EXPENSE, FUEL, ALCOHOL, UNKNOWN
    """
    desc_lower = description.lower()
    
    # Explicit keywords
    if 'e-transfer' in desc_lower or 'etransfer' in desc_lower:
        if 'float' in desc_lower:
            return 'FLOAT', 'HIGH'
        if 'reimb' in desc_lower or 'expense' in desc_lower:
            return 'REIMBURSEMENT', 'HIGH'
        if 'pay' in desc_lower or 'wage' in desc_lower or 'salary' in desc_lower:
            return 'PAY', 'MEDIUM'
        # Default etransfer classification
        return 'ETRANSFER', 'MEDIUM'
    
    if 'loan' in desc_lower:
        if amount < 0:  # Debit = payment to someone
            return 'LOAN_PAYMENT', 'HIGH'
        else:  # Credit = receiving loan
            return 'LOAN_RECEIPT', 'HIGH'
    
    if 'fuel' in desc_lower or 'gas' in desc_lower or 'petro' in desc_lower or 'shell' in desc_lower:
        return 'FUEL', 'HIGH'
    
    if 'alcohol' in desc_lower or 'liquor' in desc_lower or 'wine' in desc_lower or 'beer' in desc_lower:
        return 'ALCOHOL', 'HIGH'
    
    if 'reimb' in desc_lower or 'reimbursement' in desc_lower:
        return 'REIMBURSEMENT', 'HIGH'
    
    if 'float' in desc_lower:
        return 'FLOAT', 'HIGH'
    
    # Generic payment indicators
    if 'pay' in desc_lower or 'wage' in desc_lower:
        return 'PAY', 'LOW'
    
    return 'UNKNOWN', 'LOW'


def match_employee_to_transaction(description, employees):
    """
    Match banking transaction description to employee(s).
    Returns: [(employee, match_type, match_confidence), ...]
    """
    desc_norm = normalize_name(description)
    matches = []
    
    for emp in employees:
        # Full name match
        if emp['normalized_name'] in desc_norm:
            matches.append((emp, 'FULL_NAME', 'HIGH'))
            continue
        
        # First + Last match
        if emp['normalized_first'] and emp['normalized_last']:
            if emp['normalized_first'] in desc_norm and emp['normalized_last'] in desc_norm:
                matches.append((emp, 'FIRST_LAST', 'HIGH'))
                continue
        
        # Last name only (less confident)
        if emp['normalized_last'] and len(emp['normalized_last']) > 3:
            if emp['normalized_last'] in desc_norm:
                matches.append((emp, 'LAST_NAME', 'MEDIUM'))
    
    # Check name variants
    for canonical, variants in NAME_VARIANTS.items():
        for variant in variants:
            if normalize_name(variant) in desc_norm:
                # Find employee matching canonical name
                for emp in employees:
                    if normalize_name(canonical) in emp['normalized_name']:
                        matches.append((emp, 'NAME_VARIANT', 'HIGH'))
                        break
    
    return matches


def apply_special_classification(description, base_type):
    """Override classification for special cases."""
    desc_norm = normalize_name(description)
    
    for name_pattern, special_type in SPECIAL_CLASSIFICATIONS.items():
        if special_type is None:  # Skip drivers with no special classification
            continue
        if normalize_name(name_pattern) in desc_norm:
            return special_type
    
    return base_type


def audit_banking_employee_matches():
    """Main audit function."""
    conn = connect()
    cur = conn.cursor()
    
    employees = load_employees(cur)
    print(f"Loaded {len(employees)} employees")
    
    # Get banking transactions (debits = outgoing = potential pay/expense)
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date >= DATE '2014-01-01'
          AND (debit_amount > 0 OR credit_amount > 0)
        ORDER BY transaction_date
    """)
    transactions = cur.fetchall()
    print(f"Loaded {len(transactions)} banking transactions (2014+)")
    
    results = []
    stats = defaultdict(lambda: defaultdict(int))
    
    for txn_id, txn_date, description, debit, credit in transactions:
        amount = -(debit or 0) if debit else (credit or 0)
        
        # Classify transaction type
        base_type, type_confidence = classify_transaction_type(description, amount)
        
        # Match to employees
        emp_matches = match_employee_to_transaction(description, employees)
        
        if emp_matches:
            for emp, match_type, match_confidence in emp_matches:
                # Apply special classification overrides
                final_type = apply_special_classification(description, base_type)
                
                results.append({
                    'transaction_id': txn_id,
                    'transaction_date': txn_date,
                    'description': description,
                    'amount': amount,
                    'employee_id': emp['employee_id'],
                    'employee_name': emp['full_name'],
                    'match_type': match_type,
                    'match_confidence': match_confidence,
                    'classification': final_type,
                    'type_confidence': type_confidence,
                })
                
                # Stats
                stats[emp['full_name']][final_type] += 1
    
    print(f"Found {len(results)} banking-employee matches")
    
    # Write results
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(EXPORT_DIR / 'banking_employee_matches.csv', 'w', newline='', encoding='utf-8') as f:
        if results:
            w = csv.DictWriter(f, fieldnames=results[0].keys())
            w.writeheader()
            w.writerows(results)
    
    # Write summary by employee and type
    summary = []
    for emp_name, types in stats.items():
        for type_name, count in types.items():
            summary.append({
                'employee_name': emp_name,
                'classification': type_name,
                'transaction_count': count
            })
    
    with open(EXPORT_DIR / 'etransfer_classification_summary.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['employee_name', 'classification', 'transaction_count'])
        w.writeheader()
        w.writerows(sorted(summary, key=lambda x: (x['employee_name'], x['classification'])))
    
    # Write name variants mapping
    variants_output = []
    for canonical, variants in NAME_VARIANTS.items():
        for variant in variants:
            variants_output.append({
                'canonical_name': canonical,
                'variant': variant,
                'note': SPECIAL_CLASSIFICATIONS.get(canonical, '')
            })
    
    with open(EXPORT_DIR / 'employee_name_variants.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['canonical_name', 'variant', 'note'])
        w.writeheader()
        w.writerows(variants_output)
    
    # Print summary
    print("\nEmployee-Banking Match Summary:")
    print(f"{'Employee':<40} {'Type':<20} {'Count':>10}")
    print("-" * 72)
    for emp_name in sorted(stats.keys()):
        for type_name, count in sorted(stats[emp_name].items()):
            print(f"{emp_name:<40} {type_name:<20} {count:>10}")
    
    print(f"\nCSV outputs written to: {EXPORT_DIR}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    audit_banking_employee_matches()
