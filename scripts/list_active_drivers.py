import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*110)
print("ACTIVE DRIVERS (Booked since 2023)")
print("="*110 + "\n")

# Get active drivers with recent charter stats
cur.execute("""
    SELECT e.employee_id, e.employee_number, e.full_name, e.first_name, e.last_name,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = e.employee_id) as total_charters,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = e.employee_id AND charter_date >= '2023-01-01') as charters_2023_plus,
           (SELECT MIN(charter_date) FROM charters WHERE assigned_driver_id = e.employee_id AND charter_date >= '2023-01-01') as first_2023,
           (SELECT MAX(charter_date) FROM charters WHERE assigned_driver_id = e.employee_id AND charter_date >= '2023-01-01') as last_2023
    FROM employees e
    WHERE e.is_chauffeur = TRUE
      AND e.status = 'active'
    ORDER BY e.employee_number
""")

active_drivers = cur.fetchall()

print(f"{'ID':<6} {'Emp#':<12} {'Full Name':<30} {'Total':<8} {'2023+':<8} {'First 2023':<12} {'Last 2023':<12}")
print("-"*110)

for emp_id, emp_num, full_name, first, last, total, recent, first_date, last_date in active_drivers:
    first_str = first_date.strftime('%Y-%m-%d') if first_date else '-'
    last_str = last_date.strftime('%Y-%m-%d') if last_date else '-'
    print(f"{emp_id:<6} {emp_num or '(none)':<12} {full_name:<30} {total:<8} {recent:<8} {first_str:<12} {last_str:<12}")

print(f"\n{'='*110}")
print(f"SUMMARY: {len(active_drivers)} active drivers")
print(f"{'='*110}\n")

# Calculate total stats
cur.execute("""
    SELECT 
        SUM((SELECT COUNT(*) FROM charters WHERE assigned_driver_id = e.employee_id)) as total_all_time,
        SUM((SELECT COUNT(*) FROM charters WHERE assigned_driver_id = e.employee_id AND charter_date >= '2023-01-01')) as total_2023_plus
    FROM employees e
    WHERE e.is_chauffeur = TRUE AND e.status = 'active'
""")

total_all, total_recent = cur.fetchone()

print(f"Charter Stats for Active Drivers:")
print(f"  All-time charters: {total_all:,}")
print(f"  Charters since 2023: {total_recent:,}\n")

conn.close()
