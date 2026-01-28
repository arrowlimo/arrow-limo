#!/usr/bin/env python3
"""Check LMS for cash transactions in 2012."""

import pyodbc

LMS_PATH = r'L:\limo\backups\lms.mdb'
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

print("\n" + "="*80)
print("2012 CASH TRANSACTIONS FROM LMS")
print("="*80)

# Check for cash payment type in Reserve table
print("\n1. CASH PAYMENTS (Pymt_Type = 'Cash' or contains 'Cash'):")
print("-"*80)

lms_cur.execute("""
    SELECT Reserve_No, PU_Date, Name, Est_Charge, Deposit, Balance, Pymt_Type
    FROM Reserve
    WHERE YEAR(PU_Date) = 2012
    AND (Pymt_Type = 'Cash' OR Pymt_Type LIKE '%Cash%')
    ORDER BY PU_Date
""")

cash_reserves = lms_cur.fetchall()
if cash_reserves:
    total_est = 0
    total_deposit = 0
    for reserve_no, pu_date, name, est, deposit, balance, pymt_type in cash_reserves:
        print(f"  {reserve_no} {pu_date} {name or 'Unknown':<25} "
              f"Est:${est or 0:>8.2f} Paid:${deposit or 0:>8.2f} Type:{pymt_type}")
        total_est += (est or 0)
        total_deposit += (deposit or 0)
    print(f"\n  Total: {len(cash_reserves)} cash transactions")
    print(f"  Total estimated charges: ${total_est:.2f}")
    print(f"  Total cash collected: ${total_deposit:.2f}")
else:
    print("  No cash transactions found")

# Check all payment types in 2012 to see what exists
print("\n\n2. ALL PAYMENT TYPES IN 2012:")
print("-"*80)

lms_cur.execute("""
    SELECT Pymt_Type, COUNT(*) as count, SUM(Deposit) as total
    FROM Reserve
    WHERE YEAR(PU_Date) = 2012
    GROUP BY Pymt_Type
    ORDER BY COUNT(*) DESC
""")

pymt_types = lms_cur.fetchall()
if pymt_types:
    for pymt_type, count, total in pymt_types:
        print(f"  {pymt_type or 'NULL':<20} {count:>5} transactions  ${total or 0:>12.2f}")

lms_cur.close()
lms_conn.close()

print("\n")
