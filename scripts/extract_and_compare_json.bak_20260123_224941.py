#!/usr/bin/env python
"""
Extract charter/payment/charge data directly from MDB file using pyodbc.
Compare key fields that would have changed during reconciliation.
"""
import pyodbc
import psycopg2
import json
import os
from datetime import datetime
from collections import defaultdict

MDB_FILE = r"L:\limo\backups\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def get_mdb_connection():
    """Connect to Access database"""
    try:
        conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_FILE};'
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"Error connecting to MDB: {e}")
        return None

def get_pg_connection():
    """Connect to PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def extract_mdb_reserves():
    """Extract Reserve table from MDB"""
    conn = get_mdb_connection()
    if not conn:
        return {}
    
    print("Connecting to MDB Reserve table...")
    try:
        cursor = conn.cursor()
        
        # Get all columns from Reserve
        cursor.execute("SELECT * FROM Reserve LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        print(f"  Found {len(columns)} columns in Reserve table")
        print(f"  Key columns: {', '.join([c for c in columns if any(k in c.lower() for k in ['key', 'id', 'balance', 'paid', 'gratuity', 'extra'])])}")
        
        # Extract key fields only
        key_fields = ['Key']  # MDB Reserve key field
        balance_fields = [c for c in columns if 'balance' in c.lower()]
        paid_fields = [c for c in columns if 'paid' in c.lower()]
        gratuity_fields = [c for c in columns if 'gratuity' in c.lower()]
        extra_fields = [c for c in columns if 'extra' in c.lower()]
        date_fields = [c for c in columns if 'date' in c.lower()]
        
        all_fields = list(set(key_fields + balance_fields + paid_fields + gratuity_fields + extra_fields + date_fields[:3]))
        
        if all_fields:
            query = f"SELECT {', '.join(all_fields)} FROM Reserve"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            reserves = {}
            for row in rows:
                record = {}
                for i, field in enumerate(all_fields):
                    record[field] = row[i]
                
                # Use Key as the unique identifier
                if 'Key' in record:
                    reserves[record['Key']] = record
            
            print(f"  ✓ Extracted {len(reserves)} reserves")
            return reserves
        
    except Exception as e:
        print(f"  Error extracting MDB Reserve: {e}")
    finally:
        conn.close()
    
    return {}

def extract_mdb_payments():
    """Extract Payment table from MDB"""
    conn = get_mdb_connection()
    if not conn:
        return {}
    
    print("Connecting to MDB Payment table...")
    try:
        cursor = conn.cursor()
        
        # Get columns
        cursor.execute("SELECT * FROM Payment LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        print(f"  Found {len(columns)} columns in Payment table")
        print(f"  Columns: {', '.join(columns)}")
        
        # Extract all fields
        cursor.execute("SELECT * FROM Payment")
        rows = cursor.fetchall()
        
        payments = []
        for row in rows:
            record = {}
            for i, field in enumerate(columns):
                record[field] = row[i]
            payments.append(record)
        
        print(f"  ✓ Extracted {len(payments)} payments")
        return payments
        
    except Exception as e:
        print(f"  Error extracting MDB Payment: {e}")
    finally:
        conn.close()
    
    return []

def extract_mdb_charges():
    """Extract Charge table from MDB"""
    conn = get_mdb_connection()
    if not conn:
        return {}
    
    print("Connecting to MDB Charge table...")
    try:
        cursor = conn.cursor()
        
        # Get columns
        cursor.execute("SELECT * FROM Charge LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        print(f"  Found {len(columns)} columns in Charge table")
        print(f"  Key columns: {', '.join([c for c in columns if any(k in c.lower() for k in ['key', 'id', 'amount', 'total', 'gst'])])}")
        
        # Extract all fields
        cursor.execute("SELECT * FROM Charge")
        rows = cursor.fetchall()
        
        charges = []
        for row in rows:
            record = {}
            for i, field in enumerate(columns):
                record[field] = row[i]
            charges.append(record)
        
        print(f"  ✓ Extracted {len(charges)} charges")
        return charges
        
    except Exception as e:
        print(f"  Error extracting MDB Charge: {e}")
    finally:
        conn.close()
    
    return []

def extract_pg_charters():
    """Extract PostgreSQL charters"""
    conn = get_pg_connection()
    if not conn:
        return {}
    
    print("Connecting to PostgreSQL charters table...")
    try:
        cursor = conn.cursor()
        
        # Extract with key fields
        query = """
        SELECT 
            charter_id, 
            reserve_number, 
            balance, 
            driver_paid,
            driver_gratuity,
            total_amount_due,
            charter_date,
            updated_at
        FROM charters
        WHERE charter_id IS NOT NULL
        ORDER BY reserve_number
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        charters = {}
        for row in rows:
            charter = {
                'charter_id': row[0],
                'reserve_number': row[1],
                'balance': float(row[2]) if row[2] else None,
                'driver_paid': float(row[3]) if row[3] else None,
                'driver_gratuity': float(row[4]) if row[4] else None,
                'total_amount_due': float(row[5]) if row[5] else None,
                'charter_date': row[6],
                'updated_at': row[7]
            }
            if row[1]:  # reserve_number
                charters[row[1]] = charter
        
        print(f"  ✓ Extracted {len(charters)} charters")
        return charters
        
    except Exception as e:
        print(f"  Error extracting PostgreSQL charters: {e}")
    finally:
        conn.close()
    
    return {}

