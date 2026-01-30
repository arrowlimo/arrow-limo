#!/usr/bin/env python3
"""
Direct banking etransfer name extraction - use banking description names as-is.
Creates mapping of banking names to proper employee identification.

Outputs:
- exports/driver_audit/etransfer_names_direct.csv (etransfer names from banking with totals)
- exports/driver_audit/name_classification_map.csv (canonical mapping for corrections)
"""

import psycopg2
import csv
import re
from pathlib import Path
from collections import defaultdict

DB = dict(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
EXPORT_DIR = Path(__file__).parent.parent / 'exports' / 'driver_audit'

# Canonical name mappings based on your corrections
CANONICAL_NAMES = {
    # Banking name -> (Canonical Name, Role, Classification)
    'mike richard': ('Michael Richard', 'Driver', 'PAY'),
    'michael richard': ('Michael Richard', 'Driver', 'PAY'),
    
    'paul richard': ('Paul D Richard', 'Owner', 'DEFERRED_WAGES'),
    'paul d richard': ('Paul D Richard', 'Owner', 'DEFERRED_WAGES'),
    
    'paul mansell': ('Paul Mansell', 'Driver', 'PAY'),  # Different person from Paul Richard
    
    'matt kapustinsky': ('Matt Kapustinsky', 'Driver', 'PAY'),  # Different person from Matthew Richard
    
    'matthew donat richard': ('Matthew Donat Richard', 'Owner', 'BUSINESS_EXPENSE'),
    'matthew donat': ('Matthew Donat Richard', 'Owner', 'BUSINESS_EXPENSE'),
    'matthew richard': ('Matthew Donat Richard', 'Owner', 'BUSINESS_EXPENSE'),
    
    'david richard': ('David W Richard', 'Loan Provider', 'LOAN'),
    'david w richard': ('David W Richard', 'Loan Provider', 'LOAN'),
    
    'richard gursky': ('Richard Gursky', 'Driver', 'PAY'),
    'gursky': ('Richard Gursky', 'Driver', 'PAY'),
}


def connect():
    return psycopg2.connect(**DB)


def extract_name_from_description(description):
    """Extract person name from banking description."""
    desc_lower = description.lower().strip()
    
    # E-TRANSFER pattern: "Internet Banking E-TRANSFER105256396624 Matthew Donat Richard 4506**********534"
    match = re.search(r'e-?transfer\d*\s+([a-z\s]+?)\s+\d{4}', desc_lower)
    if match:
        return match.group(1).strip()
    
    # Check for known names in description
    for banking_name in CANONICAL_NAMES.keys():
        if banking_name in desc_lower:
            return banking_name
    
    return None


def audit_direct_etransfer_names():
    """Extract etransfer names directly from banking descriptions."""
    conn = connect()
    cur = conn.cursor()
    
    # Get all banking transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date >= DATE '2014-01-01'
          AND (debit_amount > 0 OR credit_amount > 0)
          AND LOWER(description) LIKE '%transfer%'
        ORDER BY transaction_date
    """)
    transactions = cur.fetchall()
    
    print(f"Processing {len(transactions):,} transfer transactions (2014+)")
    
    # Extract names and aggregate
    name_stats = defaultdict(lambda: {'count': 0, 'total_amount': 0.0, 'transactions': []})
    
    for txn_id, txn_date, description, debit, credit in transactions:
        amount = -(debit or 0) if debit else (credit or 0)
        
        extracted_name = extract_name_from_description(description)
        if extracted_name:
            name_stats[extracted_name]['count'] += 1
            name_stats[extracted_name]['total_amount'] += float(amount)
            name_stats[extracted_name]['transactions'].append({
                'transaction_id': txn_id,
                'date': txn_date,
                'amount': amount,
                'description': description
            })
    
    print(f"Found {len(name_stats)} unique names in etransfer descriptions")
    
    # Map to canonical names and classify
    results = []
    for banking_name, stats in name_stats.items():
        canonical_info = CANONICAL_NAMES.get(banking_name)
        if canonical_info:
            canonical_name, role, classification = canonical_info
        else:
            canonical_name = banking_name.title()
            role = 'Unknown'
            classification = 'UNKNOWN'
        
        results.append({
            'banking_name': banking_name,
            'canonical_name': canonical_name,
            'role': role,
            'classification': classification,
            'transaction_count': stats['count'],
            'total_amount': stats['total_amount'],
        })
    
    # Sort by transaction count
    results.sort(key=lambda x: x['transaction_count'], reverse=True)
    
    # Write results
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(EXPORT_DIR / 'etransfer_names_direct.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=[
            'banking_name', 'canonical_name', 'role', 'classification',
            'transaction_count', 'total_amount'
        ])
        w.writeheader()
        w.writerows(results)
    
    # Write name classification map
    map_rows = []
    for banking_name, (canonical, role, classification) in CANONICAL_NAMES.items():
        map_rows.append({
            'banking_name': banking_name,
            'canonical_name': canonical,
            'role': role,
            'classification': classification,
            'note': ''
        })
    
    with open(EXPORT_DIR / 'name_classification_map.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['banking_name', 'canonical_name', 'role', 'classification', 'note'])
        w.writeheader()
        w.writerows(sorted(map_rows, key=lambda x: x['canonical_name']))
    
    # Print summary
    print("\n" + "="*80)
    print("ETRANSFER NAME SUMMARY (by Banking Description)")
    print("="*80)
    print(f"{'Banking Name':<30} {'Canonical Name':<30} {'Role':<15} {'Count':>8} {'Total':>15}")
    print("-"*105)
    
    for row in results[:50]:  # Top 50
        print(f"{row['banking_name']:<30} {row['canonical_name']:<30} {row['role']:<15} "
              f"{row['transaction_count']:>8,} ${row['total_amount']:>14,.2f}")
    
    print(f"\n[OK] CSV outputs written to: {EXPORT_DIR}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    audit_direct_etransfer_names()
