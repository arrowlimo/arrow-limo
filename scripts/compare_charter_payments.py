#!/usr/bin/env python
"""
Compare Charters, Payments, and Charges between MDB backup and PostgreSQL
Match by reserve_number - identify what changed
"""
import pyodbc
import psycopg2
import json
from datetime import datetime
from decimal import Decimal

def extract_mdb_data():
    """Extract charters, payments, charges from MDB"""
    mdb_path = r"L:\limo\backups\lms.mdb"
    data = {'charters': {}, 'payments': {}, 'charges': {}}
    
    try:
        conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Extract charters/reserves - using simpler approach
        print("Extracting MDB charters (Reserve table)...")
        cursor.execute("SELECT * FROM [Reserve]")
        
        # Get column names
        columns = [description[0] for description in cursor.description]
        print(f"  Columns: {', '.join(columns[:10])}...")
        
        for row in cursor.fetchall():
            row_dict = {col: val for col, val in zip(columns, row)}
            reserve = row_dict.get('Key')
            if reserve:
                data['charters'][reserve] = {
                    'reserve_number': reserve,
                    'order_number': row_dict.get('Ord_Num'),
                    'customer_id': row_dict.get('Cust_ID'),
                    'charter_date': str(row_dict.get('Ord_Date')) if row_dict.get('Ord_Date') else None,
                    'service_date': str(row_dict.get('Svc_Date')) if row_dict.get('Svc_Date') else None,
                    'driver_id': row_dict.get('Driver'),
                    'gratuity': float(row_dict.get('Gratuity', 0)) if row_dict.get('Gratuity') else 0.0,
                    'extra_gratuity': float(row_dict.get('Extra_Gratuity', 0)) if row_dict.get('Extra_Gratuity') else 0.0,
                    'balance': float(row_dict.get('Balance', 0)) if row_dict.get('Balance') else 0.0,
                    'status': row_dict.get('Status')
                }
        
        print(f"✓ Found {len(data['charters'])} charters in MDB")
        
        # Extract payments
        print("Extracting MDB payments (Ord_Payment table)...")
        cursor.execute("SELECT * FROM [Ord_Payment]")
        columns = [description[0] for description in cursor.description]
        
        for row in cursor.fetchall():
            row_dict = {col: val for col, val in zip(columns, row)}
            reserve = row_dict.get('Key')
            if reserve:
                if reserve not in data['payments']:
                    data['payments'][reserve] = []
                data['payments'][reserve].append({
                    'reserve_number': reserve,
                    'amount': float(row_dict.get('Paid', 0)) if row_dict.get('Paid') else 0.0,
                    'payment_date': str(row_dict.get('Paid_Date')) if row_dict.get('Paid_Date') else None,
                    'payment_method': row_dict.get('Payment_Method'),
                    'notes': row_dict.get('Notes')
                })
        
        print(f"✓ Found {sum(len(v) for v in data['payments'].values())} payments in MDB")
        
        # Extract charges
        print("Extracting MDB charges (Charge table)...")
        cursor.execute("SELECT * FROM [Charge]")
        columns = [description[0] for description in cursor.description]
        
        for row in cursor.fetchall():
            row_dict = {col: val for col, val in zip(columns, row)}
            reserve = row_dict.get('Key')
            if reserve:
                if reserve not in data['charges']:
                    data['charges'][reserve] = []
                data['charges'][reserve].append({
                    'reserve_number': reserve,
                    'charge_type': row_dict.get('Charge_Type'),
                    'amount': float(row_dict.get('Amount', 0)) if row_dict.get('Amount') else 0.0,
                    'gst': float(row_dict.get('GST', 0)) if row_dict.get('GST') else 0.0,
                    'total': float(row_dict.get('Total', 0)) if row_dict.get('Total') else 0.0
                })
        
        print(f"✓ Found {sum(len(v) for v in data['charges'].values())} charges in MDB")
        
        conn.close()
        return data
    except Exception as e:
        print(f"Error reading MDB: {e}")
        import traceback
        traceback.print_exc()
        return data

