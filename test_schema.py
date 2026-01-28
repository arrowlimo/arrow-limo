#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

# Check schema
cur.execute("SELECT * FROM banking_transactions LIMIT 1")
cols = [desc[0] for desc in cur.description]
print("Columns:", cols)

cur.close()
conn.close()
