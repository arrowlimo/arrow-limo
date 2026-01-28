#!/usr/bin/env python3
"""
LMS RATE MAPPING IMPORT
=======================

Imports the LMS Rate Mapping List (extra charges table) into PostgreSQL
and creates a standardized fee structure for charge matching.
"""

import os
import pyodbc
import psycopg2
from datetime import datetime

# Database connections
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_connections():
    """Get both LMS and PostgreSQL connections."""
    
    # LMS Connection
    lms_path = r'L:\limo\backups\lms.mdb'
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    lms_conn = pyodbc.connect(lms_conn_str)
    
    # PostgreSQL Connection
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    return lms_conn, pg_conn

def extract_lms_rate_mapping(lms_conn):
    """Extract the Rate Mapping data from LMS."""
    
    print("📋 EXTRACTING LMS RATE MAPPING")
    print("-" * 29)
    
    cur = lms_conn.cursor()
    
    # The rate mapping table structure from the screenshot
    # Field, Sequence, Description, Flag, Rate, Formula
    try:
        # Try common table names for rate mapping
        table_queries = [
            "SELECT * FROM RateMapping ORDER BY Sequence",
            "SELECT * FROM Rate_Mapping ORDER BY Sequence", 
            "SELECT * FROM RateMappingList ORDER BY Sequence",
            "SELECT * FROM ExtraCharges ORDER BY Sequence",
            "SELECT * FROM Fees ORDER BY Sequence"
        ]
        
        rate_data = None
        table_name = None
        
        for query in table_queries:
            try:
                cur.execute(query)
                rate_data = cur.fetchall()
                table_name = query.split('FROM ')[1].split(' ')[0]
                print(f"   [OK] Found rate mapping in table: {table_name}")
                break
            except Exception as e:
                continue
        
        if not rate_data:
            # If standard queries fail, try to find the table by inspection
            cur.execute("SELECT Name FROM MSysObjects WHERE Type=1 AND Name NOT LIKE 'MSys%'")
            tables = [row[0] for row in cur.fetchall()]
            
            print(f"   📋 Available tables: {', '.join(tables)}")
            
            # Look for tables with rate/charge/fee in name
            rate_tables = [t for t in tables if any(keyword in t.lower() 
                          for keyword in ['rate', 'charge', 'fee', 'map', 'extra'])]
            
            if rate_tables:
                table_name = rate_tables[0]
                cur.execute(f"SELECT * FROM {table_name}")
                rate_data = cur.fetchall()
                print(f"   [OK] Using table: {table_name}")
            else:
                print("   [FAIL] No rate mapping table found")
                return []
        
        # Get column names
        column_names = [desc[0] for desc in cur.description]
        print(f"   📊 Columns: {', '.join(column_names)}")
        print(f"   📊 Records found: {len(rate_data):,}")
        
        # Convert to list of dictionaries
        rate_records = []
        for row in rate_data:
            record = dict(zip(column_names, row))
            rate_records.append(record)
        
        return rate_records
        
    except Exception as e:
        print(f"   [FAIL] Error extracting rate mapping: {str(e)}")
        return []

