#!/usr/bin/env python3
"""
Verify charter balances in PostgreSQL against LMS Access database.
Focus on charters with balances > $100 to identify discrepancies.
"""

import psycopg2
import pyodbc
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def get_lms_connection():
    LMS_PATH = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

# Get charters from user's list with balances > $100
problem_charters = [
    '019551', '019718', '019715', '019672', '019687', '019642', '019627', '019727',
    '016540', '019685', '019713', '019721', '019640', '019731', '019209', '016086',
    '018295', '015940', '015808', '017092', '019641', '019738', '015643', '013690',
    '017991', '015770', '019725', '015884', '015875', '019720', '019716', '017720',
    '017612', '018199', '017024', '019700', '019745', '019644', '019714', '019556'
]

pg_conn = get_db_connection()
pg_cur = pg_conn.cursor()

lms_conn = get_lms_connection()
lms_cur = lms_conn.cursor()

print("\n" + "="*120)
print("CHARTER BALANCE VERIFICATION: PostgreSQL vs LMS")
print("="*120)
print(f"\n{'Reserve':<10} {'PG Total':<12} {'PG Paid':<12} {'PG Balance':<12} {'LMS Total':<12} {'LMS Paid':<12} {'LMS Balance':<12} {'Match':<8}")
print("-"*120)

mismatches = []
matches = 0
not_in_lms = []

for reserve_num in problem_charters[:40]:  # Process first 40
    # Get PostgreSQL data
    pg_cur.execute("""
        SELECT total_amount_due, paid_amount, balance, cancelled
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    
    pg_row = pg_cur.fetchone()
    
    if not pg_row:
        print(f"{reserve_num:<10} NOT FOUND IN POSTGRESQL")
        continue
    
    pg_total = float(pg_row[0] or 0)
    pg_paid = float(pg_row[1] or 0)
    pg_balance = float(pg_row[2] or 0)
    pg_cancelled = pg_row[3]
    
    # Get LMS data
    try:
        lms_cur.execute("""
            SELECT Est_Charge, Deposit, Balance
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve_num,))
        
        lms_row = lms_cur.fetchone()
        
        if not lms_row:
            not_in_lms.append(reserve_num)
            print(f"{reserve_num:<10} NOT FOUND IN LMS")
            continue
        
        lms_total = float(lms_row[0] or 0)
        lms_paid = float(lms_row[1] or 0)
        lms_balance = float(lms_row[2] or 0)
        
        # Check for discrepancies (allow $0.01 tolerance for rounding)
        total_match = abs(pg_total - lms_total) < 0.02
        paid_match = abs(pg_paid - lms_paid) < 0.02
        balance_match = abs(pg_balance - lms_balance) < 0.02
        
        if total_match and paid_match and balance_match:
            match_str = "OK"
            matches += 1
        else:
            match_str = "MISMATCH"
            mismatches.append({
                'reserve': reserve_num,
                'pg_total': pg_total,
                'pg_paid': pg_paid,
                'pg_balance': pg_balance,
                'lms_total': lms_total,
                'lms_paid': lms_paid,
                'lms_balance': lms_balance
            })
        
        print(f"{reserve_num:<10} ${pg_total:>10.2f} ${pg_paid:>10.2f} ${pg_balance:>10.2f} "
              f"${lms_total:>10.2f} ${lms_paid:>10.2f} ${lms_balance:>10.2f} {match_str:<8}")
        
    except Exception as e:
        print(f"{reserve_num:<10} ERROR: {e}")

print("\n" + "="*120)
print("SUMMARY")
print("="*120)
print(f"Charters checked: {len(problem_charters[:40])}")
print(f"Matches: {matches}")
print(f"Mismatches: {len(mismatches)}")
print(f"Not in LMS: {len(not_in_lms)}")

if mismatches:
    print("\n" + "="*120)
    print("MISMATCHES REQUIRING CORRECTION")
    print("="*120)
    
    for m in mismatches:
        print(f"\nReserve: {m['reserve']}")
        print(f"  PostgreSQL: Total=${m['pg_total']:.2f} Paid=${m['pg_paid']:.2f} Balance=${m['pg_balance']:.2f}")
        print(f"  LMS:        Total=${m['lms_total']:.2f} Paid=${m['lms_paid']:.2f} Balance=${m['lms_balance']:.2f}")
        
        # Identify the issue
        if abs(m['pg_total'] - m['lms_total']) >= 0.02:
            print(f"  ISSUE: Total amount mismatch (${m['pg_total'] - m['lms_total']:.2f} difference)")
        if abs(m['pg_paid'] - m['lms_paid']) >= 0.02:
            print(f"  ISSUE: Paid amount mismatch (${m['pg_paid'] - m['lms_paid']:.2f} difference)")
        if abs(m['pg_balance'] - m['lms_balance']) >= 0.02:
            print(f"  ISSUE: Balance mismatch (${m['pg_balance'] - m['lms_balance']:.2f} difference)")

if not_in_lms:
    print("\n" + "="*120)
    print("CHARTERS NOT FOUND IN LMS (may be new entries)")
    print("="*120)
    for res in not_in_lms:
        print(f"  {res}")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()

print("\n")
