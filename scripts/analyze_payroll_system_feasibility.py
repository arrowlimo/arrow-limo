#!/usr/bin/env python
"""Analyze existing payroll/employee system and feasibility of pay period reconstruction.
Check:
1. Existing employee/payroll tables
2. Charter dispatcher hours availability
3. T4 data history
4. Payment records by employee
5. Feasibility of backward reconstruction
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("EMPLOYEE PAY SYSTEM ANALYSIS & FEASIBILITY STUDY")
print("="*100)
print()

# 1. Check for existing payroll tables
print("1. EXISTING PAYROLL/EMPLOYEE TABLES")
print("-" * 100)
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='public'
      AND (table_name LIKE '%employee%' OR table_name LIKE '%pay%' OR table_name LIKE '%payroll%' 
           OR table_name LIKE '%wage%' OR table_name LIKE '%t4%' OR table_name LIKE '%tax%'
           OR table_name LIKE '%deduction%' OR table_name LIKE '%gratuity%')
    ORDER BY table_name
""")
payroll_tables = [row[0] for row in cur.fetchall()]

if payroll_tables:
    print(f"Found {len(payroll_tables)} payroll-related tables:")
    for tbl in payroll_tables:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        cnt = cur.fetchone()[0]
        print(f"  - {tbl}: {cnt:,} rows")
else:
    print("❌ No dedicated payroll tables found")

# 2. Check employee table
print("\n2. EMPLOYEES TABLE STRUCTURE")
print("-" * 100)
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='employees'
    ORDER BY ordinal_position
""")
emp_cols = cur.fetchall()
if emp_cols:
    print(f"Employees table has {len(emp_cols)} columns:")
    for col, dtype in emp_cols:
        print(f"  - {col}: {dtype}")
    
    # Get employee count by type
    cur.execute("""
        SELECT COUNT(*), COUNT(DISTINCT CASE WHEN is_chauffeur=true THEN employee_id END),
               COUNT(DISTINCT CASE WHEN employee_category='owner' THEN employee_id END)
        FROM employees
    """)
    total, drivers, owners = cur.fetchone()
    print(f"\n  Employees: {total:,} total (Drivers: {drivers}, Owners: {owners})")
else:
    print("❌ Employees table not found")

# 3. Check charter structure for dispatcher hours
print("\n3. CHARTERS TABLE - DISPATCHER HOURS FIELD")
print("-" * 100)
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='charters'
      AND (column_name LIKE '%hour%' OR column_name LIKE '%dispatch%' OR column_name LIKE '%driver%')
    ORDER BY ordinal_position
""")
hour_cols = cur.fetchall()
if hour_cols:
    print(f"Found {len(hour_cols)} hour/dispatch related columns:")
    for col, dtype in hour_cols:
        cur.execute(f"SELECT COUNT(DISTINCT CASE WHEN {col} IS NOT NULL THEN 1 END) FROM charters")
        cnt = cur.fetchone()[0]
        print(f"  - {col} ({dtype}): {cnt:,} non-null values")
else:
    print("❌ No dispatcher hours field found")

# 4. Check for T4 data
print("\n4. T4 DATA AVAILABILITY")
print("-" * 100)
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='public' AND table_name LIKE '%t4%'
""")
t4_tables = [row[0] for row in cur.fetchall()]
if t4_tables:
    print(f"Found {len(t4_tables)} T4-related tables:")
    for tbl in t4_tables:
        cur.execute(f"SELECT COUNT(*), MIN(CASE WHEN year IS NOT NULL THEN year END), MAX(CASE WHEN year IS NOT NULL THEN year END) FROM {tbl}")
        cnt, min_yr, max_yr = cur.fetchone()
        print(f"  - {tbl}: {cnt:,} rows (Years: {min_yr} - {max_yr})")
else:
    print("❌ No T4 tables found")

# 5. Check payment records by employee
print("\n5. PAYMENT RECORDS BY EMPLOYEE/DRIVER")
print("-" * 100)
cur.execute("""
    SELECT COUNT(*)
    FROM payments
    WHERE employee_id IS NOT NULL
""")
emp_payment_count = cur.fetchone()[0]
cur.execute("""
    SELECT COUNT(*)
    FROM payments
""")
total_payments = cur.fetchone()[0]
pct = 100 * emp_payment_count / total_payments if total_payments > 0 else 0
print(f"Payment records with employee_id: {emp_payment_count:,}/{total_payments:,} ({pct:.1f}%)")

# Check for gratuity payments
cur.execute("""
    SELECT COUNT(*)
    FROM payments
    WHERE payment_method LIKE '%gratuity%' OR description LIKE '%gratuity%'
""")
gratuity_count = cur.fetchone()[0]
print(f"Gratuity payments: {gratuity_count:,}")

# Check for reimbursement payments
cur.execute("""
    SELECT COUNT(*)
    FROM payments
    WHERE payment_method LIKE '%reimburse%' OR description LIKE '%reimburse%'
