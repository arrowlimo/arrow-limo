#!/usr/bin/env python3
import psycopg2
import json

LOCAL_CONN_STRING = "dbname=almsdata host=localhost user=postgres password=***REDACTED***"

conn = psycopg2.connect(LOCAL_CONN_STRING)
cur = conn.cursor()

cur.execute("SELECT * FROM vehicles LIMIT 1")
col_names = [desc[0] for desc in cur.description]
vehicle = cur.fetchone()

print("Vehicle columns and values:")
for name, val in zip(col_names, vehicle):
    val_type = type(val).__name__
    val_str = str(val)[:50] if val is not None else "NULL"
    if isinstance(val, dict):
        print(f"⚠️  {name}: <dict> {json.dumps(val)[:80]}")
    else:
        print(f"  {name}: <{val_type}> {val_str}")

cur.close()
conn.close()
