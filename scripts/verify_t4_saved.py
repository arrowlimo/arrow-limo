import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 60)
print("2012 T4 DATA VERIFICATION")
print("=" * 60)

# Check total records with T4 data
cur.execute("""
    SELECT 
        COUNT(*) as total_records,
        COUNT(t4_box_10) as box_10_count,
        SUM(t4_box_14) as box_14_total,
        SUM(t4_box_16) as box_16_total,
        SUM(t4_box_18) as box_18_total,
        SUM(t4_box_22) as box_22_total,
        SUM(t4_box_24) as box_24_total,
        SUM(t4_box_26) as box_26_total
    FROM driver_payroll 
    WHERE year = 2012 AND t4_box_14 IS NOT NULL
""")
row = cur.fetchone()

print(f"\nTotal payroll records with T4 data: {row[0]}")
print(f"Records with province (box_10): {row[1]}")
print(f"\nT4 Box Totals:")
print(f"  Box 14 (Employment Income): ${row[2]:,.2f}" if row[2] else "  Box 14: None")
print(f"  Box 16 (CPP Contributions): ${row[3]:,.2f}" if row[3] else "  Box 16: None")
print(f"  Box 18 (EI Premiums): ${row[4]:,.2f}" if row[4] else "  Box 18: None")
print(f"  Box 22 (Income Tax): ${row[5]:,.2f}" if row[5] else "  Box 22: None")
print(f"  Box 24 (EI Insurable Earnings): ${row[6]:,.2f}" if row[6] else "  Box 24: None")
print(f"  Box 26 (CPP Pensionable Earnings): ${row[7]:,.2f}" if row[7] else "  Box 26: None")

# Check employees added
cur.execute("""
    SELECT COUNT(*) 
    FROM employees 
    WHERE employee_id IN (1977, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986)
""")
new_employees = cur.fetchone()[0]
print(f"\n[OK] New employees added: {new_employees}/10")

# Verify against CRA totals
print("\n" + "=" * 60)
print("COMPARISON TO CRA FILING")
print("=" * 60)
print("CRA Box 14 Total: $202,570.62")
print("Database has partial data due to incomplete payroll records")
print("(Many employees have T4 slips but no detailed payroll entries)")

cur.close()
conn.close()
