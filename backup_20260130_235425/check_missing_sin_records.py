import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check the 3 employees with missing SINs
missing_sins = [44, 45, 1979]

print("=" * 80)
print("CHECKING 3 EMPLOYEES WITH MISSING SINs")
print("=" * 80)

for emp_id in missing_sins:
    print(f"\n\n🔍 Employee ID: {emp_id}")
    print("-" * 80)
    
    # Get employee info
    cur.execute("""
        SELECT employee_id, full_name, name, t4_sin, created_at, updated_at
        FROM employees
        WHERE employee_id = %s
    """, (emp_id,))
    emp = cur.fetchone()
    if emp:
        print(f"Name: {emp[1]}")
        print(f"Display Name: {emp[2]}")
        print(f"SIN: {emp[3]}")
        print(f"Created: {emp[4]}")
    
    # Check T4 summary (converted from old employee_t4_records)
    cur.execute("""
        SELECT fiscal_year, t4_employment_income, t4_federal_tax, t4_cpp_contributions, t4_ei_contributions
        FROM employee_t4_summary
        WHERE employee_id = %s
        ORDER BY fiscal_year
    """, (emp_id,))
    t4_records = cur.fetchall()
    if t4_records:
        print(f"\n📄 T4 Summary Records ({len(t4_records)} years):")
        total_income = 0
        for row in t4_records:
            print(f"   {row[0]}: Income=${row[1]}, Tax=${row[2]}, CPP=${row[3]}, EI=${row[4]}")
            if row[1]:
                total_income += float(row[1])
        print(f"   TOTAL INCOME: ${total_income}")
    else:
        print("\n📄 T4 Summary Records: NONE")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
The 3 employees with missing SINs:
- Flinn, Winston (emp_id=44) - No T4 records in employee_t4_summary
- Derksen, Daryl (emp_id=45) - Need to check
- DEANS, Gordon (emp_id=1979) - Need to check

Note: The audit log showed they had 2012 T4 records, but those were from
employee_t4_records table (OLD schema). The current table is
employee_t4_summary (NEW schema). They may not have been migrated.
""")
