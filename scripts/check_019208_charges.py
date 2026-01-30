"""
Check reserve 019208 charges in both LMS and PostgreSQL.
User adjusted charges and gratuity in LMS to match payments.
"""

import pyodbc
import psycopg2

LMS_PATH = r'L:\limo\backups\lms.mdb'

def check_charges():
    # Connect to LMS
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***',
        host='localhost'
    )
    pg_cur = pg_conn.cursor()
    
    reserve = '019208'
    
    print("=" * 100)
    print("LMS RESERVE DATA")
    print("=" * 100)
    lms_cur.execute("""
        SELECT Reserve_No, Name, Rate, Balance, Deposit, Est_Charge, 
               PU_Date, Status
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve,))
    
    row = lms_cur.fetchone()
    if row:
        print(f"Reserve: {row[0]}")
        print(f"  Client: {row[1]}")
        print(f"  Rate: ${row[2] or 0:,.2f}")
        print(f"  Balance: ${row[3] or 0:,.2f}")
        print(f"  Deposit: ${row[4] or 0:,.2f}")
        print(f"  Est_Charge: ${row[5] or 0:,.2f}")
        print(f"  Date: {row[6]}")
        print(f"  Status: {row[7] or 'NULL'}")
    
    print("\n" + "=" * 100)
    print("LMS CHARGES (from Charges table)")
    print("=" * 100)
    lms_cur.execute("""
        SELECT Description, Type, Rate, Amount
        FROM Charges
        WHERE [Rid #] = ?
        ORDER BY Type
    """, (reserve,))
    
    lms_charges = lms_cur.fetchall()
    lms_total = 0
    if lms_charges:
        for c in lms_charges:
            print(f"  {c[0]:<30} Type: {c[1]:<10} Rate: ${c[2] or 0:>8.2f}  Amount: ${c[3] or 0:>8.2f}")
            lms_total += (c[3] or 0)
        print(f"  {'TOTAL':<30} {'':>22} ${lms_total:>8.2f}")
    else:
        print("  No charges found in LMS Charges table")
    
    print("\n" + "=" * 100)
    print("LMS PAYMENTS")
    print("=" * 100)
    lms_cur.execute("""
        SELECT Amount, [Key], LastUpdated
        FROM Payment
        WHERE Reserve_No = ?
        ORDER BY LastUpdated
    """, (reserve,))
    
    lms_payments = lms_cur.fetchall()
    lms_paid = 0
    if lms_payments:
        for p in lms_payments:
            print(f"  ${p[0] or 0:>8.2f}  Key: {p[1]}  Date: {p[2]}")
            lms_paid += (p[0] or 0)
        print(f"  {'TOTAL PAID':<30} ${lms_paid:>8.2f}")
    else:
        print("  No payments found")
    
    print("\n" + "=" * 100)
    print("POSTGRESQL CHARTER DATA")
    print("=" * 100)
    pg_cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    pg_row = pg_cur.fetchone()
    if pg_row:
        print(f"Reserve: {pg_row[0]}")
        print(f"  Total Due: ${pg_row[1]:,.2f}")
        print(f"  Paid Amount: ${pg_row[2]:,.2f}")
        print(f"  Balance: ${pg_row[3]:,.2f}")
        print(f"  Status: {pg_row[4] or 'NULL'}")
    
    print("\n" + "=" * 100)
    print("POSTGRESQL CHARTER_CHARGES")
    print("=" * 100)
    pg_cur.execute("""
        SELECT description, amount, charge_type
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY charge_type
    """, (reserve,))
    
    pg_charges = pg_cur.fetchall()
    pg_total = 0
    if pg_charges:
        for c in pg_charges:
            print(f"  {c[0]:<30} Type: {c[2] or 'NULL':<10} Amount: ${c[1]:>8.2f}")
            pg_total += c[1]
        print(f"  {'TOTAL':<30} {'':>22} ${pg_total:>8.2f}")
    else:
        print("  No charges found")
    
    print("\n" + "=" * 100)
    print("POSTGRESQL PAYMENTS")
    print("=" * 100)
    pg_cur.execute("""
        SELECT amount, payment_key, payment_date
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve,))
    
    pg_payments = pg_cur.fetchall()
    pg_paid = 0
    if pg_payments:
        for p in pg_payments:
            print(f"  ${p[0]:>8.2f}  Key: {p[1]}  Date: {p[2]}")
            pg_paid += p[0]
        print(f"  {'TOTAL PAID':<30} ${pg_paid:>8.2f}")
    else:
        print("  No payments found")
    
    print("\n" + "=" * 100)
    print("COMPARISON SUMMARY")
    print("=" * 100)
    print(f"LMS Est_Charge: ${row[5] or 0:,.2f}")
    print(f"LMS Charges Total: ${lms_total:,.2f}")
    print(f"LMS Payments Total: ${lms_paid:,.2f}")
    print(f"LMS Balance: ${row[3] or 0:,.2f}")
    print()
    print(f"PostgreSQL Total Due: ${pg_row[1]:,.2f}")
    print(f"PostgreSQL Charges Total: ${pg_total:,.2f}")
    print(f"PostgreSQL Paid Amount: ${pg_row[2]:,.2f}")
    print(f"PostgreSQL Balance: ${pg_row[3]:,.2f}")
    print()
    if abs(lms_total - pg_total) > 0.01:
        print(f"⚠️  CHARGES MISMATCH: LMS ${lms_total:,.2f} vs PostgreSQL ${pg_total:,.2f}")
    else:
        print("✓ Charges match")
    
    if abs(lms_paid - pg_paid) > 0.01:
        print(f"⚠️  PAYMENTS MISMATCH: LMS ${lms_paid:,.2f} vs PostgreSQL ${pg_paid:,.2f}")
    else:
        print("✓ Payments match")
    
    lms_cur.close()
    lms_conn.close()
    pg_cur.close()
    pg_conn.close()

if __name__ == '__main__':
    check_charges()
