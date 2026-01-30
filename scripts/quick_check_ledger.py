#!/usr/bin/env python3
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        cur.execute("""
            SELECT transaction_date, transaction_type, charge_amount, payment_amount, running_balance
            FROM rent_debt_ledger
            ORDER BY transaction_date DESC, id DESC
            LIMIT 5
        """)
        
        print("\nLast 5 rent_debt_ledger entries:")
        for row in cur.fetchall():
            print(f"  {row}")
