#!/usr/bin/env python3
"""
Verify if pre-2025 receivables have already been fixed/zeroed in LMS.
Compare almsdata balance vs LMS balance for aged receivables.
"""

import psycopg2
import pyodbc

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

LMS_PATH = r"L:\limo\backups\lms.mdb"


def get_almsdata_receivables():
    """Get pre-2025 non-balanced charters from almsdata."""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.status,
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0) as payments,
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) - 
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0) as balance
        FROM charters c
        WHERE c.charter_date < '2025-01-01'
            AND (
                COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = c.reserve_number), 0) - 
                COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = c.reserve_number), 0)
            ) > 0.01
        ORDER BY balance DESC
    """)
    
    receivables = []
    for row in cur.fetchall():
        reserve, date, status, charges, payments, balance = row
        receivables.append({
            'reserve': reserve,
            'date': str(date),
            'status': status or '',
            'alms_charges': float(charges),
            'alms_payments': float(payments),
            'alms_balance': float(balance)
        })
    
    cur.close()
    conn.close()
    return receivables


def get_lms_balance(reserve, lms_cur):
    """Get LMS balance for a reserve."""
    charges = 0.0
    payments = 0.0
    
    try:
        # Charges
        lms_cur.execute("SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
        
        reserve_field = None
        amount_field = None
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
        
        if reserve_field and amount_field:
            lms_cur.execute(f"SELECT SUM([{amount_field}]) FROM Charge WHERE [{reserve_field}] = ?", (reserve,))
            row = lms_cur.fetchone()
            charges = float(row[0] or 0)
    except Exception:
        pass
    
    try:
        # Payments
        lms_cur.execute("SELECT TOP 1 * FROM Payment")
        cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
        
        reserve_field = None
        amount_field = None
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
        
        if reserve_field and amount_field:
            lms_cur.execute(f"SELECT SUM([{amount_field}]) FROM Payment WHERE [{reserve_field}] = ?", (reserve,))
            row = lms_cur.fetchone()
            payments = float(row[0] or 0)
    except Exception:
        pass
    
    return charges - payments


def main():
    print("Verifying pre-2025 receivables vs LMS...")
    print()
    
    # Check 017991 status first
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute("SELECT status FROM charters WHERE reserve_number = %s", ('017991',))
    row = cur.fetchone()
    if row:
        print(f"017991 status in almsdata: '{row[0]}'")
        print()
    cur.close()
    conn.close()
    
    # Get almsdata receivables
    receivables = get_almsdata_receivables()
    
    # Connect to LMS
    lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    # Compare each
    already_fixed_in_lms = []
    not_fixed_in_lms = []
    
    for r in receivables:
        lms_balance = get_lms_balance(r['reserve'], lms_cur)
        
        # If LMS balance is ~0 but almsdata has positive balance, it's already fixed in LMS
        if abs(lms_balance) < 1.0 and r['alms_balance'] > 0.01:
            already_fixed_in_lms.append({
                **r,
                'lms_balance': lms_balance
            })
        else:
            not_fixed_in_lms.append({
                **r,
                'lms_balance': lms_balance
            })
    
    lms_cur.close()
    lms_conn.close()
    
    # Report
    print("=" * 100)
    print("ALREADY FIXED IN LMS (need to write down in almsdata)")
    print("=" * 100)
    print(f"{'Reserve':<12} {'Date':<12} {'Status':<15} {'ALMS Balance':<15} {'LMS Balance':<15}")
    print("-" * 100)
    
    total_to_writedown = 0.0
    for r in already_fixed_in_lms:
        print(f"{r['reserve']:<12} {r['date']:<12} {r['status']:<15} ${r['alms_balance']:>13.2f} ${r['lms_balance']:>13.2f}")
        total_to_writedown += r['alms_balance']
    
    print("-" * 100)
    print(f"Count: {len(already_fixed_in_lms)}")
    print(f"Total to write down in almsdata: ${total_to_writedown:,.2f}")
    print()
    
    print("=" * 100)
    print("NOT YET FIXED IN LMS (both systems show balance)")
    print("=" * 100)
    print(f"{'Reserve':<12} {'Date':<12} {'Status':<15} {'ALMS Balance':<15} {'LMS Balance':<15}")
    print("-" * 100)
    
    for r in not_fixed_in_lms[:20]:  # Show top 20
        print(f"{r['reserve']:<12} {r['date']:<12} {r['status']:<15} ${r['alms_balance']:>13.2f} ${r['lms_balance']:>13.2f}")
    
    if len(not_fixed_in_lms) > 20:
        print(f"... and {len(not_fixed_in_lms) - 20} more")
    
    print("-" * 100)
    print(f"Count: {len(not_fixed_in_lms)}")
    print()
    
    print(f"SUMMARY:")
    print(f"  Total pre-2025 receivables: {len(receivables)}")
    print(f"  Already fixed in LMS: {len(already_fixed_in_lms)} (need almsdata write-down)")
    print(f"  Not fixed in LMS: {len(not_fixed_in_lms)} (need review/write-off in both systems)")


if __name__ == "__main__":
    main()
