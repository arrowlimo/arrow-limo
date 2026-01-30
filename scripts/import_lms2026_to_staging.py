#!/usr/bin/env python3
"""
LMS 2026 Complete Import to Staging Tables
Extracts all LMS data preserving relationships for gap analysis and selective merge
"""
import pyodbc
import psycopg2
from datetime import datetime
import json

# Database connections
LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'
PG_HOST = "localhost"
PG_DB = "almsdata"
PG_USER = "postgres"
PG_PASSWORD = "***REMOVED***"

def connect_lms():
    """Connect to LMS Access database"""
    try:
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"❌ Could not connect to LMS: {e}")
        print("   Make sure Microsoft Access Database Engine is installed")
        return None

def connect_postgres():
    """Connect to PostgreSQL"""
    return psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )

def create_staging_tables(pg_conn):
    """Create staging tables for LMS import"""
    cur = pg_conn.cursor()
    
    print("Creating staging tables...")
    
    # Drop existing staging tables
    cur.execute("""
        DROP TABLE IF EXISTS lms2026_charges CASCADE;
        DROP TABLE IF EXISTS lms2026_payments CASCADE;
        DROP TABLE IF EXISTS lms2026_reserves CASCADE;
        DROP TABLE IF EXISTS lms2026_customers CASCADE;
        DROP TABLE IF EXISTS lms2026_vehicles CASCADE;
        DROP TABLE IF EXISTS lms2026_employees CASCADE;
    """)
    
    # LMS Reserves (main charter table)
    cur.execute("""
        CREATE TABLE lms2026_reserves (
            id SERIAL PRIMARY KEY,
            reserve_no VARCHAR(20) NOT NULL,
            account_no VARCHAR(20),
            pu_date DATE,
            pu_time TIME,
            client_name TEXT,
            phone VARCHAR(50),
            email VARCHAR(255),
            pickup_address TEXT,
            dropoff_address TEXT,
            vehicle_code VARCHAR(20),
            driver_code VARCHAR(20),
            passenger_count INTEGER,
            rate NUMERIC(12,2),
            deposit NUMERIC(12,2),
            total NUMERIC(12,2),
            balance NUMERIC(12,2),
            status VARCHAR(50),
            notes TEXT,
            special_instructions TEXT,
            pymt_type VARCHAR(50),
            created_date TIMESTAMP,
            last_updated TIMESTAMP,
            raw_data JSONB,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(reserve_no)
        );
        CREATE INDEX idx_lms2026_reserves_reserve_no ON lms2026_reserves(reserve_no);
        CREATE INDEX idx_lms2026_reserves_account_no ON lms2026_reserves(account_no);
    """)
    
    # LMS Payments
    cur.execute("""
        CREATE TABLE lms2026_payments (
            id SERIAL PRIMARY KEY,
            payment_id INTEGER,
            reserve_no VARCHAR(20),
            account_no VARCHAR(20),
            amount NUMERIC(12,2),
            payment_date DATE,
            payment_method VARCHAR(50),
            check_number VARCHAR(50),
            deposit_key VARCHAR(50),
            payment_key VARCHAR(50),
            notes TEXT,
            last_updated TIMESTAMP,
            raw_data JSONB,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_lms2026_payments_reserve_no ON lms2026_payments(reserve_no);
        CREATE INDEX idx_lms2026_payments_payment_key ON lms2026_payments(payment_key);
    """)
    
    # LMS Charges
    cur.execute("""
        CREATE TABLE lms2026_charges (
            id SERIAL PRIMARY KEY,
            charge_id INTEGER,
            reserve_no VARCHAR(20),
            account_no VARCHAR(20),
            description TEXT,
            amount NUMERIC(12,2),
            rate NUMERIC(12,2),
            sequence INTEGER,
            is_closed BOOLEAN,
            is_frozen BOOLEAN,
            note TEXT,
            last_updated TIMESTAMP,
            raw_data JSONB,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX idx_lms2026_charges_reserve_no ON lms2026_charges(reserve_no);
    """)
    
    # LMS Customers
    cur.execute("""
        CREATE TABLE lms2026_customers (
            id SERIAL PRIMARY KEY,
            account_no VARCHAR(20) NOT NULL,
            primary_name TEXT,
            company_name TEXT,
            attention TEXT,
            email TEXT,
            work_phone VARCHAR(50),
            home_phone VARCHAR(50),
            cell_phone VARCHAR(50),
            address_line1 TEXT,
            address_line2 TEXT,
            city VARCHAR(100),
            state VARCHAR(10),
            zip_code VARCHAR(20),
            country VARCHAR(50),
            balance TEXT,
            credit_limit TEXT,
            last_updated TIMESTAMP,
            raw_data JSONB,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_no)
        );
        CREATE INDEX idx_lms2026_customers_account_no ON lms2026_customers(account_no);
    """)
    
    # LMS Vehicles
    cur.execute("""
        CREATE TABLE lms2026_vehicles (
            id SERIAL PRIMARY KEY,
            vehicle_code VARCHAR(20) NOT NULL,
            vin VARCHAR(50),
            make VARCHAR(50),
            model VARCHAR(50),
            year INTEGER,
            capacity INTEGER,
            vehicle_type VARCHAR(50),
            license_plate VARCHAR(20),
            status VARCHAR(50),
            last_updated TIMESTAMP,
            raw_data JSONB,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(vehicle_code)
        );
        CREATE INDEX idx_lms2026_vehicles_code ON lms2026_vehicles(vehicle_code);
    """)
    
    # LMS Employees (drivers)
    cur.execute("""
        CREATE TABLE lms2026_employees (
            id SERIAL PRIMARY KEY,
            employee_code VARCHAR(20) NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            employee_number VARCHAR(20),
            phone VARCHAR(50),
            email VARCHAR(255),
            hire_date DATE,
            status VARCHAR(50),
            last_updated TIMESTAMP,
            raw_data JSONB,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_code)
        );
        CREATE INDEX idx_lms2026_employees_code ON lms2026_employees(employee_code);
    """)
    
    pg_conn.commit()
    print("✅ Staging tables created")

