#!/usr/bin/env python3
"""
Compare LMS updates (Oct 2025+) to almsdata to determine if applying changes
would benefit (reduce/correct) balance owing.

For each reserve with LMS updates:
1. Get current almsdata state (charges total, payments total, balance)
2. Get current LMS state (charges total, payments total, balance)
3. Determine if LMS has more accurate/complete data
4. Report which reserves would benefit from selective updates
"""

import os
import json
import csv
import pyodbc
import psycopg2
from datetime import datetime
from decimal import Decimal

# Database connections
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

LMS_PATH = r"L:\limo\backups\lms.mdb"

def get_almsdata_reserve_state(reserve_number):
    """Get current almsdata state for a reserve."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get charter info
    cur.execute("""
        SELECT charter_id, total_amount_due, paid_amount, status, created_at
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_number,))
    charter = cur.fetchone()
    
    if not charter:
        cur.close()
        conn.close()
        return None
    
    charter_id, total_amount_due, paid_amount, status, created_at = charter
    
    # Get actual charges total
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as charges_total, COUNT(*) as charge_count
        FROM charter_charges
        WHERE reserve_number = %s
    """, (reserve_number,))
    charges_total, charge_count = cur.fetchone()
    
    # Get actual payments total
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as payments_total, COUNT(*) as payment_count
        FROM payments
        WHERE reserve_number = %s
    """, (reserve_number,))
    payments_total, payment_count = cur.fetchone()
    
    cur.close()
    conn.close()
    
    # Calculate balance
    balance = float(charges_total or 0) - float(payments_total or 0)
    
    return {
        'charter_id': charter_id,
        'reserve_number': reserve_number,
        'charges_total': float(charges_total or 0),
        'charge_count': charge_count,
        'payments_total': float(payments_total or 0),
        'payment_count': payment_count,
        'balance': balance,
        'charter_total_amount_due': float(total_amount_due or 0),
        'charter_paid_amount': float(paid_amount or 0),
        'status': status,
        'created_at': str(created_at) if created_at else None
    }

