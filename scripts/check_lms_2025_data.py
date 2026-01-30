#!/usr/bin/env python3
"""Check LMS 2025 payment data and sync status"""
import pyodbc
import psycopg2

# LMS connection
lms_conn = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\New folder\lms.mdb')
lms_cur = lms_conn.cursor()

# PostgreSQL connection
pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

print("\n" + "="*80)
print("LMS 2025 PAYMENT DATA CHECK")
print("="*80)

# Check LMS Payment table for 2025
# Note: LMS last modified Nov 8, 2025 - may not have recent 2025 data
lms_cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(IIF(Reserve_No IS NOT NULL AND Reserve_No <> '', 1, 0)) as with_reserve,
        SUM(Amount) as total_amount
    FROM Payment
""")

lms_total, lms_with_res, lms_amt = lms_cur.fetchone()
print(f"\n📊 LMS Payment Table (2025):")
print(f"   Total payments: {lms_total:,}")
print(f"   With Reserve_No: {lms_with_res:,} ({lms_with_res/lms_total*100:.1f}% if lms_total > 0 else 'N/A')")
print(f"   Total amount: ${lms_amt:,.2f}" if lms_amt else "   Total amount: $0.00")

if lms_total == 0:
    print(f"\n⚠️  LMS has NO 2025 payments - need to update LMS manually first")
    lms_conn.close()
    pg_conn.close()
    exit(0)

# Check PostgreSQL 2025 payments
pg_cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve,
        SUM(amount) as total_amount
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2025
""")

pg_total, pg_with_res, pg_amt = pg_cur.fetchone()
print(f"\n📊 PostgreSQL payments table (2025):")
print(f"   Total payments: {pg_total:,}")
print(f"   With reserve_number: {pg_with_res:,} ({pg_with_res/pg_total*100:.1f}%)")
print(f"   Total amount: ${pg_amt:,.2f}")

# Sample LMS 2025 with reserve numbers
lms_cur.execute("""
    SELECT TOP 10
        PaymentID,
        Account_No,
        Amount,
        Payment_Date,
        Reserve_No,
        [Key]
    FROM Payment
    WHERE YEAR([Payment_Date]) = 2025
    AND Reserve_No IS NOT NULL
    AND Reserve_No <> ''
    ORDER BY Payment_Date DESC
""")

print(f"\n📋 Sample LMS 2025 Payments with Reserve_No:")
print(f"{'PaymentID':<12} {'Account':<10} {'Amount':<12} {'Date':<12} {'Reserve':<10}")
print("-" * 70)
for pid, acct, amt, date, reserve, key in lms_cur.fetchall():
    print(f"{pid:<12} {acct:<10} ${amt:<11,.2f} {str(date):<12} {reserve or 'NULL':<10}")

# Check for matchable 2025 payments (by Key or Account+Amount+Date)
lms_cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(IIF(Reserve_No IS NOT NULL AND Reserve_No <> '', 1, 0)) as with_reserve
    FROM Payment lms
    WHERE YEAR([Payment_Date]) = 2025
""")

lms_2025_total, lms_2025_res = lms_cur.fetchone()

print(f"\n" + "="*80)
print("SYNC POTENTIAL")
print("="*80)
print(f"""
LMS 2025 Payments: {lms_2025_total:,}
  - With Reserve_No: {lms_2025_res:,}
  - Missing Reserve_No: {lms_2025_total - lms_2025_res:,}

PostgreSQL 2025 Payments: {pg_total:,}
  - With reserve_number: {pg_with_res:,}
  - Missing reserve_number: {pg_total - pg_with_res:,}

NEXT STEPS:
1. Update LMS manually with 2025 reserve numbers
   - Look up email sender in Outlook
   - Check calendar for confirmation
   - Enter Reserve_No into LMS Payment table

2. Run sync script to update PostgreSQL from LMS
   - Match by Account_No + Amount + Date (±3 days)
   - Or match by payment Key if available

3. Re-run banking matching after reserve numbers populated
""")

lms_conn.close()
pg_conn.close()

print("="*80)
