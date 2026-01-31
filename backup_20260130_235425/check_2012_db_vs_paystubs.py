#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check what 2012 payroll data is currently in the database."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT driver_id, COUNT(*), 
           SUM(gross_pay), SUM(cpp), SUM(ei), SUM(tax)
    FROM driver_payroll 
    WHERE year = 2012 
    GROUP BY driver_id 
    ORDER BY driver_id
""")

rows = cur.fetchall()
print('2012 Driver Payroll in Database:')
print(f"{'Driver':<20} {'Count':>6} {'Gross':>12} {'CPP':>10} {'EI':>10} {'Tax':>10}")
print('-' * 80)

total_gross = total_cpp = total_ei = total_tax = 0
for r in rows:
    print(f"{r[0] or '(null)':<20} {r[1]:>6} ${float(r[2] or 0):>11.2f} ${float(r[3] or 0):>9.2f} ${float(r[4] or 0):>9.2f} ${float(r[5] or 0):>9.2f}")
    total_gross += float(r[2] or 0)
    total_cpp += float(r[3] or 0)
    total_ei += float(r[4] or 0)
    total_tax += float(r[5] or 0)

print('-' * 80)
print(f"{'TOTAL':<20} {sum(r[1] for r in rows):>6} ${total_gross:>11.2f} ${total_cpp:>9.2f} ${total_ei:>9.2f} ${total_tax:>9.2f}")

print("\n\nPaustub YTD Totals (from December 2012 PDF):")
print(f"  Gross: $116,859.97")
print(f"  CPP:   $  1,844.73")
print(f"  EI:    $  1,326.62")
print(f"  Tax:   $  1,226.81")

print(f"\nDiscrepancy:")
print(f"  Gross: ${total_gross - 116859.97:,.2f}")
print(f"  CPP:   ${total_cpp - 1844.73:,.2f}")
print(f"  EI:    ${total_ei - 1326.62:,.2f}")
print(f"  Tax:   ${total_tax - 1226.81:,.2f}")

cur.close()
conn.close()
