"""
Investigate specific balance discrepancies - checking LMS Payment records
"""
import pyodbc
import psycopg2
import os

# LMS Connection
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

# PostgreSQL Connection
pg_conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
pg_cur = pg_conn.cursor()

# Check the Callin Shaye charters
reserves = ['017822', '017823']

for reserve in reserves:
    print(f"\n{'='*80}")
    print(f"RESERVE {reserve}")
    print(f"{'='*80}")
    
    # LMS Reserve data
    lms_cur.execute("""
        SELECT Reserve_No, Name, Est_Charge, Deposit, Balance
        FROM Reserve
        WHERE Reserve_No = ?
    """, reserve)
    lms_data = lms_cur.fetchone()
    if lms_data:
        print(f"\nLMS Reserve:")
        print(f"  Name: {lms_data.Name}")
        print(f"  Est_Charge: ${lms_data.Est_Charge:,.2f}")
        print(f"  Deposit: ${lms_data.Deposit:,.2f}")
        print(f"  Balance: ${lms_data.Balance:,.2f}")
    
    # LMS Payment records
    print(f"\nLMS Payments:")
    lms_cur.execute("""
        SELECT PaymentID, Account_No, Amount, LastUpdated, LastUpdatedBy
        FROM Payment
        WHERE Reserve_No = ?
        ORDER BY LastUpdated
    """, reserve)
    lms_payments = lms_cur.fetchall()
    if lms_payments:
        total_lms_paid = 0
        for pmt in lms_payments:
            print(f"  Payment {pmt.PaymentID}: ${pmt.Amount:,.2f} on {pmt.LastUpdated} by {pmt.LastUpdatedBy}")
            total_lms_paid += pmt.Amount
        print(f"  TOTAL LMS PAYMENTS: ${total_lms_paid:,.2f}")
    else:
        print(f"  No payments found in LMS")
    
    # PostgreSQL data
    print(f"\nPostgreSQL Charter:")
    pg_cur.execute("""
        SELECT charter_id, total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    pg_data = pg_cur.fetchone()
    if pg_data:
        print(f"  Charter ID: {pg_data[0]}")
        print(f"  Total Due: ${pg_data[1]:,.2f}")
        print(f"  Paid: ${pg_data[2]:,.2f}")
        print(f"  Balance: ${pg_data[3]:,.2f}")
    
    # PostgreSQL payments
    print(f"\nPostgreSQL Payments:")
    pg_cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve,))
    pg_payments = pg_cur.fetchall()
    if pg_payments:
        total_pg_paid = 0
        for pmt in pg_payments:
            print(f"  Payment {pmt[0]}: ${pmt[1]:,.2f} on {pmt[2]} via {pmt[3]}")
            total_pg_paid += pmt[1]
        print(f"  TOTAL PG PAYMENTS: ${total_pg_paid:,.2f}")
    else:
        print(f"  No payments found in PostgreSQL")

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
