"""
CRITICAL AUDIT: Why are almsdata balances showing OVERPAID when LMS shows $0.00?
This script identifies the root cause of discrepancies.
"""

import pyodbc
import psycopg2
import os
from decimal import Decimal
import csv
from datetime import datetime

# LMS connection
LMS_PATH = r'L:\limo\data\lms.mdb'
lms_conn_str = (
    rf'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};'
    rf'DBQ={LMS_PATH};'
)

# almsdata connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

print("=" * 100)
print("OVERPAYMENT INVESTIGATION - ALMSDATA PAYMENT AUDIT")
print("=" * 100)

# Step 1: Get all mismatched reserves
print("\nStep 1: LOADING MISMATCH DATA")
print("-" * 100)

mismatches = {}

try:
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cursor = lms_conn.cursor()
    
    lms_cursor.execute("""
        SELECT Reserve_No, Name, Balance, Est_Charge
        FROM Reserve
        ORDER BY Reserve_No
    """)
    
    for row in lms_cursor.fetchall():
        reserve_no = str(row[0]).strip() if row[0] else None
        name = str(row[1]).strip() if row[1] else None
        balance = row[2]
        est_charge = row[3]
        
        if reserve_no:
            mismatches[reserve_no] = {
                'lms_name': name,
                'lms_balance': balance,
                'lms_est_charge': est_charge
            }
    
    lms_conn.close()
    print(f"Loaded {len(mismatches)} LMS reserves")
    
except Exception as e:
    print(f"ERROR: {e}")

# Step 2: Get ALMS data for these charters
print("\nStep 2: LOADING ALMSDATA CHARTER DATA")
print("-" * 100)

