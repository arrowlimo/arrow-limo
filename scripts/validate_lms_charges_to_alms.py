#!/usr/bin/env python3
"""
Validate LMS Charge table data against ALMS charters table.

For each charter in LMS, retrieves all charges and compares to ALMS
to ensure charge data was properly migrated.
"""

import pyodbc
import psycopg2
import os
from decimal import Decimal
from collections import defaultdict

# Database connections
LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def connect_lms():
    """Connect to LMS Access database."""
    conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)


def connect_alms():
    """Connect to ALMS PostgreSQL database."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def get_lms_charges(lms_conn):
    """
    Get all charges from LMS grouped by Reserve_No.
    
    Returns: dict of {reserve_no: [list of charge records]}
    """
    cur = lms_conn.cursor()
    
    # First, inspect the Charge table structure
    cur.execute("SELECT TOP 1 * FROM Charge")
    columns = [desc[0] for desc in cur.description]
    print(f"LMS Charge table columns: {', '.join(columns)}\n")
    
    # Get all charges (using actual LMS column names)
    cur.execute("""
        SELECT Reserve_No, Amount, Desc, LastUpdated, Tag
        FROM Charge
        ORDER BY Reserve_No, LastUpdated
    """)
    
    charges_by_reserve = defaultdict(list)
    total_charges = 0
    
    for row in cur.fetchall():
        reserve_no = row[0]
        if reserve_no:  # Skip NULL reserve numbers
            reserve_no = str(reserve_no).zfill(6)  # Pad to 6 digits
            charges_by_reserve[reserve_no].append({
                'amount': Decimal(str(row[1])) if row[1] else Decimal('0'),
                'description': row[2] or '',
                'date': row[3],
                'type': row[4] or ''
            })
            total_charges += 1
    
    print(f"✓ Loaded {total_charges} charges from LMS for {len(charges_by_reserve)} reserves\n")
    return charges_by_reserve


def get_alms_charters(alms_conn):
    """
    Get all charters from ALMS with their charge-related fields.
    
    Returns: dict of {reserve_number: charter record}
    """
    cur = alms_conn.cursor()
    
    # Get charter records with available amount fields
    cur.execute("""
        SELECT 
            reserve_number,
            total_amount_due,
            balance,
            deposit,
            retainer_amount,
            rate
        FROM charters
        WHERE reserve_number IS NOT NULL
        ORDER BY reserve_number
    """)
    
    charters = {}
    for row in cur.fetchall():
        reserve_no = row[0]
        charters[reserve_no] = {
            'total_amount_due': row[1] or Decimal('0'),
            'balance': row[2] or Decimal('0'),
            'deposit': row[3] or Decimal('0'),
            'retainer_amount': row[4] or Decimal('0'),
            'rate': row[5] or Decimal('0')
        }
    
    print(f"✓ Loaded {len(charters)} charters from ALMS\n")
    return charters


def compare_charges(lms_charges, alms_charters):
    """
    Compare LMS charges to ALMS charter amounts.
    
    Returns: dict of issues categorized by type
    """
    issues = {
        'missing_in_alms': [],      # Reserve in LMS but not in ALMS
        'amount_mismatch': [],       # Total doesn't match
        'component_mismatch': [],    # Individual charge components don't match
        'perfect_match': [],         # Everything matches
        'missing_in_lms': []         # Reserve in ALMS but not in LMS
    }
    
    # Check LMS reserves against ALMS
    for reserve_no, lms_charge_list in sorted(lms_charges.items()):
        # Calculate LMS total
        lms_total = sum(charge['amount'] for charge in lms_charge_list)
        
        if reserve_no not in alms_charters:
            issues['missing_in_alms'].append({
                'reserve': reserve_no,
                'lms_total': lms_total,
                'lms_charges': lms_charge_list
            })
            continue
        
        alms_charter = alms_charters[reserve_no]
        alms_total = alms_charter['total_amount_due']
        
        # Compare totals (allow 1 cent rounding difference)
        if abs(lms_total - alms_total) <= Decimal('0.01'):
            issues['perfect_match'].append({
                'reserve': reserve_no,
                'amount': lms_total
            })
        else:
            issues['amount_mismatch'].append({
                'reserve': reserve_no,
                'lms_total': lms_total,
                'alms_total': alms_total,
                'difference': lms_total - alms_total,
                'lms_charges': lms_charge_list,
                'alms_rate': alms_charter['rate'],
                'alms_deposit': alms_charter['deposit']
            })
    
    # Check for reserves in ALMS but not in LMS
    for reserve_no, charter in alms_charters.items():
        if reserve_no not in lms_charges and charter['total_amount_due'] > 0:
            issues['missing_in_lms'].append({
                'reserve': reserve_no,
                'alms_total': charter['total_amount_due']
            })
    
    return issues


def print_report(issues):
    """Print detailed comparison report."""
    print("=" * 80)
    print("LMS CHARGE VALIDATION REPORT")
    print("=" * 80)
    print()
    
    # Summary
    print("SUMMARY:")
    print(f"  ✓ Perfect matches: {len(issues['perfect_match'])}")
    print(f"  ⚠ Amount mismatches: {len(issues['amount_mismatch'])}")
    print(f"  ⚠ Missing in ALMS: {len(issues['missing_in_alms'])}")
    print(f"  ⚠ Missing in LMS: {len(issues['missing_in_lms'])}")
    print()
    
    # Missing in ALMS
    if issues['missing_in_alms']:
        print("=" * 80)
        print("RESERVES IN LMS BUT NOT IN ALMS:")
        print("=" * 80)
        for item in issues['missing_in_alms'][:20]:  # Show first 20
            print(f"\nReserve {item['reserve']}: LMS Total = ${item['lms_total']:.2f}")
            for charge in item['lms_charges']:
                print(f"  - {charge['description']}: ${charge['amount']:.2f} ({charge['type']})")
        if len(issues['missing_in_alms']) > 20:
            print(f"\n... and {len(issues['missing_in_alms']) - 20} more")
        print()
    
    # Amount mismatches
    if issues['amount_mismatch']:
        print("=" * 80)
        print("AMOUNT MISMATCHES (LMS vs ALMS):")
        print("=" * 80)
        for item in issues['amount_mismatch'][:20]:  # Show first 20
            print(f"\nReserve {item['reserve']}:")
            print(f"  LMS Total: ${item['lms_total']:.2f}")
            print(f"  ALMS Total: ${item['alms_total']:.2f}")
            print(f"  Difference: ${item['difference']:.2f}")
            print(f"  ALMS Rate: ${item['alms_rate']:.2f}, Deposit: ${item['alms_deposit']:.2f}")
            print(f"\n  LMS Charges:")
            for charge in item['lms_charges']:
                print(f"    - {charge['description']}: ${charge['amount']:.2f} ({charge['type']})")
        if len(issues['amount_mismatch']) > 20:
            print(f"\n... and {len(issues['amount_mismatch']) - 20} more")
        print()
    
    # Missing in LMS
    if issues['missing_in_lms']:
        print("=" * 80)
        print("RESERVES IN ALMS BUT NOT IN LMS (with amounts > 0):")
        print("=" * 80)
        for item in issues['missing_in_lms'][:20]:
            print(f"  Reserve {item['reserve']}: ALMS Total = ${item['alms_total']:.2f}")
        if len(issues['missing_in_lms']) > 20:
            print(f"... and {len(issues['missing_in_lms']) - 20} more")
        print()
    
    # Action items
    print("=" * 80)
    print("TODO LIST:")
    print("=" * 80)
    
    todo_count = 1
    
    if issues['missing_in_alms']:
        print(f"{todo_count}. Investigate {len(issues['missing_in_alms'])} reserves in LMS but missing in ALMS")
        print(f"   - Check if these are test/cancelled charters")
        print(f"   - Verify import scripts processed all LMS reserves")
        todo_count += 1
        print()
    
    if issues['amount_mismatch']:
        print(f"{todo_count}. Fix {len(issues['amount_mismatch'])} amount mismatches")
        print(f"   - Review charge component mapping from LMS to ALMS")
        print(f"   - Check if GST, gratuity, surcharges calculated correctly")
        print(f"   - Verify discount/cancellation fee logic")
        todo_count += 1
        print()
    
    if issues['missing_in_lms']:
        print(f"{todo_count}. Review {len(issues['missing_in_lms'])} reserves in ALMS but not in LMS")
        print(f"   - These may be manually created in ALMS")
        print(f"   - Verify they are legitimate charters")
        todo_count += 1
        print()
    
    if not issues['missing_in_alms'] and not issues['amount_mismatch'] and not issues['missing_in_lms']:
        print("✓ NO ISSUES FOUND - All charges match!")
    
    print()


def main():
    print("Connecting to databases...\n")
    
    lms_conn = connect_lms()
    alms_conn = connect_alms()
    
    try:
        # Get data
        print("Loading LMS charges...")
        lms_charges = get_lms_charges(lms_conn)
        
        print("Loading ALMS charters...")
        alms_charters = get_alms_charters(alms_conn)
        
        # Compare
        print("Comparing charges...\n")
        issues = compare_charges(lms_charges, alms_charters)
        
        # Report
        print_report(issues)
        
    finally:
        lms_conn.close()
        alms_conn.close()


if __name__ == '__main__':
    main()
