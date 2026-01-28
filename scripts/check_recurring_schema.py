#!/usr/bin/env python3
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'recurring_invoices'
            ORDER BY ordinal_position
        """)
        print("\nrecurring_invoices columns:")
        for col in cur.fetchall():
            print(f"  {col[0]}")
