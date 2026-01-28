import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("="*70)
print("DOUG REDMOND - AUGUST 2012 COMPARISON")
print("="*70)

# Check for Doug Redmond in August 2012
cur.execute("""
    SELECT id, driver_id, month, gross_pay, cpp, ei, tax, net_pay, source
    FROM driver_payroll
    WHERE year = 2012 AND month = 8 
    AND driver_id IN ('Dr_Doug', 'Doug', 'Dr_Redmond')
""")

rows = cur.fetchall()

print("\nDatabase (Doug Redmond August 2012):")
if rows:
    for row in rows:
        print(f"  ID {row[0]}: {row[1]}")
        print(f"    Gross:  ${row[3]:>10.2f}")
        print(f"    CPP:    ${row[4]:>10.2f}")
        print(f"    EI:     ${row[5]:>10.2f}")
        print(f"    Tax:    ${row[6]:>10.2f}")
        print(f"    Net:    ${row[7]:>10.2f}")
        print(f"    Source: {row[8]}")
else:
    print("  [FAIL] No entry found for Doug Redmond in August 2012")

print("\nPay Stub Screenshot (Doug Redmond August 2012):")
print(f"  Gross:  $  2,999.62")
print(f"  CPP:    $    134.04")
print(f"  EI:     $     54.89")
print(f"  Tax:    $    409.69")
print(f"  Net:    $  2,401.00")

print("\n" + "="*70)
print("CHECKING ALL DECEMBER 2012 IMPORTS")
print("="*70)

# Check if we imported December 2012 employees (which included Doug)
cur.execute("""
    SELECT driver_id, COUNT(*), SUM(gross_pay)
    FROM driver_payroll
    WHERE year = 2012 AND month = 12
    GROUP BY driver_id
    ORDER BY driver_id
""")

print("\nDecember 2012 entries:")
dec_rows = cur.fetchall()
for row in dec_rows:
    print(f"  {row[0]:15} : {row[1]} entries, ${row[2]:>10.2f}")

# Check if Dr_Doug exists at all in 2012
cur.execute("""
    SELECT month, gross_pay, cpp, ei, tax
    FROM driver_payroll
    WHERE year = 2012 AND driver_id = 'Dr_Doug'
    ORDER BY month
""")

doug_all = cur.fetchall()
if doug_all:
    print("\nDr_Doug all 2012 entries:")
    for row in doug_all:
        print(f"  Month {row[0]:2}: Gross ${row[1]:>10.2f}, CPP ${row[2]:>8.2f}, EI ${row[3]:>8.2f}, Tax ${row[4]:>8.2f}")
else:
    print("\n[FAIL] Dr_Doug has no entries in 2012")

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

if not rows:
    print("\n[WARN]  Doug Redmond's August 2012 pay stub NOT in database")
    print("   Screenshot shows: $2,999.62 gross pay")
    print("   This is part of the missing $8,696.46 for August")
    
if doug_all and any(m[0] == 12 for m in doug_all):
    print("\n[OK] Doug Redmond's December 2012 entry exists")
    print("   But August 2012 is missing - indicates incomplete import")

print("\n📋 Need to parse and import:")
print("   1. August.2012-Paul Pay Cheque_ocred (1).pdf")
print("   2. Individual pay stubs for all August 2012 employees")
print("   3. Monthly payroll summaries for Jan-Nov 2012")

cur.close()
conn.close()