""")
reimburse_count = cur.fetchone()[0]
print(f"Reimbursement payments: {reimburse_count:,}")

# 6. Check for pay period data
print("\n6. PAY PERIOD/FREQUENCY DATA")
print("-" * 100)
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM payment_date)::int as yr,
        COUNT(*) as total_payments,
        COUNT(DISTINCT employee_id) as employees_paid,
        MIN(payment_date) as first_payment,
        MAX(payment_date) as last_payment,
        ROUND(AVG(amount), 2) as avg_payment
    FROM payments
    WHERE employee_id IS NOT NULL
    GROUP BY yr
    ORDER BY yr
""")
pay_history = cur.fetchall()
if pay_history:
    print("\nPayment history by year:")
    print("Year | Payments | Employees | First Date | Last Date | Avg Payment")
    print("-" * 100)
    for yr, cnt, emp_cnt, first, last, avg in pay_history:
        if first and last:
            days = (last - first).days
            print(f"{yr} | {cnt:>8,} | {emp_cnt:>9,} | {first} | {last} | ${avg:>9,.2f} ({days} days)")

# 7. Check for T4 income data
print("\n7. T4 INCOME HISTORY")
print("-" * 100)
cur.execute("""
    SELECT * FROM information_schema.tables
    WHERE table_name='employees_t4_history'
""")
if cur.fetchone():
    cur.execute("""
        SELECT year, COUNT(*), SUM(total_income), SUM(income_tax)
        FROM employees_t4_history
        GROUP BY year
        ORDER BY year
    """)
    for yr, cnt, income, tax in cur.fetchall():
        print(f"{yr}: {cnt} employees | Total income: ${income:,.2f} | Tax: ${tax:,.2f}")
else:
    print("❌ No T4 history table found")
    
    # Try to find T4 data elsewhere
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
          AND (table_name LIKE '%t4%' OR table_name LIKE '%tax%' OR table_name LIKE '%revenue%')
    """)
    related_tables = [row[0] for row in cur.fetchall()]
    if related_tables:
        print(f"Related tables: {', '.join(related_tables)}")

# 8. Check charter/driver relationship
print("\n8. CHARTER-TO-DRIVER RELATIONSHIP")
print("-" * 100)
cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE driver_id IS NOT NULL
""")
driver_charters = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM charters")
total_charters = cur.fetchone()[0]
pct = 100 * driver_charters / total_charters if total_charters > 0 else 0
print(f"Charters with driver_id: {driver_charters:,}/{total_charters:,} ({pct:.1f}%)")

# Check if charters have hourly/time data
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name='charters'
      AND column_name SIMILAR TO '%(hour|time|duration|minute)%'
""")
time_cols = [row[0] for row in cur.fetchall()]
if time_cols:
    print(f"Time-related columns: {', '.join(time_cols)}")
else:
    print("❌ No hour/duration columns in charters")

# 9. Summarize feasibility
print("\n" + "="*100)
print("FEASIBILITY ASSESSMENT: PAY PERIOD RECONSTRUCTION")
print("="*100)
print()

# Check data availability
has_employees = len(emp_cols) > 0
has_charters_hours = len(hour_cols) > 0
has_t4_data = len(t4_tables) > 0
has_payment_history = emp_payment_count > 0
has_charter_driver_link = driver_charters > 0

print("DATA AVAILABILITY CHECKLIST:")
print(f"  {'✅' if has_employees else '❌'} Employee master table")
print(f"  {'✅' if has_charter_driver_link else '❌'} Charter-to-driver relationship")
print(f"  {'✅' if has_charters_hours else '❌'} Charter dispatcher/scheduled hours")
print(f"  {'✅' if has_payment_history else '❌'} Historical payment records by employee")
print(f"  {'✅' if has_t4_data else '❌'} T4/tax data for audit trail")
print()

feasibility = sum([has_employees, has_charters_hours, has_t4_data, has_payment_history, has_charter_driver_link])
print(f"FEASIBILITY SCORE: {feasibility}/5")
print()

if feasibility >= 4:
    print("✅ HIGHLY FEASIBLE - Proceed with pay period reconstruction system")
    print()
    print("RECOMMENDED APPROACH:")
    print("  1. Build employee_pay_periods table (week/month boundaries)")
    print("  2. Create pay_period_allocations (charter hours + manual adjustments)")
    print("  3. Build employee_pay_calc view (hours × rate + deductions + gratuity)")
    print("  4. T4 reconciliation (match calculated vs. actual tax)")
    print("  5. Audit trail (source data for each component)")
    print()
    print("RECONSTRUCTION STRATEGY:")
    print("  Phase 1: T4 anchors (known totals for each employee/year)")
    print("  Phase 2: Charter hours (sum by employee/period)")
    print("  Phase 3: Fill gaps (back-calculate missing periods)")
    print("  Phase 4: Gratuity/float/reimbursement allocation")
    print("  Phase 5: Validate against actual payments")
elif feasibility >= 3:
    print("⚠️ PARTIALLY FEASIBLE - Some work required to bridge gaps")
    print()
    print("GAPS TO FILL:")
    if not has_employees:
        print("  ❌ Build employee table (if missing)")
    if not has_charter_driver_link:
        print("  ❌ Link charters to drivers/employees")
    if not has_charters_hours:
        print("  ❌ Add dispatcher hours field to charters")
    if not has_t4_data:
        print("  ❌ Import T4 historical data")
else:
    print("❌ LIMITED FEASIBILITY - Need significant data gathering first")

cur.close()
conn.close()
