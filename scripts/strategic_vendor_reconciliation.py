#!/usr/bin/env python3
"""
Strategic Vendor Reconciliation System
=====================================

Two-phase approach:
1. PHASE 1: Systematic consolidation of major clutter groups
2. PHASE 2: Intelligent linking of related vendors (Heffner variants, etc.)

Target: Reduce 20,302 vendors to ~500 canonical vendors
"""

import psycopg2
import json
from collections import defaultdict
import re
import sys

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def analyze_vendor_patterns():
    """Categorize vendors into consolidation strategies."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all vendors with their receipt counts
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        WHERE vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY count DESC
    """)
    
    vendors = {}
    for vendor_name, count in cur.fetchall():
        vendors[vendor_name] = count
    
    cur.close()
    conn.close()
    
    # Categorize by pattern
    categories = {
        'pos_transactions': [],  # Point of Sale with transaction IDs
        'etransfers': [],        # E-Transfer with reference numbers
        'charter_refs': [],      # Charter_* entries
        'banking_ops': [],       # Banking operations
        'atm_variants': [],      # ATM/ABM variants
        'service_charges': [],   # Service charges
        'cash_ops': [],          # Cash operations
        'duplicates': [],        # Known duplicates
    }
    
    for vendor, count in vendors.items():
        if 'PURCHASE' in vendor and 'Point of Sale' in vendor:
            categories['pos_transactions'].append((vendor, count))
        elif 'E-TRANSFER' in vendor or 'E TRANSFER' in vendor:
            categories['etransfers'].append((vendor, count))
        elif vendor.startswith('Charter_'):
            categories['charter_refs'].append((vendor, count))
        elif 'ATM' in vendor or 'ABM' in vendor or 'INSTANT TELLER' in vendor:
            categories['atm_variants'].append((vendor, count))
        elif 'SERVICE CHARGE' in vendor or 'NSF' in vendor or 'OVERDRAFT' in vendor:
            categories['service_charges'].append((vendor, count))
        elif 'WITHDRAWAL' in vendor or 'Withdrawal' in vendor:
            categories['cash_ops'].append((vendor, count))
        elif 'Banking' in vendor or 'PREAUTHORIZED' in vendor or 'NETWORK' in vendor:
            categories['banking_ops'].append((vendor, count))
    
    return categories, vendors

def phase_1_consolidation_rules():
    """Define Phase 1 consolidation rules."""
    return {
        'POS_TRANSACTION_CLEANUP': {
            'pattern': r'Point of Sale - Interac.*PURCHASE\d+',
            'replace_with': 'Point of Sale - Interac Purchase',
            'reason': 'POS transaction IDs are noise, not vendor names',
            'expected_consolidation': 6200,
        },
        
        'ETRANSFER_REFERENCE_CLEANUP': {
            'pattern': r'Internet Banking E-TRANSFER \d+',
            'replace_with': 'E-Transfer (Reference on file)',
            'reason': 'Reference numbers prevent vendor grouping',
            'expected_consolidation': 2400,
        },
        
        'CHARTER_REFERENCE_CLEANUP': {
            'pattern': r'Charter_(\d{4}|Reserve_|2015_|2016_|2017_)',
            'replace_with': 'Charter Service (internal reference)',
            'reason': 'Charter IDs are not vendor names',
            'expected_consolidation': 3500,
        },
        
        'ATM_LOCATION_CLEANUP': {
            'pattern': r'(Automated Banking Machine|ABM|ATM).*WITHDRAWAL',
            'replace_with': 'ATM Withdrawal',
            'reason': 'Location details create duplicate variants',
            'expected_consolidation': 1300,
        },
        
        'SERVICE_CHARGE_STANDARDIZATION': {
            'pattern': r'Branch Transaction.*CHARGE',
            'replace_with': 'Bank Service Charges',
            'reason': 'Charge type variants create clutter',
            'expected_consolidation': 600,
        },
    }

def phase_2_linking_rules():
    """Define Phase 2 intelligent linking rules."""
    return {
        'HEFFNER_VARIANTS': {
            'patterns': [
                'HEFFNER AUTO',
                'Heffner Auto',
                'HEFFNER',
                'Heffner Auto Finance',
                'Heffner Auto Finance Corp',
            ],
            'canonical': 'Heffner Auto Finance',
            'reason': 'Equipment financing company',
        },
        
        'INSURANCE_VARIANTS': {
            'patterns': [
                'INSURANCE',
                'Insurance',
                'SGI',
                'AVIVA',
                'insurance company',
            ],
            'canonical': 'Insurance Services',
            'reason': 'Insurance premium payments',
        },
        
        'FUEL_STATIONS': {
            'patterns': [
                'CENTEX',
                'Centex',
                'FAS GAS',
                'Fas Gas',
                'SHELL',
                'Shell',
                'ESSO',
                'Esso',
            ],
            'canonical': 'Fuel Purchase',
            'reason': 'Fleet fuel expenses',
        },
        
        'LIQUOR_STORES': {
            'patterns': [
                'LIQUOR',
                'liquor',
                'PLENTY OF LIQUO',
                'LCBO',
                'Beer Store',
            ],
            'canonical': 'Liquor/Beverage Supplies',
            'reason': 'Hospitality supplies for charter',
        },
    }

