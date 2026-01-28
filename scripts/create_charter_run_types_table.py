#!/usr/bin/env python3
"""
Create charter_run_types table for admin-configurable run type dropdown
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Create table
cur.execute("""
CREATE TABLE IF NOT EXISTS charter_run_types (
    run_type_id SERIAL PRIMARY KEY,
    run_type_name VARCHAR(100) UNIQUE NOT NULL,
    display_order INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
)
""")

# Insert default run types
default_run_types = [
    ("Airport Run", 10),
    ("Birthday Party", 20),
    ("Corporate Event", 30),
    ("Graduation", 40),
    ("Wedding", 50),
    ("Wine Tour", 60),
    ("City Tour", 70),
    ("Concert/Event", 80),
    ("Sporting Event", 90),
    ("Other", 100),
]

for run_type_name, display_order in default_run_types:
    cur.execute("""
        INSERT INTO charter_run_types (run_type_name, display_order)
        VALUES (%s, %s)
        ON CONFLICT (run_type_name) DO NOTHING
    """, (run_type_name, display_order))

conn.commit()
cur.close()
conn.close()

print("✅ charter_run_types table created successfully")
print(f"✅ Inserted {len(default_run_types)} default run types")
