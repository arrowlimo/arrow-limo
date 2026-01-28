import os
import psycopg2
import pyodbc
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    # Get LMS charges by reserve
    print("Reading LMS Charge table...")
    lms_conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\\limo\\backups\\lms.mdb;')
    lms_cur = lms_conn.cursor()
    lms_cur.execute("SELECT Reserve_No, Amount FROM Charge ORDER BY Reserve_No")
    
    lms_charges = defaultdict(float)
    total_lms_charges = 0
    for r in lms_cur.fetchall():
        reserve = str(r[0]).strip() if r[0] else ""
        amount = float(r[1] or 0)
        if reserve:
            lms_charges[reserve] += amount
            total_lms_charges += amount
    
    lms_cur.close()
    lms_conn.close()
    print(f"LMS: {len(lms_charges)} reserves with total charges ${total_lms_charges:,.2f}")

    # Get ALMS payments by reserve
    print("Reading ALMS payments...")
    alms_conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    alms_cur = alms_conn.cursor()
    
    alms_cur.execute("""
        SELECT reserve_number, SUM(amount) as total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    """)
    alms_payments = {}
    for r in alms_cur.fetchall():
        alms_payments[r[0]] = float(r[1] or 0)
    print(f"ALMS: {len(alms_payments)} reserves with payments")

    # Update charters
    print("\nUpdating charters...")
    alms_cur.execute("SELECT charter_id, reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    charters = alms_cur.fetchall()
    
    updated = 0
    for charter_id, reserve in charters:
        lms_total = lms_charges.get(reserve, 0.0)
        actual_paid = alms_payments.get(reserve, 0.0)
        calculated_balance = lms_total - actual_paid
        
        alms_cur.execute("""
            UPDATE charters
            SET total_amount_due = %s,
                paid_amount = %s,
                balance = %s
            WHERE charter_id = %s
        """, (lms_total, actual_paid, calculated_balance, charter_id))
        updated += 1
        
        if updated % 1000 == 0:
            print(f"  Updated {updated} charters...")
    
    alms_conn.commit()
    print(f"\nTotal charters updated: {updated}")
    
    # Verify
    alms_cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(total_amount_due) as total_charges,
            SUM(paid_amount) as total_paid,
            SUM(balance) as total_balance
        FROM charters
    """)
    verify = alms_cur.fetchone()
    print(f"\nVerification:")
    print(f"  Total charters: {verify[0]}")
    print(f"  Total charges: ${float(verify[1] or 0):,.2f}")
    print(f"  Total paid: ${float(verify[2] or 0):,.2f}")
    print(f"  Total balance: ${float(verify[3] or 0):,.2f}")
    
    alms_cur.close()
    alms_conn.close()
    print("\n✅ Charter charges synchronized with LMS")


if __name__ == "__main__":
    main()
