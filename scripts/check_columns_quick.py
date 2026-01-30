#!/usr/bin/env python3
import psycopg2, os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check driver_payroll columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'driver_payroll' ORDER BY ordinal_position")
print('driver_payroll columns:')
for row in cur.fetchall():
    print(f'  {row[0]}')

print()

# Check charters columns for driver reference
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'charters' AND column_name LIKE '%driver%' ORDER BY ordinal_position")
print('charters driver-related columns:')
for row in cur.fetchall():
    print(f'  {row[0]}')

cur.close()
conn.close()
