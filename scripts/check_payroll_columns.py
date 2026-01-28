#!/usr/bin/env python3
import os, psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='driver_payroll' 
    ORDER BY ordinal_position
""")

print("\ndriver_payroll table columns:\n")
for col in cur.fetchall():
    print(f"{col[0]:<30} {col[1]}")

# Check for gratuity/hours related columns
gratuity_cols = ['gratuity', 'tip', 'tips', 'driver_gratuity', 'gratuities']
hours_cols = ['hours', 'hours_worked', 'driver_hours']
wage_cols = ['wages', 'base_pay', 'hourly_pay']

print("\n\nRelevant columns for pay breakdown:")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='driver_payroll' 
    ORDER BY ordinal_position
""")

all_cols = [row[0].lower() for row in cur.fetchall()]

print("\nGratuity-related:")
found_grat = [c for c in all_cols if any(g in c for g in gratuity_cols)]
print(f"  {found_grat if found_grat else 'None found'}")

print("\nHours-related:")
found_hours = [c for c in all_cols if any(h in c for h in hours_cols)]
print(f"  {found_hours if found_hours else 'None found'}")

print("\nWages-related:")
found_wages = [c for c in all_cols if any(w in c for w in wage_cols)]
print(f"  {found_wages if found_wages else 'None found'}")

print("\nExpense-related:")
found_expense = [c for c in all_cols if 'expense' in c or 'reimburse' in c]
print(f"  {found_expense if found_expense else 'None found'}")

cur.close()
conn.close()
