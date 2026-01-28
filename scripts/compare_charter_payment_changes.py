#!/usr/bin/env python
"""
Compare charters and payments between lms.mdb and almsdata
to verify expected write-off and gratuity adjustments
"""
import pyodbc
import psycopg2
import json
from datetime import datetime
from decimal import Decimal

def connect_mdb():
    """Connect to MDB backup"""
    mdb_path = r"L:\limo\backups\lms.mdb"
    conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
    return pyodbc.connect(conn_str)

def connect_pg():
    """Connect to PostgreSQL"""
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )
    conn.autocommit = True
    return conn

def extract_mdb_charters():
    """Extract charter and payment data from MDB"""
    conn = connect_mdb()
    cursor = conn.cursor()
    
    data = {}
    
    # Get charter table name (might be Reserve, Order, or Charters)
    tables = [t[2] for t in cursor.tables(tableType='TABLE')]
    charter_table = None
    for t in ['Reserve', 'Order', 'Charters', 'Charter']:
        if t in tables:
            charter_table = t
            break
    
    if not charter_table:
        print("⚠ Charter table not found in MDB")
        return data
    
    print(f"Reading from MDB table: {charter_table}")
    
    # Get all charters
    try:
        cursor.execute(f"SELECT * FROM [{charter_table}]")
        columns = [col[0] for col in cursor.description]
        
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            
            # Find reserve number field
            reserve_num = None
            for field in ['Reserve', 'ReserveNum', 'ReserveNumber', 'reserve_number', 'Key']:
                if field in record and record[field]:
                    reserve_num = str(record[field])
                    break
            
            if not reserve_num:
                continue
            
            data[reserve_num] = {
                'source': 'mdb',
                'raw': record,
                'reserve_number': reserve_num,
                'date': record.get('Date') or record.get('Charter_Date'),
                'charges': Decimal(str(record.get('Charges') or 0)),
                'gratuity': Decimal(str(record.get('Gratuity') or 0)),
                'extra_gratuity': Decimal(str(record.get('Extra_Gratuity') or record.get('ExtraGratuity') or 0)),
                'paid': Decimal(str(record.get('Paid') or record.get('Amt_Paid') or 0)),
                'balance': Decimal(str(record.get('Balance') or 0)),
                'status': record.get('Status') or record.get('Cancelled')
            }
            
    except Exception as e:
        print(f"Error reading MDB charters: {e}")
    
    conn.close()
    return data

def extract_pg_charters():
    """Extract charter data from PostgreSQL"""
    conn = connect_pg()
    cursor = conn.cursor()
    
    data = {}
    
    try:
        cursor.execute("""
            SELECT 
                reserve_number,
                charter_date,
                total_amount_due,
                driver_gratuity,
                paid_amount,
                balance,
                status
            FROM charters
            WHERE reserve_number IS NOT NULL
        """)
        
        for row in cursor.fetchall():
            reserve_num = str(row[0])
            data[reserve_num] = {
                'source': 'pg',
                'reserve_number': reserve_num,
                'date': row[1],
                'charges': Decimal(str(row[2] or 0)),
                'gratuity': Decimal(str(row[3] or 0)),
                'extra_gratuity': Decimal('0'),  # Not tracked separately in almsdata
                'paid': Decimal(str(row[4] or 0)),
                'balance': Decimal(str(row[5] or 0)),
                'status': row[6]
            }
    except Exception as e:
        print(f"Error reading PG charters: {e}")
    
    conn.close()
    return data

