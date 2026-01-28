#!/usr/bin/env python3
"""
Analyze empty tables to understand their purpose and determine if they're still needed
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 100)
print("EMPTY TABLES - PURPOSE & CURRENT USAGE ANALYSIS")
print("=" * 100)

empty_tables = [
    ('maintenance_records', 'Store vehicle maintenance/repair history'),
    ('bookings', 'Track booking/reservation lifecycle'),
    ('vehicle_documents', 'Store scanned PDFs/documents for vehicles'),
    ('vehicle_fuel_log', 'Track fuel purchases per vehicle'),
    ('vehicle_insurance', 'Track insurance policies and payments'),
    ('payment_reconciliation', 'Track bank reconciliation status'),
    ('invoices', 'Generate and track customer invoices'),
]

for table_name, purpose in empty_tables:
    print(f"\n{'=' * 100}")
    print(f"TABLE: {table_name}")
    print(f"PURPOSE: {purpose}")
    print(f"{'=' * 100}")
    
    # Check if table exists
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name = '{table_name}'
    """)
    exists = cur.fetchone()[0] > 0
    
    if not exists:
        print(f"  [FAIL] Table does not exist in database")
        continue
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]
    print(f"  📊 Current rows: {row_count}")
    
    # Get columns
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
        LIMIT 10
    """)
    cols = cur.fetchall()
    print(f"  📋 Columns ({len(cols)} shown):")
    for col, dtype in cols:
        print(f"      - {col} ({dtype})")
    
    # Check for alternative data storage
    print(f"\n  🔍 Alternative data storage check:")
    
    if table_name == 'maintenance_records':
        # Check vehicles table for maintenance fields
        cur.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE last_service_date IS NOT NULL
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ vehicles.last_service_date populated: {count} vehicles")
        
        cur.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE service_history IS NOT NULL
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ vehicles.service_history (JSONB) populated: {count} vehicles")
        
        # Check receipts for maintenance
        cur.execute("""
            SELECT COUNT(*) FROM general_ledger 
            WHERE account_name ILIKE '%repair%' OR account_name ILIKE '%maintenance%'
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ Maintenance in general_ledger: {count} entries")
    
    elif table_name == 'bookings':
        # Check charters for pending/quote status
        cur.execute("""
            SELECT status, COUNT(*) FROM charters 
            WHERE status IS NOT NULL 
            GROUP BY status 
            ORDER BY COUNT(*) DESC
        """)
        statuses = cur.fetchall()
        print(f"      ✓ Charter statuses (used for booking workflow):")
        for status, count in statuses[:5]:
            print(f"          - {status}: {count} charters")
    
    elif table_name == 'vehicle_documents':
        # Check other document tables
        cur.execute("SELECT COUNT(*) FROM driver_documents")
        count = cur.fetchone()[0]
        print(f"      ✓ driver_documents table: {count} documents")
        
        cur.execute("SELECT COUNT(*) FROM financial_documents")
        count = cur.fetchone()[0]
        print(f"      ✓ financial_documents table: {count} documents")
        
        print(f"      [WARN]  No PDF storage system implemented yet")
    
    elif table_name == 'vehicle_fuel_log':
        # Check general ledger for fuel
        cur.execute("""
            SELECT COUNT(*) FROM general_ledger 
            WHERE account_name ILIKE '%fuel%' OR account_name ILIKE '%gas%'
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ Fuel in general_ledger: {count} entries")
        
        # Check vehicles for fuel efficiency tracking
        cur.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE fuel_efficiency_data IS NOT NULL
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ vehicles.fuel_efficiency_data (JSONB): {count} vehicles")
        
        print(f"      [WARN]  No per-vehicle fuel tracking (odometer + receipts)")
    
    elif table_name == 'vehicle_insurance':
        # Check if vehicles table has insurance columns
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name = 'vehicles' AND column_name LIKE '%insurance%'
        """)
        count = cur.fetchone()[0]
        if count > 0:
            print(f"      ✓ vehicles table has {count} insurance columns")
        else:
            print(f"      [FAIL] vehicles table has NO insurance columns")
        
        cur.execute("""
            SELECT COUNT(*) FROM general_ledger 
            WHERE account_name ILIKE '%insurance%'
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ Insurance in general_ledger: {count} entries")
    
    elif table_name == 'payment_reconciliation':
        # Check bank_reconciliation
        cur.execute("SELECT COUNT(*) FROM bank_reconciliation")
        count = cur.fetchone()[0]
        print(f"      ✓ bank_reconciliation table: {count} records")
        
        cur.execute("SELECT COUNT(*) FROM banking_transactions")
        count = cur.fetchone()[0]
        print(f"      ✓ banking_transactions table: {count} records")
    
    elif table_name == 'invoices':
        # Check invoice_tracking
        cur.execute("SELECT COUNT(*) FROM invoice_tracking")
        count = cur.fetchone()[0]
        print(f"      ✓ invoice_tracking table: {count} records")
        
        cur.execute("""
            SELECT COUNT(*) FROM charters WHERE balance > 0
        """)
        count = cur.fetchone()[0]
        print(f"      ✓ Charters with balance owing: {count}")
    
    # Recommendation
    print(f"\n  💡 RECOMMENDATION:")
    if row_count == 0:
        if table_name == 'maintenance_records':
            print(f"      [WARN]  KEEP - Need proper maintenance scheduling system")
            print(f"         Current: Using vehicles.service_history (JSONB) - not ideal for reporting")
            print(f"         Should: Build maintenance_records table with proper schema")
        elif table_name == 'bookings':
            print(f"      [OK] DROP - Booking workflow handled by charters.status")
        elif table_name == 'vehicle_documents':
            print(f"      [WARN]  KEEP - Need PDF document storage system")
            print(f"         Current: No document storage implemented")
            print(f"         Should: Add file_path column + S3/filesystem storage")
        elif table_name == 'vehicle_fuel_log':
            print(f"      [WARN]  KEEP - Need per-vehicle fuel tracking")
            print(f"         Current: Fuel in general_ledger without vehicle linkage")
            print(f"         Should: Link receipts to vehicles + track odometer")
        elif table_name == 'vehicle_insurance':
            print(f"      [WARN]  KEEP - Need insurance tracking system")
            print(f"         Current: No structured insurance data")
            print(f"         Should: Store policies, premiums, renewals, claims")
        elif table_name == 'payment_reconciliation':
            print(f"      [OK] DROP - Using bank_reconciliation + banking_transactions")
        elif table_name == 'invoices':
            print(f"      [OK] DROP - Using invoice_tracking + charters.balance")
    else:
        print(f"      [OK] KEEP - Has {row_count} records")

print("\n" + "=" * 100)
print("SUMMARY - EMPTY TABLES DECISION")
print("=" * 100)

recommendations = {
    'DROP': [
        ('bookings', 'Charters table handles booking lifecycle with status field'),
        ('payment_reconciliation', 'Using bank_reconciliation table instead'),
        ('invoices', 'Using invoice_tracking + charters.balance instead'),
    ],
    'KEEP': [
        ('maintenance_records', 'Need proper maintenance scheduling (current JSONB approach inadequate)'),
        ('vehicle_documents', 'Need PDF storage system for insurance/registration docs'),
        ('vehicle_fuel_log', 'Need per-vehicle fuel tracking with odometer readings'),
        ('vehicle_insurance', 'Need insurance policy/premium/renewal tracking'),
    ]
}

print("\n[OK] SAFE TO DROP (3 tables):")
for table, reason in recommendations['DROP']:
    print(f"   • {table:<30} - {reason}")

print("\n[WARN]  KEEP FOR FUTURE USE (4 tables):")
for table, reason in recommendations['KEEP']:
    print(f"   • {table:<30} - {reason}")

conn.close()