def import_lms_table(lms_conn, pg_conn, lms_table, pg_table, field_map):
    """Generic LMS table import with field mapping"""
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    print(f"\n📥 Importing {lms_table}...")
    
    # Get all columns from LMS table
    lms_cur.execute(f"SELECT * FROM {lms_table}")
    columns = [col[0] for col in lms_cur.description]
    
    rows_imported = 0
    errors = []
    
    lms_cur.execute(f"SELECT * FROM {lms_table}")
    for row in lms_cur.fetchall():
        try:
            # Build row dict
            row_dict = {columns[i]: row[i] for i in range(len(columns))}
            
            # Map fields
            mapped_values = {}
            for pg_field, lms_field in field_map.items():
                if callable(lms_field):
                    mapped_values[pg_field] = lms_field(row_dict)
                else:
                    mapped_values[pg_field] = row_dict.get(lms_field)
            
            # Store raw JSON
            mapped_values['raw_data'] = json.dumps(row_dict, default=str)
            
            # Insert into PostgreSQL
            cols = ', '.join(mapped_values.keys())
            placeholders = ', '.join(['%s'] * len(mapped_values))
            
            pg_cur.execute(
                f"INSERT INTO {pg_table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                list(mapped_values.values())
            )
            
            rows_imported += 1
            if rows_imported % 100 == 0:
                print(f"  {rows_imported} rows...", end='\r')
                
        except Exception as e:
            errors.append(f"Row error: {e}")
    
    pg_conn.commit()
    print(f"✅ {lms_table}: {rows_imported} rows imported")
    
    if errors:
        print(f"⚠️  {len(errors)} errors (first 5):")
        for err in errors[:5]:
            print(f"   {err}")
    
    return rows_imported