def extract_mdb_payments():
    """Extract payment data from MDB"""
    conn = connect_mdb()
    cursor = conn.cursor()
    
    data = {}
    
    # Find payment table
    tables = [t[2] for t in cursor.tables(tableType='TABLE')]
    payment_table = None
    for t in ['Ord_Payment', 'Payment', 'Payments', 'OrderPay']:
        if t in tables:
            payment_table = t
            break
    
    if not payment_table:
        print("⚠ Payment table not found in MDB")
        return data
    
    print(f"Reading from MDB table: {payment_table}")
    
    try:
        cursor.execute(f"SELECT * FROM [{payment_table}]")
        columns = [col[0] for col in cursor.description]
        
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            
            # Find reserve number
            reserve_num = None
            for field in ['Reserve', 'ReserveNum', 'Key', 'OrderNum']:
                if field in record and record[field]:
                    reserve_num = str(record[field])
                    break
            
            if not reserve_num:
                continue
            
            if reserve_num not in data:
                data[reserve_num] = []
            
            data[reserve_num].append({
                'amount': Decimal(str(record.get('Amount') or record.get('Amt') or 0)),
                'date': record.get('Date') or record.get('Payment_Date'),
                'method': record.get('Method') or record.get('PayType'),
                'raw': record
            })
    except Exception as e:
        print(f"Error reading MDB payments: {e}")
    
    conn.close()
    return data

def extract_pg_payments():
    """Extract payment data from PostgreSQL"""
    conn = connect_pg()
    cursor = conn.cursor()
    
    data = {}
    
    try:
        cursor.execute("""
            SELECT 
                reserve_number,
                amount,
                payment_date,
                payment_method,
                created_at
            FROM payments
            WHERE reserve_number IS NOT NULL
        """)
        
        for row in cursor.fetchall():
            reserve_num = str(row[0])
            
            if reserve_num not in data:
                data[reserve_num] = []
            
            data[reserve_num].append({
                'amount': Decimal(str(row[1] or 0)),
                'date': row[2],
                'method': row[3],
                'created_at': row[4]
            })
    except Exception as e:
        print(f"Error reading PG payments: {e}")
    
    conn.close()
    return data

