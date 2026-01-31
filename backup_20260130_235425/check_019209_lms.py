#!/usr/bin/env python3
"""Check charter 019209 in detail from LMS."""

import pyodbc

LMS_PATH = r'L:\limo\backups\lms.mdb'
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

print("\n" + "="*80)
print("CHARTER 019209 - LMS DETAILS")
print("="*80)

# Get reserve details
lms_cur.execute("""
    SELECT Reserve_No, PU_Date, Name, Rate, Est_Charge, Deposit, Balance, 
           Vehicle, Driver, Notes
    FROM Reserve
    WHERE Reserve_No = '019209'
""")

reserve = lms_cur.fetchone()
if reserve:
    print("\nReserve Details:")
    print(f"  Reserve_No: {reserve[0]}")
    print(f"  PU_Date: {reserve[1]}")
    print(f"  Name: {reserve[2]}")
    print(f"  Rate: ${reserve[3] if reserve[3] else 0:.2f}")
    print(f"  Est_Charge: ${reserve[4] if reserve[4] else 0:.2f}")
    print(f"  Deposit (Paid): ${reserve[5] if reserve[5] else 0:.2f}")
    print(f"  Balance: ${reserve[6] if reserve[6] else 0:.2f}")
    print(f"  Vehicle: {reserve[7]}")
    print(f"  Driver: {reserve[8]}")
    print(f"  Notes: {reserve[9]}")

# Get charges/line items
print("\n" + "-"*80)
print("CHARGES (from Charges table):")
print("-"*80)

lms_cur.execute("""
    SELECT Description, Type, Rate, Amount
    FROM Charges
    WHERE Reserve_No = '019209'
    ORDER BY Type
""")

charges = lms_cur.fetchall()
if charges:
    total_charges = 0
    for desc, typ, rate, amt in charges:
        print(f"  {desc:<30} Type: {typ:<10} Rate: ${rate or 0:>8.2f} Amount: ${amt or 0:>8.2f}")
        total_charges += (amt or 0)
    print(f"  {'TOTAL CHARGES':<30} ${total_charges:>8.2f}")
else:
    print("  No charges found")

# Get payments
print("\n" + "-"*80)
print("PAYMENTS (from Payment table):")
print("-"*80)

lms_cur.execute("""
    SELECT [Key], LastUpdated, Amount, LastUpdatedBy
    FROM Payment
    WHERE Reserve_No = '019209'
    ORDER BY LastUpdated
""")

payments = lms_cur.fetchall()
if payments:
    total_paid = 0
    for key, date, amt, by_who in payments:
        print(f"  {key:<20} {date} ${amt or 0:>10.2f} by {by_who}")
        total_paid += (amt or 0)
    print(f"  {'TOTAL PAID':<20} ${total_paid:>10.2f}")
else:
    print("  No payments found")

lms_cur.close()
lms_conn.close()

print("\n")
