"""
Check Account 01668 (Gordon, Dean) for payment history and charter details.
"""
import pyodbc
import psycopg2

LMS_PATH = r'L:\New folder\lms.mdb'

def check_lms_account():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    account = '01668'
    
    print("=" * 80)
    print(f"LMS ACCOUNT {account} - Gordon, Dean")
    print("=" * 80)
    
    # Get all reserves for this account
    cur.execute("""
        SELECT Reserve_No, Name, PU_Date, Rate, Balance, Deposit, Est_Charge
        FROM Reserve
        WHERE [Account_No] = ?
        ORDER BY PU_Date DESC
    """, (account,))
    
    reserves = cur.fetchall()
    if reserves:
        print(f"\n✓ Found {len(reserves)} reserves:")
        for row in reserves:
            print(f"\n  Reserve: {row.Reserve_No}")
            print(f"    Name: {row.Name}")
            print(f"    Date: {row.PU_Date}")
            print(f"    Rate: ${row.Rate:,.2f}")
            print(f"    Est Charge: ${row.Est_Charge:,.2f}")
            print(f"    Deposit: ${row.Deposit:,.2f}")
            print(f"    Balance: ${row.Balance:,.2f}")
    else:
        print(f"\n✗ No reserves found for account {account}")
    
    # Get all payments for this account
    cur.execute("""
        SELECT PaymentID, Reserve_No, Amount, LastUpdated, LastUpdatedBy, [Key]
        FROM Payment
        WHERE [Account_No] = ?
        ORDER BY LastUpdated DESC
    """, (account,))
    
    payments = cur.fetchall()
    if payments:
        print(f"\n✓ Found {len(payments)} payments:")
        total = 0
        for row in payments:
            print(f"\n  PaymentID: {row.PaymentID}, Reserve: {row.Reserve_No}")
            print(f"    Amount: ${row.Amount:,.2f}")
            print(f"    Date: {row.LastUpdated}")
            print(f"    By: {row.LastUpdatedBy}")
            print(f"    Key: {row.Key}")
            total += row.Amount
        print(f"\n  TOTAL PAYMENTS: ${total:,.2f}")
    else:
        print(f"\n✗ No payments found for account {account}")
    
    cur.close()
    conn.close()
    
    # Check PostgreSQL
    print("\n" + "=" * 80)
    print("POSTGRESQL CHECK")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    # Check if this account_number exists
    cur.execute("""
        SELECT client_id, client_name, email
        FROM clients
        WHERE account_number = %s
    """, (account,))
    
    client = cur.fetchone()
    if client:
        print(f"\n✓ Found client: {client[1]} (ID: {client[0]})")
        print(f"    Email: {client[2]}")
    else:
        print(f"\n✗ No client found with account_number {account}")
    
    # Check charters
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, total_amount_due, paid_amount, balance
        FROM charters
        WHERE account_number = %s
        ORDER BY charter_date DESC
    """, (account,))
    
    charters = cur.fetchall()
    if charters:
        print(f"\n✓ Found {len(charters)} charters:")
        for row in charters:
            print(f"\n  Charter ID: {row[0]}, Reserve: {row[1]}")
            print(f"    Date: {row[2]}")
            print(f"    Total: ${row[3]:,.2f}, Paid: ${row[4]:,.2f}, Balance: ${row[5]:,.2f}")
    else:
        print(f"\n✗ No charters found with account_number {account}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_lms_account()
