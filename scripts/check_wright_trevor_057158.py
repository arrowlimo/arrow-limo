"""Search for Wright Trevor reservation 057158 from LMS screenshot."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("SEARCHING FOR RESERVE NUMBER 057158 (Wright Trevor)")
print("=" * 80)

# Search by exact reserve number
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due, 
           c.paid_amount, c.balance, c.payment_status, c.status,
           cl.client_name
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.reserve_number = '057158'
""")

charter = cur.fetchone()
if charter:
    print(f"\n✓ FOUND Charter:")
    print(f"  Charter ID: {charter[0]}")
    print(f"  Reserve Number: {charter[1]}")
    print(f"  Date: {charter[2]}")
    print(f"  Client: {charter[8] or 'N/A'}")
    print(f"  Total Due: ${charter[3]:,.2f}" if charter[3] else "  Total Due: N/A")
    print(f"  Paid: ${charter[4]:,.2f}" if charter[4] else "  Paid: N/A")
    print(f"  Balance: ${charter[5]:,.2f}" if charter[5] else "  Balance: N/A")
    print(f"  Payment Status: {charter[6] or 'N/A'}")
    print(f"  Status: {charter[7] or 'N/A'}")
    
    # Get payments for this charter
    print(f"\nPayments for Reserve {charter[1]}:")
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_method, 
               payment_key, reference_number, notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (charter[1],))
    
    payments = cur.fetchall()
    total_payments = 0
    if payments:
        for p in payments:
            total_payments += (p[2] or 0)
            print(f"  Payment ID {p[0]}: ${p[2]:,.2f} on {p[1]} via {p[3]}")
            if p[4]:
                print(f"    Key: {p[4]}")
            if p[5]:
                print(f"    Reference: {p[5]}")
            if p[6]:
                print(f"    Notes: {p[6]}")
        print(f"  TOTAL PAYMENTS: ${total_payments:,.2f}")
    else:
        print("  ✗ No payments found for this charter")
        
    # Get charges
    print(f"\nCharges for Reserve {charter[1]}:")
    cur.execute("""
        SELECT charge_id, description, amount, charge_date
        FROM charter_charges
        WHERE charter_id = %s
        ORDER BY charge_date
    """, (charter[0],))
    
    charges = cur.fetchall()
    total_charges = 0
    if charges:
        for ch in charges:
            total_charges += (ch[2] or 0)
            print(f"  Charge ID {ch[0]}: ${ch[2]:,.2f} - {ch[1]}")
        print(f"  TOTAL CHARGES: ${total_charges:,.2f}")
    else:
        print("  ✗ No charges found for this charter")
        
else:
    print("\n✗ Charter 057158 NOT FOUND in database")
    
    # Check if it exists in LMS
    print("\nChecking LMS Access database...")
    try:
        import pyodbc
        LMS_PATH = r'L:\limo\lms.mdb'
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        lms_conn = pyodbc.connect(conn_str)
        lms_cur = lms_conn.cursor()
        
        lms_cur.execute("""
            SELECT Reserve_No, Account_No, PU_Date, Name, Est_Charge, Deposit, Balance
            FROM Reserve
            WHERE Reserve_No = '057158'
        """)
        
        lms_reserve = lms_cur.fetchone()
        if lms_reserve:
            print(f"\n✓ FOUND in LMS:")
            print(f"  Reserve: {lms_reserve[0]}")
            print(f"  Account: {lms_reserve[1]}")
            print(f"  Date: {lms_reserve[2]}")
            print(f"  Name: {lms_reserve[3]}")
            print(f"  Est Charge: ${lms_reserve[4]:,.2f}" if lms_reserve[4] else "  Est Charge: N/A")
            print(f"  Deposit: ${lms_reserve[5]:,.2f}" if lms_reserve[5] else "  Deposit: N/A")
            print(f"  Balance: ${lms_reserve[6]:,.2f}" if lms_reserve[6] else "  Balance: N/A")
            
            # Get LMS payments
            print(f"\nLMS Payments for Reserve {lms_reserve[0]}:")
            lms_cur.execute("""
                SELECT PaymentID, Amount, [Key], LastUpdated
                FROM Payment
                WHERE Reserve_No = '057158'
                ORDER BY LastUpdated
            """)
            
            lms_payments = lms_cur.fetchall()
            if lms_payments:
                lms_total = 0
                for lp in lms_payments:
                    lms_total += (lp[1] or 0)
                    print(f"  LMS Payment {lp[0]}: ${lp[1]:,.2f} on {lp[3]} (Key: {lp[2]})")
                print(f"  TOTAL LMS PAYMENTS: ${lms_total:,.2f}")
            else:
                print("  ✗ No payments in LMS for this reserve")
        else:
            print("  ✗ NOT FOUND in LMS either")
            
        lms_cur.close()
        lms_conn.close()
    except Exception as e:
        print(f"  ! Could not access LMS: {e}")

# Also search for Wright/Trevor names
print("\n" + "=" * 80)
print("SEARCHING FOR WRIGHT/TREVOR NAMES IN DATABASE")
print("=" * 80)

cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.charter_date, 
           cl.client_name, c.total_amount_due, c.paid_amount, c.balance
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE cl.client_name ILIKE '%%wright%%'
       OR cl.client_name ILIKE '%%trevor%%'
    ORDER BY c.charter_date DESC
    LIMIT 10
""")

name_matches = cur.fetchall()
if name_matches:
    print(f"\nFound {len(name_matches)} charters with Wright/Trevor names:")
    for m in name_matches:
        print(f"  Reserve {m[1]}: {m[3]} on {m[2]}, Total=${m[4] or 0:,.2f}, Paid=${m[5] or 0:,.2f}, Balance=${m[6] or 0:,.2f}")
else:
    print("\n✗ No charters found with Wright or Trevor names")

cur.close()
conn.close()
