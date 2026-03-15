#!/usr/bin/env python3
"""Execute payment cleanup - NO PROMPTS."""
import os
import psycopg2
from dotenv import load_dotenv
import json

load_dotenv()

with open('payment_cleanup_plan_20260205_153322.json', 'r') as f:
    cleanup_plan = json.load(f)

deletion_candidates = cleanup_plan['deletion_candidates']

print(f"Deleting {len(deletion_candidates):,} payments...")

conn = psycopg2.connect(
    host='localhost',
    database=os.getenv('LOCAL_DB_NAME'),
    user=os.getenv('LOCAL_DB_USER'),
    password=os.getenv('LOCAL_DB_PASSWORD')
)

cur = conn.cursor()
cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (deletion_candidates,))
deleted = cur.rowcount
conn.commit()

cur.execute("SELECT COUNT(*) FROM payments")
final_count = cur.fetchone()[0]

cur.close()
conn.close()

print(f"✅ Deleted {deleted:,} payments")
print(f"✅ Remaining: {final_count:,} payments")