def create_lms_rate_mapping_table(pg_conn):
    """Create the LMS rate mapping table in PostgreSQL."""
    
    print("\n🔧 CREATING LMS RATE MAPPING TABLE")
    print("-" * 34)
    
    cur = pg_conn.cursor()
    
    try:
        # Create the rate mapping table
        cur.execute("""
            DROP TABLE IF EXISTS lms_rate_mapping CASCADE;
            CREATE TABLE lms_rate_mapping (
                mapping_id SERIAL PRIMARY KEY,
                field_id VARCHAR(50),
                sequence_number INTEGER,
                charge_description VARCHAR(200) NOT NULL,
                is_active BOOLEAN DEFAULT true,
                rate_amount DECIMAL(10,2),
                formula VARCHAR(100),
                charge_category VARCHAR(100),
                is_taxable BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("   [OK] Created lms_rate_mapping table")
        
        # Create indexes
        cur.execute("""
            CREATE INDEX idx_lms_rate_mapping_description 
            ON lms_rate_mapping(charge_description);
            
            CREATE INDEX idx_lms_rate_mapping_category 
            ON lms_rate_mapping(charge_category);
            
            CREATE INDEX idx_lms_rate_mapping_sequence 
            ON lms_rate_mapping(sequence_number);
        """)
        
        print("   [OK] Created indexes")
        
        pg_conn.commit()
        
    except Exception as e:
        print(f"   [FAIL] Error creating table: {str(e)}")
        pg_conn.rollback()

def categorize_charge_description(description):
    """Categorize charge descriptions into standard categories."""
    
    if not description:
        return 'Other'
    
    desc_lower = description.lower()
    
    # Define category mappings based on the screenshot
    categories = {
        'Transportation': ['airport', 'extra stops', 'wait', 'travel', 'pickup', 'dropoff'],
        'Beverages': ['beverage', 'alcohol', 'drink', 'champagne', 'wine', 'beer'],
        'Gratuities': ['gratuity', 'tip', 'service charge'],
        'Fuel': ['fuel', 'gas', 'surcharge', 'distance'],
        'Cleaning': ['clean', 'damage', 'broken', 'glass'],
        'Fees': ['service fee', 'misc fee', 'phone charge'],
        'Taxes': ['gst', 'hst', 'tax'],
        'Discounts': ['discount'],
        'Special': ['concert special', 'broken glass'],
        'Other': ['misc charges', 'other']
    }
    
    for category, keywords in categories.items():
        if any(keyword in desc_lower for keyword in keywords):
            return category
    
    return 'Other'

def import_rate_mapping_data(rate_records, pg_conn):
    """Import the rate mapping records into PostgreSQL."""
    
    print(f"\n📥 IMPORTING RATE MAPPING DATA")
    print("-" * 30)
    
    if not rate_records:
        print("   [FAIL] No rate records to import")
        return
    
    cur = pg_conn.cursor()
    
    imported_count = 0
    
    try:
        for record in rate_records:
            # Extract fields based on common LMS column names
            field_id = record.get('Field') or record.get('FieldID') or record.get('ID')
            sequence = record.get('Sequence') or record.get('SeqNo') or record.get('Order')
            description = record.get('Description') or record.get('Desc') or record.get('Name')
            flag = record.get('Flag') or record.get('Active') or record.get('Enabled')
            rate = record.get('Rate') or record.get('Amount') or record.get('Price')
            formula = record.get('Formula') or record.get('Calculation')
            
            # Clean and validate data
            if not description or description.strip() == '':
                continue
                
            description = str(description).strip()
            
            # Convert flag to boolean (True/False based on various representations)
            is_active = True
            if flag is not None:
                if isinstance(flag, bool):
                    is_active = flag
                elif isinstance(flag, str):
                    is_active = flag.lower() in ['true', 't', 'yes', 'y', '1', 'active']
                elif isinstance(flag, (int, float)):
                    is_active = bool(flag)
            
            # Convert sequence to integer with error handling
            sequence_num = None
            if sequence is not None and sequence != '':
                try:
                    if str(sequence).upper() != 'XXX':
                        sequence_num = int(sequence)
                except (ValueError, TypeError):
                    sequence_num = None
            
            # Convert rate to decimal
            rate_amount = None
            if rate is not None and rate != '':
                try:
                    rate_amount = float(rate)
                except (ValueError, TypeError):
                    rate_amount = None
            
            # Categorize the charge
            category = categorize_charge_description(description)
            
            # Determine if taxable (gratuities typically not taxed)
            is_taxable = category not in ['Gratuities']
            
            # Insert into database
            cur.execute("""
                INSERT INTO lms_rate_mapping (
                    field_id, sequence_number, charge_description, is_active,
                    rate_amount, formula, charge_category, is_taxable
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(field_id) if field_id else None,
                sequence_num,
                description,
                is_active,
                rate_amount,
                str(formula) if formula else None,
                category,
                is_taxable
            ))
            
            imported_count += 1
            
            if imported_count <= 10:  # Show first 10 imports
                rate_str = f"${rate_amount:.2f}" if rate_amount else "No rate"
                print(f"   [OK] Imported: {description} ({category}) - {rate_str}")
        
        pg_conn.commit()
        print(f"\n   📊 Successfully imported {imported_count:,} rate mapping records")
        
    except Exception as e:
        print(f"   [FAIL] Error importing data: {str(e)}")
        pg_conn.rollback()