def get_lms_reserve_state(reserve_number):
    """Get current LMS state for a reserve."""
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        f'DBQ={LMS_PATH};'
    )
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    # Use introspection like audit script to avoid column name issues
    try:
        # Get charges - use ReserveID field from audit CSV
        cur.execute(f"SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in cur.description] if cur.description else []
        
        # Find the reserve field (could be Reserve_No, ReserveID, etc.)
        reserve_field = None
        amount_field = None
        for col in cols:
            col_lower = col.lower()
            if 'reserve' in col_lower and ('no' in col_lower or 'id' in col_lower):
                reserve_field = col
            if col_lower == 'amount':
                amount_field = col
        
        if not reserve_field or not amount_field:
            # Can't query, return minimal state
            cur.close()
            conn.close()
            return {
                'reserve_number': reserve_number,
                'charges_total': 0,
                'charge_count': 0,
                'payments_total': 0,
                'payment_count': 0,
                'balance': 0,
                'status': None,
                'created_date': None
            }
        
        # Get charges using found field names
        cur.execute(f"SELECT SUM([{amount_field}]), COUNT(*) FROM Charge WHERE [{reserve_field}] = ?", (reserve_number,))
        charge_row = cur.fetchone()
        charges_total = float(charge_row[0] or 0)
        charge_count = charge_row[1] or 0
        
        # Try payments
        try:
            cur.execute(f"SELECT TOP 1 * FROM Payment")
            payment_cols = [d[0] for d in cur.description] if cur.description else []
            
            payment_reserve_field = None
            payment_amount_field = None
            for col in payment_cols:
                col_lower = col.lower()
                if 'reserve' in col_lower and ('no' in col_lower or 'id' in col_lower):
                    payment_reserve_field = col
                if col_lower == 'amount':
                    payment_amount_field = col
            
            if payment_reserve_field and payment_amount_field:
                cur.execute(f"SELECT SUM([{payment_amount_field}]), COUNT(*) FROM Payment WHERE [{payment_reserve_field}] = ?", (reserve_number,))
                payment_row = cur.fetchone()
                payments_total = float(payment_row[0] or 0)
                payment_count = payment_row[1] or 0
            else:
                payments_total = 0
                payment_count = 0
        except:
            payments_total = 0
            payment_count = 0
        
    except Exception as e:
        print(f"Error querying LMS for {reserve_number}: {e}")
        cur.close()
        conn.close()
        return {
            'reserve_number': reserve_number,
            'charges_total': 0,
            'charge_count': 0,
            'payments_total': 0,
            'payment_count': 0,
            'balance': 0,
            'status': None,
            'created_date': None
        }
    
    cur.close()
    conn.close()
    
    # Calculate balance
    calc_balance = charges_total - payments_total
    
    return {
        'reserve_number': reserve_number,
        'charges_total': charges_total,
        'charge_count': charge_count,
        'payments_total': payments_total,
        'payment_count': payment_count,
        'balance': calc_balance,
        'status': None,
        'created_date': None
    }

def analyze_benefit(alms_state, lms_state, reserve_number):
    """Determine if LMS update would benefit balance accuracy."""
    if not alms_state:
        return {
            'reserve_number': reserve_number,
            'benefit': 'MISSING_IN_ALMSDATA',
            'reason': 'Reserve exists in LMS but not in almsdata',
            'lms_charges': lms_state['charges_total'] if lms_state else 0,
            'lms_balance': lms_state['balance'] if lms_state else 0,
            'alms_charges': 0,
            'alms_balance': 0,
            'charge_diff': lms_state['charges_total'] if lms_state else 0,
            'balance_diff': lms_state['balance'] if lms_state else 0
        }
    
    if not lms_state:
        return {
            'reserve_number': reserve_number,
            'benefit': 'MISSING_IN_LMS',
            'reason': 'Reserve exists in almsdata but not in LMS',
            'lms_charges': 0,
            'lms_balance': 0,
            'alms_charges': alms_state['charges_total'],
            'alms_balance': alms_state['balance'],
            'charge_diff': -alms_state['charges_total'],
            'balance_diff': -alms_state['balance']
        }
    
    # Compare charges
    charge_diff = lms_state['charges_total'] - alms_state['charges_total']
    balance_diff = lms_state['balance'] - alms_state['balance']
    
    # Determine benefit
    benefit = 'NO_BENEFIT'
    reason = ''
    
    if abs(charge_diff) < 0.01 and abs(balance_diff) < 0.01:
        benefit = 'ALREADY_SYNCED'
        reason = 'LMS and almsdata already match'
    elif lms_state['charge_count'] > alms_state['charge_count']:
        benefit = 'MISSING_CHARGES'
        reason = f"LMS has {lms_state['charge_count'] - alms_state['charge_count']} more charges"
    elif lms_state['charge_count'] < alms_state['charge_count']:
        benefit = 'EXTRA_CHARGES_IN_ALMS'
        reason = f"almsdata has {alms_state['charge_count'] - lms_state['charge_count']} extra charges"
    elif abs(charge_diff) > 0.01:
        if charge_diff > 0:
            benefit = 'LMS_CHARGES_HIGHER'
            reason = f"LMS charges ${charge_diff:.2f} higher (same count, different amounts)"
        else:
            benefit = 'ALMS_CHARGES_HIGHER'
            reason = f"almsdata charges ${-charge_diff:.2f} higher (same count, different amounts)"
    
    # Check if balance is closer to zero in LMS (likely more accurate)
    if abs(lms_state['balance']) < abs(alms_state['balance']) - 0.01:
        if benefit == 'ALREADY_SYNCED':
            benefit = 'BETTER_BALANCE_IN_LMS'
        reason += f" | LMS balance closer to zero (${lms_state['balance']:.2f} vs ${alms_state['balance']:.2f})"
    
    return {
        'reserve_number': reserve_number,
        'benefit': benefit,
        'reason': reason,
        'lms_charges': lms_state['charges_total'],
        'lms_charge_count': lms_state['charge_count'],
        'lms_payments': lms_state['payments_total'],
        'lms_balance': lms_state['balance'],
        'alms_charges': alms_state['charges_total'],
        'alms_charge_count': alms_state['charge_count'],
        'alms_payments': alms_state['payments_total'],
        'alms_balance': alms_state['balance'],
        'charge_diff': charge_diff,
        'balance_diff': balance_diff,
        'alms_status': alms_state['status'],
        'lms_status': lms_state['status']
    }

def main():
    # Read Oct 2025+ updates
    with open(r'L:\limo\reports\LMS_UPDATES_SINCE_OCT2025_SUMMARY.json', 'r') as f:
        updates_summary = json.load(f)
    
    print(f"Analyzing {updates_summary['reserves_affected']} reserves with updates since Oct 2025...")
    print()
    
    # Get all affected reserve numbers
    affected_reserves = set()
    with open(r'L:\limo\reports\LMS_UPDATES_SINCE_OCT2025.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            affected_reserves.add(row['reserve'])
    
    print(f"Found {len(affected_reserves)} unique reserves")
    print()
    
    # Analyze each reserve
    results = []
    for i, reserve_number in enumerate(sorted(affected_reserves), 1):
        if i % 20 == 0:
            print(f"  Processed {i}/{len(affected_reserves)}...")
        
        alms_state = get_almsdata_reserve_state(reserve_number)
        lms_state = get_lms_reserve_state(reserve_number)
        analysis = analyze_benefit(alms_state, lms_state, reserve_number)
        results.append(analysis)
    
    print(f"  Processed {len(affected_reserves)}/{len(affected_reserves)}")
    print()
    
    # Categorize results
    categories = {}
    for result in results:
        benefit = result['benefit']
        if benefit not in categories:
            categories[benefit] = []
        categories[benefit].append(result)
    
    # Write detailed CSV
    output_csv = r'L:\limo\reports\LMS_UPDATES_BALANCE_COMPARISON.csv'
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'reserve_number', 'benefit', 'reason',
            'lms_charges', 'lms_charge_count', 'lms_payments', 'lms_balance',
            'alms_charges', 'alms_charge_count', 'alms_payments', 'alms_balance',
            'charge_diff', 'balance_diff',
            'alms_status', 'lms_status'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    
    # Write summary JSON
    summary = {
        'analyzed_date': datetime.now().isoformat(),
        'total_reserves': len(affected_reserves),
        'categories': {
            cat: {
                'count': len(items),
                'reserves': [r['reserve_number'] for r in items[:10]],  # First 10
                'total_charge_diff': sum(r['charge_diff'] for r in items),
                'total_balance_diff': sum(r['balance_diff'] for r in items)
            }
            for cat, items in categories.items()
        },
        'recommendations': []
    }
    
    # Generate recommendations
    if 'MISSING_CHARGES' in categories:
        count = len(categories['MISSING_CHARGES'])
        total_diff = sum(r['charge_diff'] for r in categories['MISSING_CHARGES'])
        summary['recommendations'].append({
            'type': 'MISSING_CHARGES',
            'count': count,
            'total_amount': total_diff,
            'action': f'Consider adding {count} reserves with missing charges (total ${total_diff:.2f})'
        })
    
    if 'LMS_CHARGES_HIGHER' in categories:
        count = len(categories['LMS_CHARGES_HIGHER'])
        total_diff = sum(r['charge_diff'] for r in categories['LMS_CHARGES_HIGHER'])
        summary['recommendations'].append({
            'type': 'LMS_CHARGES_HIGHER',
            'count': count,
            'total_amount': total_diff,
            'action': f'Review {count} reserves where LMS has higher charges (total ${total_diff:.2f})'
        })
    
    if 'ALREADY_SYNCED' in categories:
        count = len(categories['ALREADY_SYNCED'])
        summary['recommendations'].append({
            'type': 'ALREADY_SYNCED',
            'count': count,
            'action': f'{count} reserves already match - no action needed'
        })
    
    output_json = r'L:\limo\reports\LMS_UPDATES_BALANCE_COMPARISON_SUMMARY.json'
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("=" * 80)
    print("BALANCE COMPARISON SUMMARY")
    print("=" * 80)
    print()
    
    for category, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        count = len(items)
        total_charge_diff = sum(r['charge_diff'] for r in items)
        total_balance_diff = sum(r['balance_diff'] for r in items)
        
        print(f"{category}: {count} reserves")
        print(f"  Total charge difference: ${total_charge_diff:,.2f}")
        print(f"  Total balance difference: ${total_balance_diff:,.2f}")
        
        if items:
            print(f"  Sample: {items[0]['reserve_number']} - {items[0]['reason']}")
        print()
    
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    for rec in summary['recommendations']:
        print(f"• {rec['action']}")
    
    print()
    print(f"Details: {output_csv}")
    print(f"Summary: {output_json}")

if __name__ == '__main__':
    main()
