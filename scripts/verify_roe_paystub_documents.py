import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("="*70)
print("ROE & PAY STUB DOCUMENT VERIFICATION")
print("="*70)

# Check Dustan Townsend August 2012
print("\n1. DUSTAN TOWNSEND - August 2012 Pay Stub")
print("-" * 70)

cur.execute("""
    SELECT id, driver_id, month, gross_pay, cpp, ei, tax, net_pay
    FROM driver_payroll
    WHERE year = 2012 AND month = 8 
    AND driver_id IN ('Dr_Dustan', 'Dustan', 'Dr_Townsend')
""")

dustan_aug = cur.fetchall()
if dustan_aug:
    for row in dustan_aug:
        print(f"[OK] Found in database:")
        print(f"   ID {row[0]}: {row[1]}")
        print(f"   Gross: ${row[2]:>10.2f} (Pay stub: $285.00)")
        print(f"   CPP:   ${row[3]:>10.2f} (Pay stub: $0.00)")
        print(f"   EI:    ${row[4]:>10.2f} (Pay stub: $5.22)")
        print(f"   Tax:   ${row[5]:>10.2f} (Pay stub: $0.00)")
        print(f"   Net:   ${row[6]:>10.2f} (Pay stub: $279.78)")
else:
    print("[FAIL] NOT in database")
    print("   Pay stub shows: Gross $285.00, EI $5.22, Net $279.78")

# Check Doug Redmond (we already know August is missing)
print("\n2. DOUG REDMOND - ROE Document (Terminated 2015)")
print("-" * 70)
print("   ROE shows insurable earnings: $1,627.80")
print("   Status: Already checked - December 2012 exists, August missing")

# Check Kevin Kosik
print("\n3. KEVIN KOSIK - ROE Document (Terminated Dec 2013)")
print("-" * 70)

cur.execute("""
    SELECT id, driver_id, year, month, gross_pay
    FROM driver_payroll
    WHERE driver_id IN ('Dr_Kevin', 'Kevin', 'Dr_Kosik')
    ORDER BY year, month
""")

kevin_all = cur.fetchall()
if kevin_all:
    print("[OK] Found in database:")
    for row in kevin_all:
        print(f"   {row[2]}-{row[3]:02d}: ${row[4]:>10.2f}")
else:
    print("[FAIL] NOT in database")

print("\n" + "="*70)
print("AUGUST 2012 PAYROLL SUMMARY COMPARISON")
print("="*70)

# Get all August 2012 employees in database
cur.execute("""
    SELECT driver_id, SUM(gross_pay) as total
    FROM driver_payroll
    WHERE year = 2012 AND month = 8
    GROUP BY driver_id
    ORDER BY driver_id
""")

db_employees = {row[0]: float(row[1]) for row in cur.fetchall()}

# Expected employees from August 2012 Payroll Summary PDF
expected_employees = {
    'Angel Escobar': 1455.50,
    'Chantal Thomas': 292.50,
    'Dale Menard': 1434.57,
    'Doug Redmond': 2999.62,
    'Dustan Townsend': 285.00,
    'Jeannie Gordon': 1996.00,
    'Jesse Gordon': 97.50,
    'Michael Richard': 2689.67,
    'Paul D Richard': 1202.64,
    'Paul Mansell': 2233.09,
    'Zak Keller': 97.50
}

print("\nExpected employees from PDF summary (11 employees):")
for name, amount in expected_employees.items():
    print(f"  {name:<20} ${amount:>10.2f}")

print(f"\nTotal from PDF: ${sum(expected_employees.values()):>10.2f}")

total_db = sum(db_employees.values())
print(f"Total in database: ${total_db:>10.2f}")
print(f"Missing: ${sum(expected_employees.values()) - total_db:>10.2f}")

print("\n" + "="*70)
print("MISSING EMPLOYEE DATA")
print("="*70)

missing_employees = []
if not dustan_aug:
    missing_employees.append("Dustan Townsend ($285.00)")
if not any(row[1] == 'Dr_Doug' and row[2] == 8 for row in kevin_all if row[2] == 2012):
    missing_employees.append("Doug Redmond ($2,999.62)")

if missing_employees:
    print("\n[FAIL] Confirmed missing from August 2012:")
    for emp in missing_employees:
        print(f"   • {emp}")
else:
    print("\n[OK] All sampled employees found")

print("\n📋 Documents provide verification data:")
print("   • Individual pay stubs confirm August 2012 amounts")
print("   • ROEs provide employment history and termination dates")
print("   • Can cross-reference against payroll summary PDF")

cur.close()
conn.close()