def analyze_differences(mdb_charters, pg_charters, mdb_payments, pg_payments):
    """Analyze differences and categorize them"""
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'mdb_charters': len(mdb_charters),
            'pg_charters': len(pg_charters),
            'common_charters': 0,
            'only_in_mdb': 0,
            'only_in_pg': 0
        },
        'expected_changes': {
            'charges_reduced': [],
            'gratuity_moved': [],
            'balance_written_off': [],
            'pre_2005_adjustments': []
        },
        'unexpected_changes': {
            'missing_payments_in_almsdata': [],
            'extra_payments_in_almsdata': [],
            'charge_increases': [],
            'other_discrepancies': []
        },
        'samples': {
            'charge_reduction_sample': [],
            'gratuity_move_sample': [],
            'writeoff_sample': []
        }
    }
    
    all_reserves = set(list(mdb_charters.keys()) + list(pg_charters.keys()))
    
    for reserve_num in all_reserves:
        mdb = mdb_charters.get(reserve_num)
        pg = pg_charters.get(reserve_num)
        
        if mdb and not pg:
            report['summary']['only_in_mdb'] += 1
            continue
        
        if pg and not mdb:
            report['summary']['only_in_pg'] += 1
            continue
        
        if mdb and pg:
            report['summary']['common_charters'] += 1
            
            # Compare charges
            charge_diff = pg['charges'] - mdb['charges']
            
            # Check for charge reduction (expected)
            if charge_diff < 0:
                report['expected_changes']['charges_reduced'].append({
                    'reserve': reserve_num,
                    'mdb_charges': float(mdb['charges']),
                    'pg_charges': float(pg['charges']),
                    'reduction': float(abs(charge_diff)),
                    'date': str(mdb.get('date'))
                })
                
                if len(report['samples']['charge_reduction_sample']) < 10:
                    report['samples']['charge_reduction_sample'].append(reserve_num)
            
            # Check for charge increase (unexpected)
            elif charge_diff > 0:
                report['unexpected_changes']['charge_increases'].append({
                    'reserve': reserve_num,
                    'mdb_charges': float(mdb['charges']),
                    'pg_charges': float(pg['charges']),
                    'increase': float(charge_diff)
                })
            
            # Check gratuity moved to extra_gratuity
            grat_moved = (mdb['gratuity'] > pg['gratuity']) and (pg['extra_gratuity'] > mdb['extra_gratuity'])
            if grat_moved:
                report['expected_changes']['gratuity_moved'].append({
                    'reserve': reserve_num,
                    'mdb_gratuity': float(mdb['gratuity']),
                    'pg_gratuity': float(pg['gratuity']),
                    'mdb_extra': float(mdb['extra_gratuity']),
                    'pg_extra': float(pg['extra_gratuity']),
                    'amount_moved': float(mdb['gratuity'] - pg['gratuity'])
                })
                
                if len(report['samples']['gratuity_move_sample']) < 10:
                    report['samples']['gratuity_move_sample'].append(reserve_num)
            
            # Check for balance write-offs (balance reduced to near 0)
            if mdb['balance'] > Decimal('10.00') and pg['balance'] < Decimal('1.00'):
                report['expected_changes']['balance_written_off'].append({
                    'reserve': reserve_num,
                    'mdb_balance': float(mdb['balance']),
                    'pg_balance': float(pg['balance']),
                    'written_off': float(mdb['balance'])
                })
                
                if len(report['samples']['writeoff_sample']) < 10:
                    report['samples']['writeoff_sample'].append(reserve_num)
            
            # Check pre-2005 charters
            try:
                if mdb.get('date'):
                    charter_year = mdb['date'].year if hasattr(mdb['date'], 'year') else int(str(mdb['date'])[:4])
                    if charter_year < 2005 and pg['balance'] != Decimal('0'):
                        report['expected_changes']['pre_2005_adjustments'].append({
                            'reserve': reserve_num,
                            'year': charter_year,
                            'balance': float(pg['balance']),
                            'needs_adjustment': True
                        })
            except:
                pass
            
            # Compare payments
            mdb_pmts = mdb_payments.get(reserve_num, [])
            pg_pmts = pg_payments.get(reserve_num, [])
            
            mdb_total = sum(p['amount'] for p in mdb_pmts)
            pg_total = sum(p['amount'] for p in pg_pmts)
            
            payment_diff = pg_total - mdb_total
            
            if payment_diff > Decimal('1.00'):
                # More payments in PG = found revenue
                report['unexpected_changes']['extra_payments_in_almsdata'].append({
                    'reserve': reserve_num,
                    'mdb_payment_total': float(mdb_total),
                    'pg_payment_total': float(pg_total),
                    'extra_revenue': float(payment_diff),
                    'pg_payment_count': len(pg_pmts),
                    'mdb_payment_count': len(mdb_pmts)
                })
            elif payment_diff < Decimal('-1.00'):
                # Fewer payments in PG = missing revenue
                report['unexpected_changes']['missing_payments_in_almsdata'].append({
                    'reserve': reserve_num,
                    'mdb_payment_total': float(mdb_total),
                    'pg_payment_total': float(pg_total),
                    'missing_revenue': float(abs(payment_diff)),
                    'pg_payment_count': len(pg_pmts),
                    'mdb_payment_count': len(mdb_pmts)
                })
    
    return report