def extract_pg_payments():
    """Extract PostgreSQL payments"""
    conn = get_pg_connection()
    if not conn:
        return []
    
    print("Connecting to PostgreSQL payments table...")
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            payment_id,
            reserve_number,
            charter_id,
            amount,
            payment_date,
            payment_method,
            updated_at
        FROM payments
        ORDER BY reserve_number, payment_date
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        payments = []
        for row in rows:
            payment = {
                'payment_id': row[0],
                'reserve_number': row[1],
                'charter_id': row[2],
                'amount': float(row[3]) if row[3] else None,
                'payment_date': row[4],
                'payment_method': row[5],
                'updated_at': row[6]
            }
            payments.append(payment)
        
        print(f"  ✓ Extracted {len(payments)} payments")
        return payments
        
    except Exception as e:
        print(f"  Error extracting PostgreSQL payments: {e}")
    finally:
        conn.close()
    
    return []

def extract_pg_charges():
    """Extract PostgreSQL charges"""
    conn = get_pg_connection()
    if not conn:
        return []
    
    print("Connecting to PostgreSQL charges table...")
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            charge_id,
            reserve_number,
            charter_id,
            amount,
            gst_amount,
            updated_at
        FROM charter_charges
        ORDER BY reserve_number
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        charges = []
        for row in rows:
            charge = {
                'charge_id': row[0],
                'reserve_number': row[1],
                'charter_id': row[2],
                'amount': float(row[3]) if row[3] else None,
                'gst_amount': float(row[4]) if row[4] else None,
                'updated_at': row[5]
            }
            charges.append(charge)
        
        print(f"  ✓ Extracted {len(charges)} charges")
        return charges
        
    except Exception as e:
        print(f"  Error extracting PostgreSQL charges: {e}")
    finally:
        conn.close()
    
    return []

def generate_comparison_report(mdb_reserves, mdb_payments, mdb_charges, 
                              pg_charters, pg_payments, pg_charges):
    """Generate detailed comparison report"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'mdb_data': {
            'reserves_count': len(mdb_reserves),
            'payments_count': len(mdb_payments),
            'charges_count': len(mdb_charges),
            'sample_fields_in_reserve': list(mdb_reserves.values())[0].keys() if mdb_reserves else []
        },
        'pg_data': {
            'charters_count': len(pg_charters),
            'payments_count': len(pg_payments),
            'charges_count': len(pg_charges)
        },
        'findings': []
    }
    
    # Key findings
    findings = []
    
    # 1. Balance changes
    zero_balance_count = sum(1 for c in pg_charters.values() if c['balance'] == 0)
    findings.append({
        'category': 'Charters with $0 balance',
        'count': zero_balance_count,
        'percentage': f"{(zero_balance_count/len(pg_charters)*100):.1f}%" if pg_charters else "N/A",
        'interpretation': 'Likely already reconciled - aged debt removed or paid'
    })
    
    # 2. Payment coverage
    pg_payment_by_reserve = defaultdict(float)
    for p in pg_payments:
        if p['reserve_number']:
            pg_payment_by_reserve[p['reserve_number']] += p['amount'] or 0
    
    fully_paid = sum(1 for c in pg_charters.values() if pg_payment_by_reserve.get(c['reserve_number'], 0) >= c['total_amount_due'])
    findings.append({
        'category': 'Fully paid charters',
        'count': fully_paid,
        'percentage': f"{(fully_paid/len(pg_charters)*100):.1f}%" if pg_charters else "N/A",
        'interpretation': 'Payment amount >= total amount due'
    })
    
    # 3. Gratuity usage
    gratuity_set = sum(1 for c in pg_charters.values() if c['driver_gratuity'] and c['driver_gratuity'] > 0)
    findings.append({
        'category': 'Charters with gratuity',
        'count': gratuity_set,
        'percentage': f"{(gratuity_set/len(pg_charters)*100):.1f}%" if pg_charters else "N/A",
        'interpretation': 'Gratuity field populated (potential non-taxed gratuity split)'
    })
    
    report['findings'] = findings
    
    print("\n" + "="*70)
    print("COMPARISON FINDINGS")
    print("="*70)
    
    for finding in findings:
        print(f"\n📊 {finding['category']}: {finding['count']} ({finding['percentage']})")
        print(f"   → {finding['interpretation']}")
    
    # Save report
    output_file = r"L:\limo\reports\charter_comparison_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n✓ Report saved to {output_file}")
    return report

if __name__ == '__main__':
    print("\n" + "="*70)
    print("EXTRACTING CHARTER/PAYMENT/CHARGE DATA FROM MDB AND POSTGRESQL")
    print("="*70)
    
    # Extract from MDB
    print("\n🔍 MDB EXTRACTION:")
    mdb_reserves = extract_mdb_reserves()
    mdb_payments = extract_mdb_payments()
    mdb_charges = extract_mdb_charges()
    
    # Extract from PostgreSQL
    print("\n🔍 POSTGRESQL EXTRACTION:")
    pg_charters = extract_pg_charters()
    pg_payments = extract_pg_payments()
    pg_charges = extract_pg_charges()
    
    # Generate comparison
    print("\n📊 GENERATING COMPARISON REPORT:")
    report = generate_comparison_report(mdb_reserves, mdb_payments, mdb_charges,
                                       pg_charters, pg_payments, pg_charges)
    
    print("\n" + "="*70)
    print("EXTRACTION COMPLETE")
    print("="*70)
