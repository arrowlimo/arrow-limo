#!/usr/bin/env python3
"""Investigate charter 019404 - was it really cancelled or a data error?"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("CHARTER 019404 INVESTIGATION")
print("=" * 80)

# Get charter details
cur.execute("""
    SELECT *
    FROM charters
    WHERE reserve_number = '019404'
""")

charter = cur.fetchone()

if not charter:
    print("\n[FAIL] Charter 019404 not found!")
    exit(1)

print(f"\n📋 CHARTER DETAILS:")
print(f"   Reserve: {charter['reserve_number']}")
print(f"   Charter ID: {charter['charter_id']}")
print(f"   Date: {charter['charter_date']}")
print(f"   Pickup time: {charter['pickup_time']}")
print(f"   Status: {'CANCELLED' if charter['cancelled'] else 'ACTIVE'}")
print(f"   Trip status: {charter['trip_status']}")
print(f"   Booking status: {charter['booking_status']}")
print(f"   ")
print(f"   Client ID: {charter['client_id']}")
print(f"   Passenger: {charter['passenger_count']}")
print(f"   Vehicle: {charter['vehicle']}")
print(f"   ")
print(f"   Pickup: {charter['pickup_address']}")
print(f"   Dropoff: {charter['dropoff_address']}")
print(f"   ")
print(f"   Rate: ${charter['rate'] or 0:.2f}")
print(f"   Total due: ${charter['total_amount_due'] or 0:.2f}")
print(f"   Paid: ${charter['paid_amount'] or 0:.2f}")
print(f"   Balance: ${charter['balance'] or 0:.2f}")
print(f"   ")
print(f"   Driver ID: {charter['assigned_driver_id']}")
print(f"   Created: {charter['created_at']}")
print(f"   Updated: {charter['updated_at']}")

if charter['notes']:
    print(f"\n📝 NOTES:")
    print(f"   {charter['notes']}")

# Get driver info
if charter['assigned_driver_id']:
    cur.execute("""
        SELECT full_name, status
        FROM employees
        WHERE employee_id = %s
    """, (charter['assigned_driver_id'],))
    
    driver = cur.fetchone()
    if driver:
        print(f"\n👤 DRIVER: {driver['full_name']} ({driver['status']})")

# Check payroll
print(f"\n💰 PAYROLL RECORDS:")
cur.execute("""
    SELECT id, pay_date, gross_pay, employee_id, driver_id,
           year, month, source
    FROM driver_payroll
    WHERE charter_id::integer = %s
    OR reserve_number = %s
    ORDER BY pay_date
""", (charter['charter_id'], charter['reserve_number']))

payroll = cur.fetchall()

if payroll:
    for p in payroll:
        emp_name = "Unknown"
        if p['employee_id']:
            cur.execute("SELECT full_name FROM employees WHERE employee_id = %s", (p['employee_id'],))
            emp = cur.fetchone()
            if emp:
                emp_name = emp['full_name']
        
        print(f"   Payroll ID {p['id']}:")
        print(f"      Pay date: {p['pay_date']}")
        print(f"      Employee: {emp_name} (ID: {p['employee_id']})")
        print(f"      Driver ID: {p['driver_id']}")
        print(f"      Amount: ${p['gross_pay']:.2f}")
        print(f"      Year/Month: {p['year']}/{p['month']}")
        print(f"      Source: {p['source']}")
else:
    print(f"   [FAIL] NO PAYROLL RECORDS FOUND")
    print(f"   → Driver was NOT paid for this charter")

# Check payments
print(f"\n💵 PAYMENTS RECEIVED:")
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method,
           reference_number, notes
    FROM payments
    WHERE charter_id = %s
    OR reserve_number = %s
    ORDER BY payment_date
""", (charter['charter_id'], charter['reserve_number']))

payments = cur.fetchall()

if payments:
    for p in payments:
        print(f"   Payment {p['payment_id']}:")
        print(f"      Date: {p['payment_date']}")
        print(f"      Amount: ${p['amount']:.2f}")
        print(f"      Method: {p['payment_method']}")
        print(f"      Reference: {p['reference_number']}")
        if p['notes']:
            print(f"      Notes: {p['notes']}")
else:
    print(f"   [FAIL] NO PAYMENTS FOUND")

# Check charges
print(f"\n📋 CHARGES:")
cur.execute("""
    SELECT id as charge_id, description, amount, created_at
    FROM charter_charges
    WHERE charter_id = %s
    ORDER BY created_at
""", (charter['charter_id'],))

charges = cur.fetchall()

if charges:
    for c in charges:
        print(f"   Charge {c['charge_id']}: {c['description']} - ${c['amount']:.2f}")
else:
    print(f"   [FAIL] NO CHARGES FOUND")

# Check LMS data
print(f"\n🔍 CHECKING LMS SOURCE DATA:")
try:
    import pyodbc
    LMS_PATH = r'L:\limo\lms.mdb'
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    lms_cur.execute("""
        SELECT Reserve_No, PU_Date, Rate, Balance, Deposit,
               Cancel, Trip_Status, Name, Pickup, Dropoff
        FROM Reserve
        WHERE Reserve_No = '019404'
    """)
    
    lms = lms_cur.fetchone()
    
    if lms:
        print(f"   LMS Reserve_No: {lms.Reserve_No}")
        print(f"   LMS PU_Date: {lms.PU_Date}")
        print(f"   LMS Rate: ${lms.Rate or 0:.2f}")
        print(f"   LMS Balance: ${lms.Balance or 0:.2f}")
        print(f"   LMS Deposit: ${lms.Deposit or 0:.2f}")
        print(f"   LMS Cancel: {lms.Cancel}")
        print(f"   LMS Trip_Status: {lms.Trip_Status}")
        print(f"   LMS Name: {lms.Name}")
        print(f"   LMS Pickup: {lms.Pickup}")
        print(f"   LMS Dropoff: {lms.Dropoff}")
    else:
        print(f"   [FAIL] NOT FOUND IN LMS")
    
    lms_conn.close()
except Exception as e:
    print(f"   [WARN] Could not check LMS: {e}")

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

if not payroll:
    print("\n[OK] DRIVER WAS NOT PAID")
    print("   The earlier report showing '$0.00 driver pay' was correct.")
    print("   No payroll records exist for this charter.")

if charter['cancelled'] and payments:
    print(f"\n[WARN] CHARTER IS CANCELLED BUT HAS {len(payments)} PAYMENTS (${sum(p['amount'] for p in payments):.2f})")
    print("   This indicates customer paid deposits but charter was cancelled.")
    print("   Negative balance represents customer credit/refund due.")

if charter['cancelled']:
    print(f"\n❓ WHY IS THIS MARKED CANCELLED?")
    print("   Check if this was:")
    print("   1. Legitimate cancellation (customer cancelled)")
    print("   2. Data entry error (should be active)")
    print("   3. Airport run that was completed but marked wrong")

conn.close()