def analyze_imported_rates(pg_conn):
    """Analyze the imported rate mapping data."""
    
    print(f"\n📊 RATE MAPPING ANALYSIS")
    print("-" * 23)
    
    cur = pg_conn.cursor()
    
    # Category breakdown
    cur.execute("""
        SELECT charge_category, COUNT(*) as count,
               COUNT(CASE WHEN rate_amount IS NOT NULL THEN 1 END) as with_rates,
               ROUND(AVG(rate_amount), 2) as avg_rate,
               ROUND(MIN(rate_amount), 2) as min_rate,
               ROUND(MAX(rate_amount), 2) as max_rate
        FROM lms_rate_mapping
        GROUP BY charge_category
        ORDER BY count DESC
    """)
    
    categories = cur.fetchall()
    
    print("📋 Categories:")
    for category, count, with_rates, avg_rate, min_rate, max_rate in categories:
        print(f"   • {category}: {count} charges ({with_rates} with rates)")
        if avg_rate:
            print(f"     Range: ${min_rate} - ${max_rate}, Avg: ${avg_rate}")
    
    # Active vs inactive
    cur.execute("""
        SELECT is_active, COUNT(*) 
        FROM lms_rate_mapping 
        GROUP BY is_active
    """)
    
    active_stats = cur.fetchall()
    print(f"\n📊 Status:")
    for is_active, count in active_stats:
        status = "Active" if is_active else "Inactive"
        print(f"   • {status}: {count:,} charges")
    
    # Sample charges by category
    print(f"\n📋 Sample Charges:")
    cur.execute("""
        SELECT charge_category, charge_description, rate_amount
        FROM lms_rate_mapping
        WHERE is_active = true
        ORDER BY charge_category, sequence_number
    """)
    
    samples = cur.fetchall()
    current_cat = None
    count = 0
    
    for category, description, rate in samples:
        if category != current_cat:
            current_cat = category
            print(f"\n   {category}:")
            count = 0
        
        if count < 3:  # Show 3 per category
            rate_str = f"${rate:.2f}" if rate else "No rate"
            print(f"     • {description} - {rate_str}")
            count += 1

def main():
    """Main import process."""
    
    print("📋 LMS RATE MAPPING IMPORT")
    print("=" * 26)
    
    try:
        # Get database connections
        lms_conn, pg_conn = get_connections()
        print("[OK] Database connections established")
        
        # Extract LMS rate mapping data
        rate_records = extract_lms_rate_mapping(lms_conn)
        
        if rate_records:
            # Create PostgreSQL table
            create_lms_rate_mapping_table(pg_conn)
            
            # Import the data
            import_rate_mapping_data(rate_records, pg_conn)
            
            # Analyze results
            analyze_imported_rates(pg_conn)
            
            print(f"\n[OK] IMPORT COMPLETED SUCCESSFULLY")
            print(f"   🎯 Ready for charge matching integration")
        else:
            print(f"\n[FAIL] No rate mapping data found in LMS")
        
    except Exception as e:
        print(f"\n[FAIL] Import failed: {str(e)}")
    
    finally:
        try:
            lms_conn.close()
            pg_conn.close()
            print(f"\n🔒 Database connections closed")
        except:
            pass

if __name__ == "__main__":
    # Set environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    main()