#!/usr/bin/env python3
"""
Import LMS Charge table from Access to Postgres
This creates the missing lms_charges table needed for complete mapping
"""

import pyodbc
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

def main():
    # Load environment variables
    load_dotenv()
    
    # Connect to LMS Access database
    lms_path = r'L:\limo\lms.mdb'
    access_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    access_conn = pyodbc.connect(access_conn_str)
    access_cursor = access_conn.cursor()
    
    # Connect to Postgres
    pg_conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'), 
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    pg_cursor = pg_conn.cursor()
    
    print("Creating lms_charges table...")
    
    # Drop and recreate the table
    pg_cursor.execute("DROP TABLE IF EXISTS lms_charges")
    
    create_sql = """
    CREATE TABLE lms_charges (
        charge_id INTEGER PRIMARY KEY,
        account_no VARCHAR(20),
        amount DECIMAL(10,4),
        closed BOOLEAN,
        description TEXT,
        frozen BOOLEAN,
        note TEXT,
        rate DECIMAL(10,4),
        reserve_no VARCHAR(20),
        sequence VARCHAR(20),
        tag BOOLEAN,
        last_updated TIMESTAMP,
        last_updated_by VARCHAR(50)
    )
    """
    pg_cursor.execute(create_sql)
    
    print("Loading data from LMS Access...")
    
    # Get all charges from Access
    access_cursor.execute("""
        SELECT Account_no, Amount, Closed, Desc, Frozen, Note, Rate, 
               Reserve_No, Sequence, Tag, LastUpdated, LastUpdatedBy, ChargeID
        FROM [Charge]
        ORDER BY ChargeID
    """)
    
    charges = access_cursor.fetchall()
    print(f"Found {len(charges)} charges to import")
    
    # Insert into Postgres
    insert_sql = """
    INSERT INTO lms_charges (
        account_no, amount, closed, description, frozen, note, rate,
        reserve_no, sequence, tag, last_updated, last_updated_by, charge_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    batch_size = 1000
    for i in range(0, len(charges), batch_size):
        batch = charges[i:i + batch_size]
        batch_data = []
        
        for charge in batch:
            # Convert Access data types
            account_no = charge[0]
            amount = float(charge[1]) if charge[1] is not None else 0.0
            closed = bool(charge[2])
            description = charge[3]
            frozen = bool(charge[4])
            note = charge[5]
            rate = float(charge[6]) if charge[6] is not None else 0.0
            reserve_no = charge[7]
            sequence = charge[8]
            tag = bool(charge[9])
            last_updated = charge[10]
            last_updated_by = charge[11]
            charge_id = int(charge[12])
            
            batch_data.append((
                account_no, amount, closed, description, frozen, note, rate,
                reserve_no, sequence, tag, last_updated, last_updated_by, charge_id
            ))
        
        pg_cursor.executemany(insert_sql, batch_data)
        print(f"Imported batch {i//batch_size + 1}/{(len(charges)-1)//batch_size + 1}")
    
    # Create indexes for better performance
    print("Creating indexes...")
    pg_cursor.execute("CREATE INDEX idx_lms_charges_reserve_no ON lms_charges(reserve_no)")
    pg_cursor.execute("CREATE INDEX idx_lms_charges_account_no ON lms_charges(account_no)")
    pg_cursor.execute("CREATE INDEX idx_lms_charges_amount ON lms_charges(amount)")
    
    # Commit changes
    pg_conn.commit()
    
    # Get final count
    pg_cursor.execute("SELECT COUNT(*) FROM lms_charges")
    final_count = pg_cursor.fetchone()[0]
    
    print(f"Successfully imported {final_count} charges to lms_charges table")
    
    # Show sample of imported data
    print("\nSample imported data:")
    pg_cursor.execute("SELECT * FROM lms_charges LIMIT 3")
    samples = pg_cursor.fetchall()
    for sample in samples:
        print(f"  ChargeID {sample[0]}: Reserve {sample[8]}, {sample[3]}, ${sample[1]}")
    
    # Close connections
    access_cursor.close()
    access_conn.close()
    pg_cursor.close() 
    pg_conn.close()
    
    print("\nLMS Charges import completed!")

if __name__ == "__main__":
    main()