def extract_pg_data():
    """Extract charters and payments from PostgreSQL"""
    data = {'charters': {}, 'payments': {}, 'charges': {}}
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user="postgres",
            password="***REMOVED***"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Extract charters
        print("Extracting PostgreSQL charters...")
        cursor.execute("""
            SELECT 
                reserve_number,
                charter_id,
                account_number,
                charter_date,
                driver,
                driver_gratuity,
                balance,
                status
            FROM charters
            WHERE reserve_number IS NOT NULL
            ORDER BY reserve_number
        """)
        
        for row in cursor.fetchall():
            reserve = row[0]
            if reserve:
                data['charters'][reserve] = {
                    'reserve_number': row[0],
                    'charter_id': row[1],
                    'account_number': row[2],
                    'charter_date': str(row[3]) if row[3] else None,
                    'driver': row[4],
                    'driver_gratuity': float(row[5]) if row[5] else 0.0,
                    'balance': float(row[6]) if row[6] else 0.0,
                    'status': row[7]
                }
        
        print(f"✓ Found {len(data['charters'])} charters in PostgreSQL")
        
        # Extract payments
        print("Extracting PostgreSQL payments...")
        cursor.execute("""
            SELECT 
                reserve_number,
                payment_id,
                amount,
                payment_date,
                payment_method,
                notes
            FROM payments
            WHERE reserve_number IS NOT NULL
            ORDER BY reserve_number, payment_date
        """)
        
        for row in cursor.fetchall():
            reserve = row[0]
            if reserve:
                if reserve not in data['payments']:
                    data['payments'][reserve] = []
                data['payments'][reserve].append({
                    'reserve_number': row[0],
                    'payment_id': row[1],
                    'amount': float(row[2]) if row[2] else 0.0,
                    'payment_date': str(row[3]) if row[3] else None,
                    'payment_method': row[4],
                    'notes': row[5]
                })
        
        print(f"✓ Found {sum(len(v) for v in data['payments'].values())} payments in PostgreSQL")
        
        # Check if charges table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'charges'
            )
        """)
        
        if cursor.fetchone()[0]:
            print("Extracting PostgreSQL charges...")
            cursor.execute("""
                SELECT 
                    reserve_number,
                    charge_type,
                    amount,
                    gst,
                    total
                FROM charges
                WHERE reserve_number IS NOT NULL
                ORDER BY reserve_number
            """)
            
            for row in cursor.fetchall():
                reserve = row[0]
                if reserve:
                    if reserve not in data['charges']:
                        data['charges'][reserve] = []
                    data['charges'][reserve].append({
                        'reserve_number': row[0],
                        'charge_type': row[1],
                        'amount': float(row[2]) if row[2] else 0.0,
                        'gst': float(row[3]) if row[3] else 0.0,
                        'total': float(row[4]) if row[4] else 0.0
                    })
            
            print(f"✓ Found {sum(len(v) for v in data['charges'].values())} charges in PostgreSQL")
        else:
            print("ℹ No charges table in PostgreSQL")
        
        conn.close()
        return data
    except Exception as e:
        print(f"Error reading PostgreSQL: {e}")
        return data

def compare_data(mdb_data, pg_data):
    """Compare MDB and PostgreSQL data"""
    comparison = {
        'timestamp': datetime.now().isoformat(),
        'charter_summary': {
            'mdb_count': len(mdb_data['charters']),
            'pg_count': len(pg_data['charters']),
            'in_both': 0,
            'only_in_mdb': 0,
            'only_in_pg': 0
        },
        'differences': []
    }
    
    all_reserves = set(list(mdb_data['charters'].keys()) + list(pg_data['charters'].keys()))
    
    for reserve in sorted(all_reserves):
        mdb_charter = mdb_data['charters'].get(reserve)
        pg_charter = pg_data['charters'].get(reserve)
        
        if mdb_charter and pg_charter:
            comparison['charter_summary']['in_both'] += 1
            
            # Check for differences
            changes = {}
            
            # Compare critical fields
            if mdb_charter['gratuity'] != pg_charter['driver_gratuity']:
                changes['gratuity'] = {
                    'mdb': mdb_charter['gratuity'],
                    'pg': pg_charter['driver_gratuity'],
                    'diff': mdb_charter['gratuity'] - pg_charter['driver_gratuity']
                }
            
            if mdb_charter.get('extra_gratuity', 0) != 0:
                changes['extra_gratuity_added'] = {
                    'mdb': mdb_charter.get('extra_gratuity', 0),
                    'note': 'Extra gratuity separated from regular gratuity (non-taxed)'
                }
            
            if mdb_charter['balance'] != pg_charter['balance']:
                changes['balance_owing'] = {
                    'mdb': mdb_charter['balance'],
                    'pg': pg_charter['balance'],
                    'diff': mdb_charter['balance'] - pg_charter['balance'],
                    'note': 'Aged unpaid charges and bad debt reduced from balance'
                }
            
            # Compare payments
            mdb_total_paid = sum(p['amount'] for p in mdb_data['payments'].get(reserve, []))
            pg_total_paid = sum(p['amount'] for p in pg_data['payments'].get(reserve, []))
            
            if mdb_total_paid != pg_total_paid:
                changes['total_payments'] = {
                    'mdb': mdb_total_paid,
                    'pg': pg_total_paid,
                    'diff': mdb_total_paid - pg_total_paid,
                    'mdb_payment_count': len(mdb_data['payments'].get(reserve, [])),
                    'pg_payment_count': len(pg_data['payments'].get(reserve, []))
                }
            
            # Compare charges
            mdb_total_charges = sum(c['total'] for c in mdb_data['charges'].get(reserve, []))
            pg_total_charges = sum(c['total'] for c in pg_data['charges'].get(reserve, []))
            
            if mdb_total_charges != pg_total_charges:
                changes['total_charges'] = {
                    'mdb': mdb_total_charges,
                    'pg': pg_total_charges,
                    'diff': mdb_total_charges - pg_total_charges,
                    'mdb_charge_count': len(mdb_data['charges'].get(reserve, [])),
                    'pg_charge_count': len(pg_data['charges'].get(reserve, []))
                }
            
            if changes:
                comparison['differences'].append({
                    'reserve_number': reserve,
                    'charter_date': mdb_charter['charter_date'],
                    'changes': changes
                })
        
        elif mdb_charter and not pg_charter:
            comparison['charter_summary']['only_in_mdb'] += 1
        elif pg_charter and not mdb_charter:
            comparison['charter_summary']['only_in_pg'] += 1
    
    return comparison

if __name__ == '__main__':
    print("="*70)
    print("COMPARING CHARTERS, PAYMENTS, CHARGES")
    print("MDB Backup (lms.mdb) vs PostgreSQL (almsdata)")
    print("="*70)
    print()
    
    print("EXTRACTING DATA FROM MDB...")
    mdb_data = extract_mdb_data()
    print()
    
    print("EXTRACTING DATA FROM POSTGRESQL...")
    pg_data = extract_pg_data()
    print()
    
    print("COMPARING DATA...")
    comparison = compare_data(mdb_data, pg_data)
    
    # Save detailed report
    output_file = r"L:\limo\reports\charter_payment_comparison_detailed.json"
    with open(output_file, 'w') as f:
        json.dump({
            'comparison': comparison,
            'mdb_data_sample': {k: list(v.items())[:3] for k, v in mdb_data.items()},
            'pg_data_sample': {k: list(v.items())[:3] for k, v in pg_data.items()}
        }, f, indent=2, default=str)
    
    print(f"✓ Detailed report saved to {output_file}")
    print()
    
    # Print summary
    print("="*70)
    print("COMPARISON SUMMARY")
    print("="*70)
    summary = comparison['charter_summary']
    print(f"MDB Charters:       {summary['mdb_count']}")
    print(f"PostgreSQL Charters: {summary['pg_count']}")
    print(f"In Both:            {summary['in_both']}")
    print(f"Only in MDB:        {summary['only_in_mdb']}")
    print(f"Only in PostgreSQL: {summary['only_in_pg']}")
    print()
    
    print(f"CHARTERS WITH DIFFERENCES: {len(comparison['differences'])}")
    print()
    
    # Show detailed changes
    if comparison['differences']:
        print("DETAILED CHANGES (by reserve number and date):")
        print("-"*70)
        
        changes_by_type = {}
        for diff in comparison['differences']:
            for field, values in diff['changes'].items():
                if field not in changes_by_type:
                    changes_by_type[field] = []
                changes_by_type[field].append({
                    'reserve': diff['reserve_number'],
                    'date': diff['charter_date'],
                    'change': values
                })
        
        for field in ['gratuity', 'extra_gratuity', 'balance', 'total_payments', 'total_charges']:
            if field in changes_by_type:
                print(f"\n{field.upper()} CHANGES ({len(changes_by_type[field])} charters):")
                
                total_diff = sum(abs(c['change'].get('diff', 0)) for c in changes_by_type[field])
                print(f"  Total difference: ${total_diff:.2f}")
                
                # Show first 5
                for i, item in enumerate(changes_by_type[field][:5]):
                    mdb_val = item['change'].get('mdb', 'N/A')
                    pg_val = item['change'].get('pg', 'N/A')
                    diff = item['change'].get('diff', 0)
                    
                    if isinstance(mdb_val, (int, float)):
                        print(f"  {item['reserve']:12} ({item['date']:10}): MDB=${mdb_val:10.2f} → PG=${pg_val:10.2f} (Δ${diff:10.2f})")
                    else:
                        print(f"  {item['reserve']:12} ({item['date']:10}): MDB={mdb_val} → PG={pg_val}")
                
                if len(changes_by_type[field]) > 5:
                    print(f"  ... and {len(changes_by_type[field]) - 5} more")
    
    print("\n" + "="*70)
    print("✓ Full comparison saved - review reports/charter_payment_comparison_detailed.json")
