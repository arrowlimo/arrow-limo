#!/usr/bin/env python3
"""Check charter_run_types table and create if needed"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check if table exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'charter_run_types'
    )
""")
exists = cur.fetchone()[0]

if not exists:
    print("Table does not exist. Creating charter_run_types...")
    cur.execute("""
        CREATE TABLE charter_run_types (
            id SERIAL PRIMARY KEY,
            run_type_name VARCHAR(100) NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 999,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert standard run types
    run_types = [
        ("Airport Pick-up Calgary", True, 10),
        ("Airport Drop-off Calgary", True, 11),
        ("Airport Pick-up Edmonton", True, 12),
        ("Airport Drop-off Edmonton", True, 13),
        ("Airport Pick-up Red Deer", True, 14),
        ("Airport Drop-off Red Deer", True, 15),
        ("Concert Package", True, 20),
        ("Concert Run", True, 21),
        ("Sports Package", True, 30),
        ("Sports Run", True, 31),
        ("Birthday Party", True, 40),
        ("Corporate Event", True, 41),
        ("Graduation", True, 42),
        ("Wedding", True, 43),
        ("Wine Tour", True, 50),
        ("City Tour", True, 51),
        ("Split-run", True, 60),
        ("Donation", True, 70),
        ("Trade of Services", True, 71),
        ("Other", True, 999),
    ]
    
    for run_type, active, order in run_types:
        cur.execute("""
            INSERT INTO charter_run_types (run_type_name, is_active, display_order)
            VALUES (%s, %s, %s)
        """, (run_type, active, order))
    
    conn.commit()
    print("✅ Table created with default run types")
else:
    print("✅ Table exists. Current run types:")
    cur.execute("""
        SELECT id, run_type_name, is_active, display_order 
        FROM charter_run_types 
        ORDER BY display_order, run_type_name
    """)
    for row_id, name, active, order in cur.fetchall():
        status = "✓" if active else "✗"
        print(f"  {status} {name:30} (order: {order})")

cur.close()
conn.close()
