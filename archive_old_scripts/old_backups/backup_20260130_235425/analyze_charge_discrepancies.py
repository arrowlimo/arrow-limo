"""
Analyze charter_charges vs total_amount_due discrepancies
Focus on understanding why 8804 charters have mismatched totals
"""
import psycopg2
import os
import pyodbc

# PostgreSQL
pg_conn = psycopg2.connect(
    host='localhost', database='almsdata',
    user='postgres', password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

# LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("=" * 120)
print("CHARTER CHARGES VS TOTAL_AMOUNT_DUE ANALYSIS")
print("=" * 120)
print()

# Get statistics
pg_cur.execute("""
    WITH charge_analysis AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            COUNT(cc.charge_id) as charge_count,
            COALESCE(SUM(cc.amount), 0) as charges_sum,
            c.total_amount_due - COALESCE(SUM(cc.amount), 0) as difference
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    )
    SELECT 
        COUNT(*) as total_charters,
        SUM(CASE WHEN ABS(difference) > 0.02 THEN 1 ELSE 0 END) as mismatched,
        SUM(CASE WHEN charge_count = 0 THEN 1 ELSE 0 END) as no_charges,
        SUM(CASE WHEN charge_count = 1 THEN 1 ELSE 0 END) as single_charge,
        SUM(CASE WHEN charge_count > 1 THEN 1 ELSE 0 END) as multi_charge
    FROM charge_analysis
""")
stats = pg_cur.fetchone()

print(f"Total charters: {stats[0]}")
print(f"Mismatched totals: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
print(f"Charters with NO charges: {stats[2]}")
print(f"Charters with 1 charge: {stats[3]}")
print(f"Charters with multiple charges: {stats[4]}")
print()

# Check a few specific examples
print("=" * 120)
print("SAMPLE ANALYSIS - Comparing to LMS Est_Charge")
print("=" * 120)
print()

# Get top 5 discrepancies
pg_cur.execute("""
    WITH charge_analysis AS (
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            COUNT(cc.charge_id) as charge_count,
            COALESCE(SUM(cc.amount), 0) as charges_sum,
            ABS(c.total_amount_due - COALESCE(SUM(cc.amount), 0)) as abs_diff
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
        GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    )
    SELECT reserve_number, total_amount_due, charge_count, charges_sum
    FROM charge_analysis
    WHERE abs_diff > 0.02
    ORDER BY abs_diff DESC
    LIMIT 5
""")
samples = pg_cur.fetchall()

for reserve, pg_total, charge_count, charges_sum in samples:
    print(f"\nReserve {reserve}:")
    print(f"  PostgreSQL total_amount_due: ${pg_total:,.2f}")
    print(f"  PostgreSQL charge count: {charge_count}")
    print(f"  PostgreSQL charges SUM: ${charges_sum:,.2f}")
    
    # Get LMS Est_Charge
    lms_cur.execute("SELECT Est_Charge, Rate FROM Reserve WHERE Reserve_No = ?", reserve)
    lms_data = lms_cur.fetchone()
    if lms_data:
        print(f"  LMS Est_Charge: ${lms_data.Est_Charge:,.2f}")
        print(f"  LMS Rate: ${lms_data.Rate:,.2f}")
        
        # Compare
        if abs(pg_total - lms_data.Est_Charge) < 0.02:
            print(f"  ✅ PostgreSQL total_amount_due MATCHES LMS Est_Charge")
        else:
            print(f"  ⚠️  PostgreSQL total_amount_due DIFFERS from LMS Est_Charge by ${pg_total - lms_data.Est_Charge:,.2f}")
        
        if abs(charges_sum - lms_data.Est_Charge) < 0.02:
            print(f"  ✅ charter_charges SUM MATCHES LMS Est_Charge")
        else:
            print(f"  ⚠️  charter_charges SUM DIFFERS from LMS Est_Charge by ${charges_sum - lms_data.Est_Charge:,.2f}")

print()
print("=" * 120)
print("PATTERN ANALYSIS")
print("=" * 120)
print()

# Check which field is more accurate - total_amount_due or charter_charges sum
pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters c
    WHERE c.total_amount_due = 0 
      AND EXISTS (SELECT 1 FROM charter_charges cc WHERE cc.charter_id = c.charter_id)
""")
zero_total_with_charges = pg_cur.fetchone()[0]

print(f"Charters with total_amount_due=$0 but HAVE charges: {zero_total_with_charges}")

pg_cur.execute("""
    SELECT COUNT(*)
    FROM charters c
    WHERE c.total_amount_due > 0
      AND NOT EXISTS (SELECT 1 FROM charter_charges cc WHERE cc.charter_id = c.charter_id)
""")
total_without_charges = pg_cur.fetchone()[0]

print(f"Charters with total_amount_due>$0 but NO charges: {total_without_charges}")
print()

# Check if charges are itemized breakdowns or duplicates
print("Sample charter with multiple charges:")
pg_cur.execute("""
    SELECT c.reserve_number, c.total_amount_due,
           ARRAY_AGG(cc.description) as descriptions,
           ARRAY_AGG(cc.amount) as amounts
    FROM charters c
    JOIN charter_charges cc ON cc.charter_id = c.charter_id
    WHERE c.reserve_number IS NOT NULL
    GROUP BY c.charter_id, c.reserve_number, c.total_amount_due
    HAVING COUNT(cc.charge_id) > 1
    LIMIT 3
""")
multi = pg_cur.fetchall()

for reserve, total, descs, amts in multi:
    print(f"\n  Reserve {reserve} - Total: ${total:,.2f}")
    for desc, amt in zip(descs, amts):
        print(f"    {desc}: ${amt:,.2f}")
    print(f"    Charges SUM: ${sum(amts):,.2f}")

print()

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