if __name__ == '__main__':
    print("="*70)
    print("CHARTER & PAYMENT COMPARISON: lms.mdb vs almsdata")
    print("="*70)
    
    print("\n📊 Extracting MDB data...")
    mdb_charters = extract_mdb_charters()
    mdb_payments = extract_mdb_payments()
    print(f"  ✓ MDB: {len(mdb_charters)} charters, {sum(len(p) for p in mdb_payments.values())} payments")
    
    print("\n📊 Extracting PostgreSQL data...")
    pg_charters = extract_pg_charters()
    pg_payments = extract_pg_payments()
    print(f"  ✓ PostgreSQL: {len(pg_charters)} charters, {sum(len(p) for p in pg_payments.values())} payments")
    
    print("\n🔍 Analyzing differences...")
    report = analyze_differences(mdb_charters, pg_charters, mdb_payments, pg_payments)
    
    # Save full report
    output_file = r"L:\limo\reports\charter_payment_comparison_2025-12-26.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  ✓ Full report saved to {output_file}")
    
    # Print summary
    print("\n" + "="*70)
    print("EXPECTED CHANGES (Write-offs & Adjustments)")
    print("="*70)
    
    print(f"\n✓ Charges Reduced (Aged Unpaid Written Off):")
    print(f"  Count: {len(report['expected_changes']['charges_reduced'])}")
    if report['expected_changes']['charges_reduced']:
        total_reduction = sum(c['reduction'] for c in report['expected_changes']['charges_reduced'])
        print(f"  Total Amount Reduced: ${total_reduction:,.2f}")
        print(f"  Sample reserves: {', '.join(report['samples']['charge_reduction_sample'][:5])}")
    
    print(f"\n✓ Gratuity Moved to Extra Gratuity (Non-Taxed):")
    print(f"  Count: {len(report['expected_changes']['gratuity_moved'])}")
    if report['expected_changes']['gratuity_moved']:
        total_moved = sum(g['amount_moved'] for g in report['expected_changes']['gratuity_moved'])
        print(f"  Total Gratuity Moved: ${total_moved:,.2f}")
        print(f"  Sample reserves: {', '.join(report['samples']['gratuity_move_sample'][:5])}")
    
    print(f"\n✓ Balances Written Off (Uncollectable):")
    print(f"  Count: {len(report['expected_changes']['balance_written_off'])}")
    if report['expected_changes']['balance_written_off']:
        total_writeoff = sum(b['written_off'] for b in report['expected_changes']['balance_written_off'])
        print(f"  Total Written Off: ${total_writeoff:,.2f}")
        print(f"  Sample reserves: {', '.join(report['samples']['writeoff_sample'][:5])}")
    
    print(f"\n⚠ Pre-2005 Charters Still With Balance:")
    print(f"  Count: {len(report['expected_changes']['pre_2005_adjustments'])}")
    if report['expected_changes']['pre_2005_adjustments']:
        for adj in report['expected_changes']['pre_2005_adjustments'][:5]:
            print(f"    - {adj['reserve']} ({adj['year']}): ${adj['balance']:.2f}")
    
    print("\n" + "="*70)
    print("UNEXPECTED CHANGES (Need Review)")
    print("="*70)
    
    print(f"\n⚠ Missing Payments in almsdata (Lost Revenue?):")
    print(f"  Count: {len(report['unexpected_changes']['missing_payments_in_almsdata'])}")
    if report['unexpected_changes']['missing_payments_in_almsdata']:
        total_missing = sum(m['missing_revenue'] for m in report['unexpected_changes']['missing_payments_in_almsdata'])
        print(f"  Total Missing: ${total_missing:,.2f}")
        for missing in report['unexpected_changes']['missing_payments_in_almsdata'][:5]:
            print(f"    - {missing['reserve']}: ${missing['missing_revenue']:.2f}")
    
    print(f"\n✓ Extra Payments in almsdata (Found Revenue!):")
    print(f"  Count: {len(report['unexpected_changes']['extra_payments_in_almsdata'])}")
    if report['unexpected_changes']['extra_payments_in_almsdata']:
        total_extra = sum(e['extra_revenue'] for e in report['unexpected_changes']['extra_payments_in_almsdata'])
        print(f"  Total Extra Revenue: ${total_extra:,.2f}")
        for extra in report['unexpected_changes']['extra_payments_in_almsdata'][:5]:
            print(f"    - {extra['reserve']}: ${extra['extra_revenue']:.2f}")
    
    print(f"\n⚠ Charge Increases (Unexpected!):")
    print(f"  Count: {len(report['unexpected_changes']['charge_increases'])}")
    if report['unexpected_changes']['charge_increases']:
        for increase in report['unexpected_changes']['charge_increases'][:5]:
            print(f"    - {increase['reserve']}: +${increase['increase']:.2f}")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"MDB Charters: {report['summary']['mdb_charters']}")
    print(f"PostgreSQL Charters: {report['summary']['pg_charters']}")
    print(f"Common (in both): {report['summary']['common_charters']}")
    print(f"Only in MDB: {report['summary']['only_in_mdb']}")
    print(f"Only in PostgreSQL: {report['summary']['only_in_pg']}")
    print("="*70)
