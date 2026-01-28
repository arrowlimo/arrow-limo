import psycopg2
from datetime import datetime

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*100)
print("FINDING EMPLOYEES WITH NO CHARTER BOOKINGS SINCE 2023")
print("="*100 + "\n")

# Find employees with no charters from 2023 onwards
cur.execute("""
    SELECT e.employee_id, e.employee_number, e.full_name, e.status,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = e.employee_id) as total_charters,
           (SELECT MAX(charter_date) FROM charters WHERE assigned_driver_id = e.employee_id) as last_charter_date,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = e.employee_id AND charter_date >= '2023-01-01') as charters_since_2023
    FROM employees e
    WHERE e.is_chauffeur = TRUE
      AND e.status = 'active'
    ORDER BY e.employee_number
""")

employees = cur.fetchall()

inactive_candidates = []

for emp_id, emp_num, full_name, status, total_charters, last_charter, charters_2023 in employees:
    if charters_2023 == 0:  # No bookings since 2023
        inactive_candidates.append({
            'id': emp_id,
            'emp_num': emp_num,
            'name': full_name,
            'total': total_charters,
            'last_date': last_charter,
            'since_2023': charters_2023
        })

print(f"Found {len(inactive_candidates)} employees with no charter bookings since 2023:\n")
print(f"{'ID':<6} {'Emp#':<12} {'Full Name':<35} {'Total':<8} {'Last Charter':<15} {'2023+':<8}")
print("-"*100)

for emp in inactive_candidates:
    last_date = emp['last_date'].strftime('%Y-%m-%d') if emp['last_date'] else 'Never'
    print(f"{emp['id']:<6} {emp['emp_num'] or '(none)':<12} {emp['name']:<35} {emp['total']:<8} {last_date:<15} {emp['since_2023']:<8}")

print(f"\n{'='*100}")
print(f"SUMMARY: {len(inactive_candidates)} employees to mark as inactive")
print(f"{'='*100}\n")

response = input(f"Mark {len(inactive_candidates)} employees as inactive? (yes/no): ").strip().lower()

if response == 'yes':
    print("\n[UPDATING] Marking employees as inactive...\n")
    
    ids_to_update = [emp['id'] for emp in inactive_candidates]
    
    cur.execute("""
        UPDATE employees
        SET status = 'inactive'
        WHERE employee_id = ANY(%s)
    """, (ids_to_update,))
    
    conn.commit()
    
    updated_count = cur.rowcount
    
    print(f"✅ Marked {updated_count} employees as inactive (no bookings since 2023)\n")
    
    # Show summary
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'active') as active_count,
            COUNT(*) FILTER (WHERE status = 'inactive') as inactive_count
        FROM employees
        WHERE is_chauffeur = TRUE
    """)
    
    active, inactive = cur.fetchone()
    
    print(f"Employee Status Summary:")
    print(f"  Active drivers: {active}")
    print(f"  Inactive drivers: {inactive}")
    print(f"  Total drivers: {active + inactive}\n")
    
else:
    print("\n❌ Cancelled")

conn.close()
