"""
Investigate charters 014941 and 013717 - why huge credits when paid in full?
"""

import psycopg2
import os

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def investigate_charter(cur, reserve_number):
    print("\n" + "="*100)
    print(f"CHARTER {reserve_number} INVESTIGATION")
    print("="*100 + "\n")
    
    # Get charter details
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.cancelled,
            c.closed
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = %s
    """, (reserve_number,))
    
    charter = cur.fetchone()
    
    if not charter:
        print(f"Charter {reserve_number} not found!")
        return
    
    charter_id, reserve_num, charter_date, client_name, total_due, paid, balance, status, cancelled, closed = charter
    
    print(f"Charter Details:")
    print(f"  Reserve Number: {reserve_num}")
    print(f"  Charter Date: {charter_date}")
    print(f"  Client: {client_name}")
    print(f"  Status: {status}")
    print(f"  Cancelled: {cancelled}")
    print(f"  Closed: {closed}")
    print(f"\nFinancial Summary:")
    print(f"  Total Amount Due: ${total_due or 0:,.2f}")
    print(f"  Paid Amount: ${paid or 0:,.2f}")
    print(f"  Balance: ${balance or 0:,.2f}")
    
    # Get all charges
    cur.execute("""
        SELECT charge_id, description, amount, created_at
        FROM charter_charges
        WHERE charter_id = %s
        ORDER BY charge_id
    """, (charter_id,))
    charges = cur.fetchall()
    
    print(f"\nCharges ({len(charges)} total):")
    if charges:
        charge_total = 0
        for charge_id, desc, amount, created_at in charges:
            print(f"  {charge_id}: {desc:<40} ${amount:>10,.2f}  (created: {created_at})")
            charge_total += (amount or 0)
        print(f"  {'TOTAL CHARGES':<44} ${charge_total:>10,.2f}")
    else:
        print("  No charges found")
    
    # Get all payments
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.notes,
            p.created_at,
            p.square_transaction_id
        FROM payments p
        WHERE p.charter_id = %s
        ORDER BY p.payment_date, p.payment_id
    """, (charter_id,))
    payments = cur.fetchall()
    
    print(f"\nPayments ({len(payments)} total):")
    if payments:
        payment_total = 0
        for payment_id, payment_date, amount, method, notes, created_at, square_id in payments:
            square_info = f" [Square: {square_id}]" if square_id else ""
            notes_info = f" - {notes[:40]}" if notes else ""
            print(f"  {payment_id}: {payment_date} ${amount:>10,.2f} ({method or 'unknown'}){square_info}{notes_info}")
            payment_total += (amount or 0)
        print(f"  {'TOTAL PAYMENTS':<44} ${payment_total:>10,.2f}")
    else:
        print("  No payments found")
    
    # Check LMS data
    print("\n" + "-"*100)
    print("Checking LMS Source Data...")
    print("-"*100)
    
    try:
        import pyodbc
        LMS_PATH = r'L:\limo\lms.mdb'
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        lms_conn = pyodbc.connect(conn_str)
        lms_cur = lms_conn.cursor()
        
        # Get reserve from LMS
        lms_cur.execute("""
            SELECT Reserve_No, PU_Date, Rate, Balance, Deposit, Est_Charge
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve_number,))
        lms_reserve = lms_cur.fetchone()
        
        if lms_reserve:
            lms_reserve_no, lms_date, lms_rate, lms_balance, lms_deposit, lms_est_charge = lms_reserve
            print(f"\nLMS Reserve Data:")
            print(f"  Reserve_No: {lms_reserve_no}")
            print(f"  PU_Date: {lms_date}")
            print(f"  Rate: ${lms_rate or 0:,.2f}")
            print(f"  Est_Charge: ${lms_est_charge or 0:,.2f}")
            print(f"  Deposit: ${lms_deposit or 0:,.2f}")
            print(f"  Balance: ${lms_balance or 0:,.2f}")
        else:
            print(f"\nNOT FOUND in LMS")
        
        # Get payments from LMS
        lms_cur.execute("""
            SELECT PaymentID, Amount, LastUpdated, [Key]
            FROM Payment
            WHERE Reserve_No = ?
            ORDER BY LastUpdated
        """, (reserve_number,))
        lms_payments = lms_cur.fetchall()
        
        if lms_payments:
            print(f"\nLMS Payments ({len(lms_payments)} total):")
            lms_payment_total = 0
            for lms_payment_id, lms_amount, lms_date, lms_key in lms_payments:
                print(f"  {lms_payment_id}: {lms_date} ${lms_amount:>10,.2f} (Key: {lms_key})")
                lms_payment_total += (lms_amount or 0)
            print(f"  {'TOTAL LMS PAYMENTS':<44} ${lms_payment_total:>10,.2f}")
        else:
            print("\nNo payments in LMS")
        
        lms_cur.close()
        lms_conn.close()
        
    except Exception as e:
        print(f"Could not check LMS: {e}")
    
    print("\n" + "="*100)
    print("ANALYSIS:")
    print("="*100)
    
    if len(charges) == 0 and paid > 0:
        print("[WARN]  NO CHARGES but has payments - charges may have been deleted")
        print("    This creates a credit balance equal to all payments")
    
    if paid > total_due and total_due > 0:
        print(f"[WARN]  OVERPAID: Payments (${paid:,.2f}) exceed charges (${total_due:,.2f})")
        print(f"    Overpayment amount: ${paid - total_due:,.2f}")
    
    if len(payments) > 1:
        print(f"ℹ️  Multiple payments ({len(payments)}) - may include duplicates or batch payments")

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Investigate both charters
    investigate_charter(cur, '014941')
    investigate_charter(cur, '013717')
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
