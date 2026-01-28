#!/usr/bin/env python
"""
Extract current state of charters, payments, and charges from PostgreSQL
and save to JSON for easy parsing and comparison.
"""
import psycopg2
import json
import os
from datetime import datetime
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

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

def extract_charters():
    """Extract all charters with key fields"""
    conn = get_pg_connection()
    if not conn:
        return {}
    
    print("Extracting charters...")
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            charter_id,
            reserve_number,
            client_id,
            account_number,
            charter_date,
            balance,
            total_amount_due,
            driver_paid,
            driver_gratuity,
            status,
            updated_at
        FROM charters
        WHERE reserve_number IS NOT NULL
        ORDER BY reserve_number
        LIMIT 100
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        charters = {}
        for row in rows:
            charter = {
                'charter_id': row[0],
                'reserve_number': row[1],
                'client_id': row[2],
                'account_number': row[3],
                'charter_date': row[4].isoformat() if row[4] else None,
                'balance': float(row[5]) if row[5] else 0,
                'total_amount_due': float(row[6]) if row[6] else 0,
                'driver_paid': float(row[7]) if row[7] else 0,
                'driver_gratuity': float(row[8]) if row[8] else 0,
                'status': row[9],
                'updated_at': row[10].isoformat() if row[10] else None
            }
            charters[str(row[1])] = charter
        
        print(f"  ✓ Extracted {len(charters)} charters")
        return charters
        
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        conn.close()
    
    return {}

def extract_payments():
    """Extract payments grouped by reserve_number"""
    conn = get_pg_connection()
    if not conn:
        return {}
    
    print("Extracting payments...")
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
        WHERE reserve_number IS NOT NULL
        ORDER BY reserve_number, payment_date
        LIMIT 500
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Group by reserve_number
        payments_by_reserve = {}
        for row in rows:
            reserve = str(row[1])
            if reserve not in payments_by_reserve:
                payments_by_reserve[reserve] = []
            
            payment = {
                'payment_id': row[0],
                'amount': float(row[3]) if row[3] else 0,
                'payment_date': row[4].isoformat() if row[4] else None,
                'payment_method': row[5],
                'charter_id': row[2],
                'updated_at': row[6].isoformat() if row[6] else None
            }
            payments_by_reserve[reserve].append(payment)
        
        print(f"  ✓ Extracted {len(payments_by_reserve)} reserves with payments")
        return payments_by_reserve
        
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        conn.close()
    
    return {}

def extract_charges():
    """Extract charges grouped by reserve_number"""
    conn = get_pg_connection()
    if not conn:
        return {}
    
    print("Extracting charges...")
    try:
        cursor = conn.cursor()
        
        query = """
        SELECT 
            charge_id,
            reserve_number,
            charter_id,
            amount,
            gst_amount,
            description,
            created_at
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        ORDER BY reserve_number
        LIMIT 1000
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Group by reserve_number
        charges_by_reserve = {}
        for row in rows:
            reserve = str(row[1])
            if reserve not in charges_by_reserve:
                charges_by_reserve[reserve] = []
            
            charge = {
                'charge_id': row[0],
                'amount': float(row[3]) if row[3] else 0,
                'gst_amount': float(row[4]) if row[4] else 0,
                'description': row[5],
                'charter_id': row[2],
                'created_at': row[6].isoformat() if row[6] else None
            }
            charges_by_reserve[reserve].append(charge)
        
        print(f"  ✓ Extracted {len(charges_by_reserve)} reserves with charges")
        return charges_by_reserve
        
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        conn.close()
    
    return {}

def save_json_file(data, filename):
    """Save data to JSON file"""
    filepath = rf"L:\limo\reports\{filename}"
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"✓ Saved to {filepath}")
    return filepath

if __name__ == '__main__':
    print("\n" + "="*70)
    print("EXTRACTING CURRENT ALMSDATA STATE TO JSON")
    print("="*70 + "\n")
    
    # Extract data
    charters = extract_charters()
    payments = extract_payments()
    charges = extract_charges()
    
    # Combine into one file
    almsdata_state = {
        'timestamp': datetime.now().isoformat(),
        'database': 'almsdata (PostgreSQL)',
        'statistics': {
            'charters_count': len(charters),
            'payment_groups_count': len(payments),
            'charge_groups_count': len(charges)
        },
        'charters': charters,
        'payments': payments,
        'charges': charges
    }
    
    save_json_file(almsdata_state, 'almsdata_current_state.json')
    
    print("\n" + "="*70)
    print("EXTRACTION COMPLETE")
    print("="*70)
    print("\nNext: Use compare_json_files.py to compare MDB vs PostgreSQL")