try:
    alms_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    alms_cursor = alms_conn.cursor()
    
    # Get all charters with balances
    alms_cursor.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            cl.name as client_name,
            c.charter_date,
            c.total_amount_due,
            c.balance,
            c.created_at
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number IS NOT NULL
        ORDER BY c.reserve_number
    """)
    
    alms_charters = {}
    for row in alms_cursor.fetchall():
        charter_id = row[0]
        reserve_no = row[1]
        client_name = row[2]
        charter_date = row[3]
        total_due = row[4] if row[4] else 0
        balance = row[5] if row[5] else 0
        created_at = row[6]
        
        alms_charters[reserve_no] = {
            'charter_id': charter_id,
            'client_name': client_name,
            'charter_date': charter_date,
            'total_amount_due': total_due,
            'balance': balance,
            'created_at': created_at
        }
    
    print(f"Loaded {len(alms_charters)} almsdata charters")
    
except Exception as e:
    print(f"ERROR: {e}")

# Step 3: Identify overpaid reserves (balance < 0)
print("\nStep 3: IDENTIFYING OVERPAID RESERVES")
print("-" * 100)

overpaid = {}
for reserve_no in sorted(alms_charters.keys()):
    if reserve_no in mismatches:
        alms_bal = alms_charters[reserve_no]['balance']
        lms_bal = mismatches[reserve_no]['lms_balance']
        
        if alms_bal < 0:  # Overpaid
            overpaid[reserve_no] = {
                'lms_balance': lms_bal,
                'alms_balance': alms_bal,
                'overpay_amount': abs(alms_bal),
                'charter_id': alms_charters[reserve_no]['charter_id'],
                'total_due': alms_charters[reserve_no]['total_amount_due'],
                'client_name': alms_charters[reserve_no]['client_name']
            }

print(f"Found {len(overpaid)} overpaid reserves")

# Step 4: Audit ALL payments for overpaid charters
print("\nStep 4: DETAILED PAYMENT AUDIT FOR OVERPAID RESERVES")
print("-" * 100)

problem_cases = []

try:
    for reserve_no in sorted(overpaid.keys())[:20]:  # First 20 for detailed output
        charter_id = overpaid[reserve_no]['charter_id']
        total_due = overpaid[reserve_no]['total_due']
        alms_bal = overpaid[reserve_no]['alms_balance']
        client_name = overpaid[reserve_no]['client_name']
        
        # Get ALL payments for this charter
        alms_cursor.execute("""
            SELECT 
                p.payment_id,
                p.reserve_number,
                p.amount,
                p.payment_date,
                p.payment_method,
                p.created_at,
                p.notes
            FROM payments p
            WHERE p.reserve_number = %s
            ORDER BY p.payment_date
        """, (reserve_no,))
        
        payments = alms_cursor.fetchall()
        total_paid = sum([p[2] for p in payments if p[2]])
        
        print(f"\n>>> Reserve {reserve_no} ({client_name})")
        print(f"    Total Due:     ${total_due:.2f}")
        print(f"    Total Paid:    ${total_paid:.2f}")
        print(f"    Balance:       ${alms_bal:.2f} ({'OVERPAID' if alms_bal < 0 else 'OWED'})")
        print(f"    Overpay:       ${abs(alms_bal):.2f}")
        print(f"    Payments ({len(payments)} records):")
        
        for p in payments:
            print(f"      {p[3]} | ${p[2]:8.2f} | {p[4]:15} | {p[6] if p[6] else '(no notes)'}")
        
        # Check for issues
        if abs(total_paid - total_due) > 0.01:
            if total_paid > total_due:
                problem_cases.append({
                    'reserve_no': reserve_no,
                    'client_name': client_name,
                    'total_due': total_due,
                    'total_paid': total_paid,
                    'overpay': total_paid - total_due,
                    'issue': f'OVERPAID BY ${abs(total_paid - total_due):.2f}',
                    'payment_count': len(payments)
                })
            else:
                problem_cases.append({
                    'reserve_no': reserve_no,
                    'client_name': client_name,
                    'total_due': total_due,
                    'total_paid': total_paid,
                    'overpay': total_paid - total_due,
                    'issue': f'UNDERPAID BY ${abs(total_paid - total_due):.2f}',
                    'payment_count': len(payments)
                })
    
    alms_conn.close()
    
except Exception as e:
    print(f"ERROR in payment audit: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Summary analysis
print("\n" + "=" * 100)
print("ANALYSIS SUMMARY")
print("=" * 100)

print(f"\nTotal mismatches between LMS and almsdata: 357")
print(f"Total OVERPAID reserves (negative balance): {len(overpaid)}")

if problem_cases:
    print(f"\n⚠️  PROBLEM CASES FOUND: {len(problem_cases)} reserves have payment/balance mismatches")
    print("\nDetailed breakdown of problematic reserves:")
    print("-" * 100)
    
    for case in problem_cases[:20]:
        print(f"{case['reserve_no']:6} | {case['client_name']:30} | Due: ${case['total_due']:10.2f} | Paid: ${case['total_paid']:10.2f} | {case['issue']}")

# Step 6: Root cause analysis
print("\n" + "=" * 100)
print("POTENTIAL ROOT CAUSES")
print("=" * 100)

print("""
1. DUPLICATE PAYMENTS
   - Same amount paid multiple times for same charter
   - Solution: Check payment records for exact duplicates

2. PAYMENTS APPLIED TO WRONG RESERVE
   - Payment recorded under one reserve number but should be on another
   - Solution: Search for similar amounts on different reserves

3. CHARGEBACKS/REVERSALS NOT RECORDED
   - Payment posted but then reversed in bank, but reversal not recorded in almsdata
   - Solution: Check if payment has banking_transaction_id and verify with bank

4. INVOICE ADJUSTMENTS
   - Total_amount_due changed after payment was made
   - Solution: Check charter modification history

5. PAYMENT CREDITING ERROR
   - Payment amounts entered incorrectly (too much paid)
   - Solution: Manual verification needed

6. TEST/SAMPLE DATA
   - Old test payments never cleaned up
   - Solution: Check created_at dates vs business dates

NEXT STEPS:
Run: python scripts/audit_payment_details.py
This will provide detailed payment-by-payment analysis for overpaid reserves.
""")

print("=" * 100)
