#!/usr/bin/env python3
"""
Find and use LMS relationship table to link PaymentID to Reserve_No/Charter.
"""

import pyodbc
import psycopg2

LMS_PATH = r'L:\New folder\lms.mdb'

def get_lms_connection():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

print("="*80)
print("FINDING LMS PAYMENT-CHARTER RELATIONSHIP TABLE")
print("="*80)

conn = get_lms_connection()
cur = conn.cursor()

# Check tables that might link Payment to Reserve/Charter
candidate_tables = [
    'D_Payables',  # Has Reserve_No, Amt_Paid, Key
    'Dri_Distr',   # Has Reserve_No, Amt_Paid, Key
    'Payment',     # Direct: Has Reserve_No
    'Reserve',     # Charter table
]

for table in candidate_tables:
    try:
        print(f"\n📋 {table} table:")
        
        # Get structure
        cur.execute(f"SELECT TOP 1 * FROM [{table}]")
        columns = [col[0] for col in cur.description]
        print(f"   Columns: {', '.join(columns)}")
        
        # Get count
        cur.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = cur.fetchone()[0]
        print(f"   Records: {count:,}")
        
        # Check for PaymentID column
        has_payment_id = 'PaymentID' in columns or 'Payment_ID' in columns
        has_reserve = any('reserve' in c.lower() for c in columns)
        
        if has_payment_id and has_reserve:
            print(f"   ✅ HAS BOTH PaymentID and Reserve columns!")
        elif has_payment_id:
            print(f"   ⚠️  Has PaymentID but no Reserve column")
        elif has_reserve:
            print(f"   ⚠️  Has Reserve but no PaymentID column")
        
        # Show sample with Reserve_No
        if has_reserve:
            reserve_col = next(c for c in columns if 'reserve' in c.lower())
            cur.execute(f"SELECT TOP 10 * FROM [{table}] WHERE {reserve_col} IS NOT NULL")
            rows = cur.fetchall()
            
            if rows:
                print(f"   Sample records:")
                for i, row in enumerate(rows[:5], 1):
                    print(f"      {i}. {row}")
    
    except Exception as e:
        print(f"   Error: {e}")

# Now check if Reserve table (charter table) has payment linkage info
print(f"\n" + "="*80)
print("RESERVE (CHARTER) TABLE ANALYSIS")
print("="*80)

try:
    cur.execute("SELECT TOP 1 * FROM Reserve")
    columns = [col[0] for col in cur.description]
    print(f"\nReserve table columns: {', '.join(columns)}")
    
    # Get sample
    cur.execute("SELECT TOP 10 * FROM Reserve")
    print(f"\nSample Reserve records:")
    for i, row in enumerate(cur.fetchall()[:5], 1):
        print(f"   {i}. {row}")

except Exception as e:
    print(f"Error: {e}")

# Check if there's a Payment-Reserve junction/link table
print(f"\n" + "="*80)
print("LOOKING FOR PAYMENT-RESERVE LINK TABLES")
print("="*80)

cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
all_tables = [row[0] for row in cur.fetchall()]

link_candidates = [t for t in all_tables if any(word in t.lower() for word in ['pay', 'reserve', 'charge'])]

print(f"\nTables with 'pay', 'reserve', or 'charge':")
for table in sorted(link_candidates):
    try:
        cur.execute(f"SELECT TOP 1 * FROM [{table}]")
        cols = [c[0] for c in cur.description]
        
        has_payment_ref = any('payment' in c.lower() for c in cols)
        has_reserve_ref = any('reserve' in c.lower() for c in cols)
        
        if has_payment_ref or has_reserve_ref:
            cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cur.fetchone()[0]
            markers = []
            if has_payment_ref:
                markers.append('💰 Payment')
            if has_reserve_ref:
                markers.append('📋 Reserve')
            
            print(f"\n   {table} ({count:,} records) - {' + '.join(markers)}")
            print(f"      Columns: {', '.join(cols)}")
    except:
        pass

conn.close()

print(f"\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
print("\n💡 Look for a table that has BOTH payment and reserve reference columns")
