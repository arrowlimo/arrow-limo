#!/usr/bin/env python3
"""
Analyze the 20 amount mismatches in detail.
"""

import pyodbc
import psycopg2
import os
from decimal import Decimal

LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")

# The 20 mismatched reserves
MISMATCHES = [
    '016202', '017943', '017991', '019236', '019463', '019588', '019595',
    '019598', '019642', '019731', '019745', '019758', '019759', '019760',
    '019761', '019836', '019839', '019845', '019846', '019848'
]

def analyze_mismatch(reserve_no, lms_conn, alms_conn):
    """Analyze a single mismatch in detail."""
    lms_cur = lms_conn.cursor()
    alms_cur = alms_conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"RESERVE {reserve_no}")
    print(f"{'='*80}")
    
    # Get LMS charges - Reserve_No is text field
    lms_cur.execute("""
        SELECT Amount, [Desc], Tag, [Closed]
        FROM Charge 
        WHERE Reserve_No = ?
        ORDER BY Sequence
    """, (reserve_no,))
    
    lms_charges = []
    lms_total = Decimal('0')
    for row in lms_cur.fetchall():
        amt = Decimal(str(row[0])) if row[0] else Decimal('0')
        lms_charges.append({
            'amount': amt,
            'desc': row[1] or '',
            'tag': row[2] or '',
            'closed': row[3]
        })
        lms_total += amt
    
    print(f"\nLMS Charges (Total: ${lms_total:.2f}):")
    for i, c in enumerate(lms_charges, 1):
        closed_flag = " [CLOSED]" if c['closed'] else ""
        print(f"  {i}. {c['desc']:30} ${c['amount']:>10.2f} (Tag: {c['tag']}){closed_flag}")
    
    # Get LMS Reserve status
    lms_cur.execute("""
        SELECT [Closed], [Cancelled], Balance, Deposit
        FROM Reserve
        WHERE Reserve_No = ?
    """, (int(reserve_no),))
    lms_reserve = lms_cur.fetchone()
    if lms_reserve:
        print(f"\nLMS Reserve Status:")
        print(f"  Closed: {lms_reserve[0]}, Cancelled: {lms_reserve[1]}")
        print(f"  Balance: ${lms_reserve[2] or 0:.2f}, Deposit: ${lms_reserve[3] or 0:.2f}")
    
    # Get ALMS charter
    alms_cur.execute("""
        SELECT total_amount_due, balance, deposit, rate, status, cancelled, closed
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_no,))
    
    alms_charter = alms_cur.fetchone()
    if alms_charter:
        print(f"\nALMS Charter:")
        print(f"  Total Amount Due: ${alms_charter[0] or 0:.2f}")
        print(f"  Balance: ${alms_charter[1] or 0:.2f}")
        print(f"  Deposit: ${alms_charter[2] or 0:.2f}")
        print(f"  Rate: ${alms_charter[3] or 0:.2f}")
        print(f"  Status: {alms_charter[4] or 'NULL'}, Cancelled: {alms_charter[5]}, Closed: {alms_charter[6]}")
        
        diff = lms_total - (alms_charter[0] or Decimal('0'))
        print(f"\n  DIFFERENCE: ${diff:.2f} (LMS - ALMS)")
        
        # Categorize the issue
        if alms_charter[0] == 0:
            print(f"  ⚠ ISSUE: ALMS has $0 total - charter may be cancelled/incomplete")
        elif lms_total == 0:
            print(f"  ⚠ ISSUE: LMS has $0 charges - charges may be closed/deleted")
        elif abs(diff) <= Decimal('10'):
            print(f"  ℹ Minor rounding/calculation difference (<$10)")
        else:
            print(f"  ⚠ MAJOR DIFFERENCE (>${abs(diff):.2f})")
    else:
        print(f"\n⚠ CHARTER NOT FOUND IN ALMS!")


def main():
    print("Analyzing 20 Amount Mismatches")
    print("="*80)
    
    lms_conn = pyodbc.connect(f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    alms_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    
    try:
        for reserve_no in MISMATCHES:
            analyze_mismatch(reserve_no, lms_conn, alms_conn)
            
        # Summary categories
        print(f"\n\n{'='*80}")
        print("SUMMARY OF ISSUES")
        print("="*80)
        print("\nIssue Categories:")
        print("1. Charges with Closed flag in LMS (may be cancelled charges)")
        print("2. ALMS total = $0 (charter may be cancelled or not imported fully)")
        print("3. LMS total = $0 (charges closed/deleted in LMS)")
        print("4. Minor rounding differences (<$10)")
        print("5. Major differences - needs investigation")
        
    finally:
        lms_conn.close()
        alms_conn.close()


if __name__ == '__main__':
    main()
