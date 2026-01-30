#!/usr/bin/env python3
"""
Check LMS data for the 24 charters with missing payments.
Query LMS database for payment records.
"""

import os
import sys

# Try to import pyodbc for LMS Access database
try:
    import pyodbc
except ImportError:
    print("❌ pyodbc not installed. Cannot access LMS Access database.")
    print("   Run: pip install pyodbc")
    sys.exit(1)

# List of 24 charters with missing payments
MISSING_PAYMENT_CHARTERS = [
    '019551', '019718', '007346', '006856', '019495', '019216', '019418', '008454',
    '007362', '019268', '008005', '019298', '019423', '007980', '019618', '019657',
    '007358', '019228', '019358', '008427', '019212', '008301', '006190', '007801',
    '005976'
]

LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'

print("="*100)
print("CHECK LMS DATA FOR 24 CHARTERS WITH MISSING PAYMENTS")
print("="*100)
print(f"\nLMS database: {LMS_PATH}")
print(f"File exists: {os.path.exists(LMS_PATH)}")

if not os.path.exists(LMS_PATH):
    print(f"❌ LMS database file not found!")
    sys.exit(1)

try:
    # Connect to LMS
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    conn = pyodbc.connect(conn_str)
    print("✅ Connected to LMS database")
    
    cur = conn.cursor()
    
    # Get list of tables
    print("\nTables in LMS database:")
    cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='TABLE'")
    for row in cur.fetchall():
        print(f"  {row[0]}")
    
    # Check for Payments table
    print("\n" + "-"*100)
    print("CHECKING FOR PAYMENT DATA IN LMS")
    print("-"*100)
    
    # Try different possible table names
    payment_tables = ['Payments', 'Payment', 'payments', 'reserve_payments', 'ReservePayments']
    
    for table_name in payment_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            count = cur.fetchone()[0]
            print(f"\n✅ Found table: {table_name} ({count:,} rows)")
            
            # Get columns
            cur.execute(f"SELECT * FROM [{table_name}] WHERE 1=0")
            print(f"   Columns: {', '.join([desc[0] for desc in cur.description])}")
            
            # Check for sample reserve
            placeholders = ','.join([f"'{r}'" for r in MISSING_PAYMENT_CHARTERS[:5]])
            cur.execute(f"SELECT COUNT(*) FROM [{table_name}] WHERE reserve_no IN ({placeholders})")
            match_count = cur.fetchone()[0]
            print(f"   Matches for first 5 charters: {match_count}")
            
        except Exception as e:
            pass  # Table doesn't exist
    
    # Try to find payments for our 24 reserves
    print("\n" + "-"*100)
    print("CHECKING RESERVES TABLE FOR PAYMENT DATA")
    print("-"*100)
    
    try:
        # Check Reserves table structure
        cur.execute("SELECT * FROM [Reserves] WHERE 1=0")
        columns = [desc[0] for desc in cur.description]
        print(f"\nReserves table columns: {', '.join(columns)}")
        
        # Look for payment-related columns
        payment_cols = [c for c in columns if 'pay' in c.lower() or 'amount' in c.lower() or 'balance' in c.lower()]
        if payment_cols:
            print(f"Payment-related columns: {', '.join(payment_cols)}")
        
        # Query our 24 charters
        placeholders = ','.join([f"'{r}'" for r in MISSING_PAYMENT_CHARTERS])
        query = f"SELECT reserve_no, {', '.join(payment_cols)} FROM [Reserves] WHERE reserve_no IN ({placeholders})"
        
        cur.execute(query)
        results = cur.fetchall()
        
        print(f"\nFound {len(results)} of 24 charters in LMS:")
        for row in results[:10]:
            print(f"  {row}")
            
    except Exception as e:
        print(f"Error querying Reserves: {e}")
    
    conn.close()
    
except pyodbc.Error as e:
    print(f"❌ Database connection error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*100)
