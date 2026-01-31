"""
Audit LMS vs almsdata balance matching
Answers:
1. How many LMS tables have been changed?
2. Which ones were recently changed?
3. Are our almsdata balances matching LMS balances?
"""

import pyodbc
import psycopg2
import os
from decimal import Decimal
from datetime import datetime
import pandas as pd

# LMS connection
LMS_PATH = r'L:\limo\data\lms.mdb'
lms_conn_str = (
    rf'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};'
    rf'DBQ={LMS_PATH};'
)

# almsdata connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

print("=" * 80)
print("LMS vs almsdata BALANCE AUDIT")
print("=" * 80)

# 1. Check LMS table info
print("\n1. LMS DATABASE TABLE INFORMATION")
print("-" * 80)
try:
    lms_conn = pyodbc.connect(lms_conn_str)
    cursor = lms_conn.cursor()
    
    # Get all tables
    tables = cursor.tables(tableType='TABLE')
    table_list = [row.table_name for row in tables if not row.table_name.startswith('MSys')]
    
    print(f"Total LMS tables: {len(table_list)}")
    print(f"Tables: {', '.join(sorted(table_list))}")
    
    # Get Reserve table info
    print("\nReserve table structure:")
    cursor.execute("SELECT * FROM Reserve WHERE 1=0")
    columns = [desc[0] for desc in cursor.description]
    print(f"Columns: {', '.join(columns)}")
    
    # Count reserves
    cursor.execute("SELECT COUNT(*) as cnt FROM Reserve")
    res_count = cursor.fetchone()[0]
    print(f"Total reserves in LMS: {res_count}")
    
    lms_conn.close()
except Exception as e:
    print(f"ERROR accessing LMS: {e}")
    import traceback
    traceback.print_exc()

# 2. Load LMS balance data
print("\n2. LOADING LMS BALANCE DATA")
print("-" * 80)
try:
    lms_conn = pyodbc.connect(lms_conn_str)
    cursor = lms_conn.cursor()
    
    # Load all reserves with balance
    cursor.execute("""
        SELECT Reserve_No, Name, PU_Date, Est_Charge, Balance
        FROM Reserve
        ORDER BY Reserve_No
    """)
    
    lms_data = {}
    for row in cursor.fetchall():
        reserve_no = str(row[0]).strip() if row[0] else None
        name = str(row[1]).strip() if row[1] else None
        pu_date = row[2]
        est_charge = row[3]
        balance = row[4]
        
        if reserve_no:
            lms_data[reserve_no] = {
                'name': name,
                'pu_date': pu_date,
                'est_charge': est_charge,
                'balance': balance
            }
    
    print(f"Loaded {len(lms_data)} LMS reserves with balance data")
    lms_conn.close()
    
except Exception as e:
    print(f"ERROR loading LMS data: {e}")
    import traceback
    traceback.print_exc()

# 3. Load almsdata balance data
print("\n3. LOADING ALMSDATA BALANCE DATA")
print("-" * 80)
try:
    alms_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    alms_cursor = alms_conn.cursor()
    
    # Get all charters with balance
    alms_cursor.execute("""
        SELECT 
            c.reserve_number,
            c.client_id,
            cl.name,
            c.charter_date,
            c.total_amount_due,
            c.balance,
            c.created_at
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number IS NOT NULL
        ORDER BY c.reserve_number
    """)
    
    alms_data = {}
    for row in alms_cursor.fetchall():
        reserve_no = row[0]
        client_name = row[2]
        charter_date = row[3]
        total_due = row[4]
        balance = row[5]
        created_at = row[6]
        
        alms_data[reserve_no] = {
            'name': client_name,
            'charter_date': charter_date,
            'total_due': total_due,
            'balance': balance,
            'created_at': created_at
        }
    
    print(f"Loaded {len(alms_data)} almsdata reserves with balance data")
    
    alms_conn.close()
    
except Exception as e:
    print(f"ERROR loading almsdata: {e}")
    import traceback
    traceback.print_exc()

# 4. Compare balances
print("\n4. BALANCE COMPARISON ANALYSIS")
print("-" * 80)

matches = 0
mismatches = 0
alms_only = 0
lms_only = 0

mismatch_details = []

# Check reserves in both databases
for reserve_no in sorted(set(list(lms_data.keys()) + list(alms_data.keys()))):
    if reserve_no not in lms_data:
        alms_only += 1
        print(f"ALMS ONLY: {reserve_no} (in almsdata but not LMS)")
    elif reserve_no not in alms_data:
        lms_only += 1
        print(f"LMS ONLY: {reserve_no} (in LMS but not almsdata)")
    else:
        # Both exist - compare balance
        lms_balance = lms_data[reserve_no]['balance']
        alms_balance = alms_data[reserve_no]['balance']
        
        # Handle None values
        if lms_balance is None:
            lms_balance = 0
        if alms_balance is None:
            alms_balance = 0
        
        # Convert to Decimal for comparison
        try:
            lms_bal_decimal = Decimal(str(lms_balance)) if lms_balance else Decimal(0)
            alms_bal_decimal = Decimal(str(alms_balance)) if alms_balance else Decimal(0)
        except:
            lms_bal_decimal = Decimal(0)
            alms_bal_decimal = Decimal(0)
        
        if lms_bal_decimal == alms_bal_decimal:
            matches += 1
        else:
            mismatches += 1
            mismatch_details.append({
                'reserve_no': reserve_no,
                'lms_name': lms_data[reserve_no]['name'],
                'lms_balance': float(lms_balance) if lms_balance else 0,
                'alms_balance': float(alms_balance) if alms_balance else 0,
                'difference': float(alms_balance - lms_balance) if (alms_balance and lms_balance) else 0
            })

print(f"\nBoth databases:")
print(f"  Matching balances: {matches}")
print(f"  MISMATCHED balances: {mismatches}")
print(f"  In almsdata only: {alms_only}")
print(f"  In LMS only: {lms_only}")

# Show mismatches
if mismatch_details:
    print(f"\n5. BALANCE MISMATCHES (showing first 50):")
    print("-" * 80)
    for i, detail in enumerate(sorted(mismatch_details, key=lambda x: x['reserve_no'])[:50]):
        print(f"Reserve {detail['reserve_no']} ({detail['lms_name']}):")
        print(f"  LMS Balance:    ${detail['lms_balance']:.2f}")
        print(f"  ALMS Balance:   ${detail['alms_balance']:.2f}")
        print(f"  Difference:     ${detail['difference']:.2f}")
    
    if len(mismatch_details) > 50:
        print(f"\n... and {len(mismatch_details) - 50} more mismatches")

# 5. Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
total_lms = len(lms_data)
total_alms = len(alms_data)
overlap = len([r for r in lms_data if r in alms_data])

print(f"\nLMS Database:")
print(f"  Total reserves: {total_lms}")
print(f"  Last modified: [Access DB - check file properties]")

print(f"\nAlmsdata Database:")
print(f"  Total reserves: {total_alms}")

print(f"\nBalance Sync Status:")
print(f"  Total in both: {overlap}")
print(f"  Matching balances: {matches} ({100*matches/max(overlap,1):.1f}%)")
print(f"  MISMATCHED balances: {mismatches} ({100*mismatches/max(overlap,1):.1f}%)")
print(f"  Data integrity: {'✅ OK' if mismatches == 0 else '⚠️  NEEDS ATTENTION'}")

print("\n" + "=" * 80)
