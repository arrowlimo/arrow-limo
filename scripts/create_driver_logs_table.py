"""
Create charter_driver_logs table for driver-side information capture.

Business Rules:
- Link via reserve_number (BUSINESS KEY) NOT charter_id
- Store driver times, odometer, fuel, HOS (Hours of Service) notes
- Support multiple submissions per charter (e.g., multiple legs or corrections)
- Keep JSON backup for historical reference
"""

import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REDACTED***')

def create_driver_logs_table():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        # Check if table already exists
        cur.execute("""
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'charter_driver_logs'
        """)
        
        if cur.fetchone():
            print("✅ charter_driver_logs table already exists")
            cur.close()
            conn.close()
            return
        
        # Create table with proper structure
        cur.execute("""
        CREATE TABLE charter_driver_logs (
            driver_log_id SERIAL PRIMARY KEY,
            reserve_number VARCHAR(20) NOT NULL,
            charter_id INT,
            depart_time TIME,
            pickup_time TIME,
            start_odometer INT,
            end_odometer INT,
            fuel_liters INT,
            fuel_amount NUMERIC(10,2),
            float_amount NUMERIC(10,2),
            hos_notes TEXT,
            driver_notes TEXT,
            submitted_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            json_backup JSONB,
            FOREIGN KEY (reserve_number) REFERENCES charters(reserve_number) ON DELETE CASCADE,
            UNIQUE(reserve_number, submitted_at)
        )
        """)
        
        # Create indexes for fast lookups
        cur.execute("CREATE INDEX idx_driver_logs_reserve ON charter_driver_logs(reserve_number)")
        cur.execute("CREATE INDEX idx_driver_logs_charter ON charter_driver_logs(charter_id)")
        cur.execute("CREATE INDEX idx_driver_logs_submitted ON charter_driver_logs(submitted_at)")
        
        conn.commit()
        print("✅ charter_driver_logs table created successfully")
        print(f"   Location: public.charter_driver_logs")
        print(f"   Columns: driver_log_id, reserve_number, charter_id, depart_time, pickup_time,")
        print(f"            start_odometer, end_odometer, fuel_liters, fuel_amount, float_amount,")
        print(f"            hos_notes, driver_notes, submitted_at, created_at, updated_at, json_backup")
        
    except psycopg2.Error as e:
        conn.rollback()
        print(f"❌ Error creating table: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_driver_logs_table()