def import_all_lms_data():
    """Main import orchestrator"""
    print("=" * 80)
    print("LMS 2026 COMPLETE IMPORT TO STAGING")
    print("=" * 80)
    
    # Connect to databases
    lms_conn = connect_lms()
    if not lms_conn:
        return
    
    pg_conn = connect_postgres()
    
    # Create staging tables
    create_staging_tables(pg_conn)
    
    # Import Reserves (main charter table)
    print("\n" + "=" * 80)
    print("IMPORTING RESERVES (CHARTERS)")
    print("=" * 80)
    reserves_map = {
        'reserve_no': 'Reserve_No',
        'account_no': 'Account_No',
        'pu_date': lambda r: r.get('PU_Date'),
        'pu_time': lambda r: r.get('PU_Time'),
        'client_name': 'Name',
        'phone': 'Phone',
        'email': 'EMail',
        'pickup_address': 'PU_Address',
        'dropoff_address': 'DO_Address',
        'vehicle_code': 'Vehicle',
        'driver_code': 'Driver',
        'passenger_count': 'Passengers',
        'rate': 'Rate',
        'deposit': 'Deposit',
        'total': 'Total',
        'balance': 'Balance',
        'status': 'Status',
        'notes': 'Notes',
        'special_instructions': 'Special_Instructions',
        'pymt_type': 'Pymt_Type',
        'last_updated': 'Last_Updated'
    }
    import_lms_table(lms_conn, pg_conn, 'Reserve', 'lms2026_reserves', reserves_map)
    
    # Import Payments
    print("\n" + "=" * 80)
    print("IMPORTING PAYMENTS")
    print("=" * 80)
    payments_map = {
        'payment_id': 'Payment_ID',
        'reserve_no': 'Reserve_No',
        'account_no': 'Account_No',
        'amount': 'Amount',
        'payment_date': 'Payment_Date',
        'payment_method': 'Payment_Type',
        'check_number': 'Check_No',
        'deposit_key': 'Deposit_Key',
        'payment_key': 'Payment_Key',
        'notes': 'Notes',
        'last_updated': 'Last_Updated'
    }
    import_lms_table(lms_conn, pg_conn, 'Payment', 'lms2026_payments', payments_map)
    
    # Import Charges
    print("\n" + "=" * 80)
    print("IMPORTING CHARGES")
    print("=" * 80)
    charges_map = {
        'charge_id': 'ID',
        'reserve_no': 'Reserve_No',
        'account_no': 'Account_No',
        'description': 'Desc',
        'amount': 'Amount',
        'rate': 'Rate',
        'sequence': 'Seq',
        'is_closed': 'Closed',
        'is_frozen': 'Frozen',
        'note': 'Note',
        'last_updated': 'Last_Updated'
    }
    import_lms_table(lms_conn, pg_conn, 'Charge', 'lms2026_charges', charges_map)
    
    # Import Customers
    print("\n" + "=" * 80)
    print("IMPORTING CUSTOMERS")
    print("=" * 80)
    customers_map = {
        'account_no': 'Account_No',
        'primary_name': 'Name',
        'company_name': 'Company',
        'attention': 'Attention',
        'email': 'EMail',
        'work_phone': 'Work_Phone',
        'home_phone': 'Home_Phone',
        'cell_phone': 'Cell_Phone',
        'address_line1': 'Address1',
        'address_line2': 'Address2',
        'city': 'City',
        'state': 'State',
        'zip_code': 'Zip',
        'country': 'Country',
        'balance': 'Balance',
        'credit_limit': 'Credit_Limit',
        'last_updated': 'Last_Updated'
    }
    import_lms_table(lms_conn, pg_conn, 'Customer', 'lms2026_customers', customers_map)
    
    # Import Vehicles
    print("\n" + "=" * 80)
    print("IMPORTING VEHICLES")
    print("=" * 80)
    vehicles_map = {
        'vehicle_code': 'Vehicle',
        'vin': 'VIN',
        'make': 'Make',
        'model': 'Model',
        'year': 'Year',
        'capacity': 'Capacity',
        'vehicle_type': 'Type',
        'license_plate': 'License',
        'status': 'Status',
        'last_updated': 'Last_Updated'
    }
    try:
        import_lms_table(lms_conn, pg_conn, 'Vehicles', 'lms2026_vehicles', vehicles_map)
    except Exception as e:
        print(f"⚠️  Vehicles table not found or error: {e}")
    
    # Import Drivers (Employees)
    print("\n" + "=" * 80)
    print("IMPORTING DRIVERS")
    print("=" * 80)
    employees_map = {
        'employee_code': 'Driver',
        'first_name': 'First_Name',
        'last_name': 'Last_Name',
        'employee_number': 'Emp_ID',
        'phone': 'Phone',
        'email': 'Email',
        'hire_date': 'Hire_Date',
        'status': 'Status',
        'last_updated': 'Last_Updated'
    }
    try:
        import_lms_table(lms_conn, pg_conn, 'Drivers', 'lms2026_employees', employees_map)
    except Exception as e:
        print(f"⚠️  Drivers table not found or error: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("IMPORT SUMMARY")
    print("=" * 80)
    
    cur = pg_conn.cursor()
    tables = [
        'lms2026_reserves',
        'lms2026_payments',
        'lms2026_charges',
        'lms2026_customers',
        'lms2026_vehicles',
        'lms2026_employees'
    ]
    
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  {table:30} {count:,} rows")
    
    pg_conn.close()
    lms_conn.close()
    
    print("\n✅ LMS 2026 import complete!")
    print("\nNext steps:")
    print("  1. Run: python scripts/analyze_lms_vs_almsdata_gaps.py")
    print("  2. Review gap analysis report")
    print("  3. Run: python scripts/merge_lms_to_almsdata.py --dry-run")

if __name__ == "__main__":
    import_all_lms_data()