def print_phase_1_summary():
    """Print Phase 1 consolidation impact."""
    rules = phase_1_consolidation_rules()
    
    print("\n" + "="*80)
    print("PHASE 1: SYSTEMATIC CONSOLIDATION")
    print("="*80)
    print("\nThese consolidations will:")
    print("  • Remove transaction reference noise")
    print("  • Keep actual vendor names intact")
    print("  • Reduce vendor count from 20,302 → ~14,000")
    print("  • Impact ~14,000 receipts with automatic mapping")
    
    total_expected = 0
    for rule_name, rule_def in rules.items():
        print(f"\n{rule_name}:")
        print(f"  Pattern: {rule_def['pattern']}")
        print(f"  Consolidate to: {rule_def['replace_with']}")
        print(f"  Reason: {rule_def['reason']}")
        print(f"  Expected consolidation: ~{rule_def['expected_consolidation']} receipts")
        total_expected += rule_def['expected_consolidation']
    
    print(f"\nTotal Phase 1 consolidation: ~{total_expected} receipts")
    print("Remaining vendors: ~14,100 (many still having legitimate variants)")

def print_phase_2_summary():
    """Print Phase 2 linking impact."""
    rules = phase_2_linking_rules()
    
    print("\n" + "="*80)
    print("PHASE 2: INTELLIGENT LINKING")
    print("="*80)
    print("\nThese linkages will:")
    print("  • Connect legitimate vendor name variations")
    print("  • Preserve alternative names for reference")
    print("  • Create canonical vendor master list")
    print("  • Reduce remaining vendors from ~14,100 → ~500 canonical")
    
    for link_name, link_def in rules.items():
        patterns = link_def['patterns']
        print(f"\n{link_name}:")
        print(f"  Canonical: {link_def['canonical']}")
        print(f"  Link {len(patterns)} variations: {patterns[:3]} ...")
        print(f"  Reason: {link_def['reason']}")

def run_phase_1_simulation(dry_run=True):
    """Simulate Phase 1 consolidation impact."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    rules = phase_1_consolidation_rules()
    
    print("\n" + "="*80)
    print("PHASE 1 SIMULATION")
    print("="*80)
    
    total_affected = 0
    results = {}
    
    for rule_name, rule_def in rules.items():
        pattern = rule_def['pattern']
        replace_with = rule_def['replace_with']
        
        # Count affected vendors and receipts
        cur.execute("""
            SELECT COUNT(DISTINCT vendor_name) as vendor_count,
                   COUNT(*) as receipt_count
            FROM receipts
            WHERE vendor_name ~ %s
        """, (pattern,))
        
        vendor_count, receipt_count = cur.fetchone()
        results[rule_name] = {
            'vendors': vendor_count,
            'receipts': receipt_count,
            'pattern': pattern,
            'replace_with': replace_with,
        }
        total_affected += receipt_count
        
        print(f"\n{rule_name}:")
        print(f"  Affected vendors: {vendor_count}")
        print(f"  Affected receipts: {receipt_count}")
        print(f"  Would consolidate to: {replace_with}")
    
    cur.close()
    conn.close()
    
    print(f"\nTotal receipts affected by Phase 1: {total_affected}")
    return results

def export_vendor_strategy():
    """Export vendor reconciliation strategy to file."""
    categories, vendors = analyze_vendor_patterns()
    
    strategy = {
        'analysis_date': '2025-12-05',
        'total_unique_vendors': len(vendors),
        'total_receipts': sum(vendors.values()),
        'phase_1': {
            'approach': 'Remove transaction reference noise',
            'rules': phase_1_consolidation_rules(),
            'target_vendors': 14000,
        },
        'phase_2': {
            'approach': 'Link legitimate vendor variations',
            'rules': phase_2_linking_rules(),
            'target_vendors': 500,
        },
        'vendor_categories': {
            k: len(v) for k, v in categories.items()
        }
    }
    
    with open('l:\\limo\\reports\\vendor_reconciliation_strategy.json', 'w') as f:
        json.dump(strategy, f, indent=2)
    
    print(f"\nStrategy exported to: l:\\limo\\reports\\vendor_reconciliation_strategy.json")

if __name__ == '__main__':
    print_phase_1_summary()
    print_phase_2_summary()
    
    results = run_phase_1_simulation(dry_run=True)
    
    export_vendor_strategy()
    
    print("\n" + "="*80)
    print("STRATEGIC RECOMMENDATION")
    print("="*80)
    print("""
This two-phase approach allows for:

1. PHASE 1 (Automated): Remove noise while preserving vendor names
   - 14,000+ receipts automatically consolidated
   - No manual review needed - purely technical cleanup
   - Result: More meaningful vendor grouping

2. PHASE 2 (Validated): Intelligent linking with business logic
   - Links legitimate variations (Heffner variants, fuel stations, etc.)
   - Preserves original names in audit trail
   - Creates canonical vendor master list
   - Result: ~500 canonical vendors for reporting

NEXT STEPS:
1. Review Phase 1 rules for accuracy
2. Gather business approval for canonical names (Phase 2)
3. Create vendor master table with historical mapping
4. Execute consolidation with full audit trail
5. Update GL account mapping to new vendor structure
""")
