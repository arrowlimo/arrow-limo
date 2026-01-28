"""
Compare 2012 T4 data against complete almsdata export JSON.
"""
import json
import csv
from decimal import Decimal

print("=" * 80)
print("LOADING DATA")
print("=" * 80)

# Load T4 data
print("Loading T4 data from CSV...")
t4_data = {}
with open('l:/limo/data/2012_cra_t4_complete_extraction.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row['last_name'] + ', ' + row['first_name']
        t4_data[name] = {
            'box_14': Decimal(row['box_14']),
            'box_16': Decimal(row['box_16']) if row['box_16'] else Decimal('0'),
            'box_18': Decimal(row['box_18']) if row['box_18'] else Decimal('0'),
            'box_22': Decimal(row['box_22']) if row['box_22'] else Decimal('0'),
        }
print(f"[OK] Loaded {len(t4_data)} T4 records")

# Load almsdata export
print("\nLoading complete almsdata export...")
print("(This may take a moment - file is >50MB)")
with open('l:/limo/reports/complete_almsdata_export.json', encoding='utf-8') as f:
    almsdata = json.load(f)
print(f"[OK] Loaded {len(almsdata)} tables")

# Show table summary
print("\n" + "=" * 80)
print("DATABASE TABLES OVERVIEW")
print("=" * 80)
print(f"{'Table Name':<40} {'Records':>15}")
print("-" * 80)
for table, records in sorted(almsdata.items()):
    print(f"{table:<40} {len(records):>15,}")

# Analyze driver_payroll table
print("\n" + "=" * 80)
print("DRIVER_PAYROLL 2012 ANALYSIS")
print("=" * 80)

payroll_2012 = [r for r in almsdata['driver_payroll'] if r.get('year') == 2012]
print(f"Total 2012 payroll records: {len(payroll_2012)}")

# Group by employee
from collections import defaultdict
by_employee = defaultdict(lambda: {
    'records': 0,
    'gross_pay': Decimal('0'),
    'base_wages': Decimal('0'),
    'hours_worked': Decimal('0'),
    'gratuity': Decimal('0'),
    'expenses': Decimal('0'),
    't4_box_14': None,
})

for record in payroll_2012:
    emp_id = record.get('employee_id')
    if not emp_id:
        continue
    
    by_employee[emp_id]['records'] += 1
    by_employee[emp_id]['gross_pay'] += Decimal(str(record.get('gross_pay') or 0))
    by_employee[emp_id]['base_wages'] += Decimal(str(record.get('base_wages') or 0))
    by_employee[emp_id]['hours_worked'] += Decimal(str(record.get('hours_worked') or 0))
    by_employee[emp_id]['gratuity'] += Decimal(str(record.get('gratuity_amount') or 0))
    by_employee[emp_id]['expenses'] += Decimal(str(record.get('expenses') or 0))
    
    if record.get('t4_box_14'):
        by_employee[emp_id]['t4_box_14'] = Decimal(str(record['t4_box_14']))

print(f"Employees with payroll: {len(by_employee)}")

# Get employee names
employees = {e['employee_id']: e['full_name'] for e in almsdata['employees']}

# Compare with T4 data
print("\n" + "=" * 80)
print("T4 VS DATABASE COMPARISON")
print("=" * 80)
print(f"{'Employee':<25} {'T4 Box14':>12} {'DB Base':>12} {'DB Expenses':>12} {'Gap':>12} {'Hours':>8}")
print("-" * 80)

total_t4 = Decimal('0')
total_db_base = Decimal('0')
total_db_expenses = Decimal('0')
total_gap = Decimal('0')

matched = 0
for emp_id, payroll in sorted(by_employee.items(), key=lambda x: x[1]['t4_box_14'] or 0, reverse=True):
    emp_name = employees.get(emp_id, 'UNKNOWN')
    t4_box_14 = payroll['t4_box_14'] or Decimal('0')
    base_wages = payroll['base_wages']
    expenses = payroll['expenses']
    hours = payroll['hours_worked']
    
    if t4_box_14 > 0:
        gap = t4_box_14 - base_wages
        total_t4 += t4_box_14
        total_db_base += base_wages
        total_db_expenses += expenses
        total_gap += gap
        matched += 1
        
        print(f"{emp_name[:24]:<25} ${t4_box_14:>10,.2f} ${base_wages:>10,.2f} "
              f"${expenses:>10,.2f} ${gap:>10,.2f} {hours:>7.1f}")

print("-" * 80)
print(f"{'TOTALS':<25} ${total_t4:>10,.2f} ${total_db_base:>10,.2f} "
      f"${total_db_expenses:>10,.2f} ${total_gap:>10,.2f}")
print(f"\nMatched employees with T4 data: {matched}")

# Analyze expenses field
print("\n" + "=" * 80)
print("EXPENSES FIELD ANALYSIS")
print("=" * 80)
print(f"Total expenses in database: ${total_db_expenses:,.2f}")
print(f"Total base_wages: ${total_db_base:,.2f}")
print(f"Expenses / Base ratio: {(total_db_expenses / total_db_base * 100) if total_db_base else 0:.1f}%")
print("\nHypothesis: If expenses contains actual wages, then:")
print(f"  Base + Expenses = ${total_db_base + total_db_expenses:,.2f}")
print(f"  T4 Box 14 Total = ${total_t4:,.2f}")
print(f"  New Gap = ${total_t4 - (total_db_base + total_db_expenses):,.2f}")

# Check charters table
print("\n" + "=" * 80)
print("CHARTERS 2012 ANALYSIS")
print("=" * 80)

charters_2012 = [c for c in almsdata['charters'] 
                 if c.get('charter_date') and '2012' in str(c['charter_date'])]
print(f"Total 2012 charters: {len(charters_2012):,}")

with_driver = sum(1 for c in charters_2012 if c.get('assigned_driver_id'))
with_hours = sum(1 for c in charters_2012 if c.get('calculated_hours'))
total_hours = sum(Decimal(str(c.get('calculated_hours') or 0)) for c in charters_2012)

print(f"With assigned_driver_id: {with_driver:,} ({with_driver/len(charters_2012)*100:.1f}%)")
print(f"With calculated_hours: {with_hours:,} ({with_hours/len(charters_2012)*100:.1f}%)")
print(f"Total charter hours: {total_hours:,.1f}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"T4 Box 14 Total: ${total_t4:,.2f}")
print(f"Database base_wages: ${total_db_base:,.2f} ({total_db_base/total_t4*100:.1f}% of T4)")
print(f"Database expenses: ${total_db_expenses:,.2f} ({total_db_expenses/total_t4*100:.1f}% of T4)")
print(f"Missing from T4: ${total_gap:,.2f} ({total_gap/total_t4*100:.1f}%)")
print(f"\nCharter hours available: {total_hours:,.1f}")
print(f"Payroll hours recorded: {sum(p['hours_worked'] for p in by_employee.values()):,.1f}")
