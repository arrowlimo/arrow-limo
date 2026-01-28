#!/usr/bin/env python3
"""
Verify clean bulk restore worked: 
- Charges in almsdata match LMS
- Balances are ~0 for all candidates
- Sample verification across full dataset
"""

import csv
import random
import psycopg2
import pyodbc

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

LMS_PATH = r"L:\limo\backups\lms.mdb"

CANDIDATES_CSV = r"L:\limo\reports\CANDIDATES_FOR_CHARGE_RESTORE.csv"
OUTPUT_VERIFY = r"L:\limo\reports\VERIFY_BULK_RESTORE.csv"


def get_almsdata_state(reserve, alms_cur):
    """Get current almsdata charges and payments."""
    alms_cur.execute("""
        SELECT 
            COALESCE(SUM(cc.amount), 0) as charges_total,
            COALESCE(SUM(p.amount), 0) as payments_total
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.reserve_number = c.reserve_number
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number = %s
    """, (reserve,))
    
    row = alms_cur.fetchone()
    if not row:
        return None
    
    charges_total, payments_total = row
    balance = float(charges_total or 0) - float(payments_total or 0)
    
    return {
        'charges': float(charges_total or 0),
        'payments': float(payments_total or 0),
        'balance': balance
    }


def get_lms_state(reserve, lms_cur):
    """Get LMS charges and payments."""
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
    
    balance = charges - payments
    
    return {
        'charges': charges,
        'payments': payments,
        'balance': balance
    }


def main():
    alms_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    lms_conn = pyodbc.connect(lms_conn_str)
    
    alms_cur = alms_conn.cursor()
    lms_cur = lms_conn.cursor()
    
    # Read all candidates
    with open(CANDIDATES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        candidates = list(reader)
    
    print(f"Verifying {len(candidates)} restored charters...")
    print()
    
    # Sample: stratified across dataset (first 20, middle 20, last 20, plus 40 random)
    sample_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]  # First 20
    mid = len(candidates) // 2
    sample_indices += list(range(mid - 10, mid + 10))  # Middle 20
    sample_indices += list(range(len(candidates) - 20, len(candidates)))  # Last 20
    sample_indices += random.sample(range(20, len(candidates) - 20), min(40, len(candidates) - 40))  # Random 40
    sample_indices = list(set(sample_indices))[:100]  # Dedupe, limit to 100
    
    verified = []
    ok_count = 0
    mismatch_count = 0
    zero_balance_count = 0
    
    for idx in sorted(sample_indices):
        candidate = candidates[idx]
        reserve = candidate['reserve']
        
        alms = get_almsdata_state(reserve, alms_cur)
        lms = get_lms_state(reserve, lms_cur)
        
        if not alms or not lms:
            continue
        
        # Check if charges match and balance is ~0
        charges_match = abs(alms['charges'] - lms['charges']) < 0.01
        balance_zero = abs(alms['balance']) < 0.01
        
        status = 'OK' if (charges_match and balance_zero) else 'MISMATCH'
        if status == 'OK':
            ok_count += 1
        else:
            mismatch_count += 1
        
        if balance_zero:
            zero_balance_count += 1
        
        verified.append({
            'reserve': reserve,
            'alms_charges': alms['charges'],
            'lms_charges': lms['charges'],
            'charges_match': charges_match,
            'alms_payments': alms['payments'],
            'alms_balance': alms['balance'],
            'lms_balance': lms['balance'],
            'balance_zero': balance_zero,
            'status': status
        })
    
    # Write results
    with open(OUTPUT_VERIFY, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['reserve', 'alms_charges', 'lms_charges', 'charges_match', 'alms_payments', 'alms_balance', 'lms_balance', 'balance_zero', 'status']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in verified:
            writer.writerow(v)
    
    # Summary
    print(f"Sample verification ({len(verified)} out of {len(candidates)}):")
    print(f"  OK (charges match + balance ~0): {ok_count}")
    print(f"  Mismatches: {mismatch_count}")
    print(f"  Zero balance: {zero_balance_count}/{len(verified)}")
    print()
    
    if mismatch_count > 0:
        print("Mismatches found:")
        for v in verified:
            if v['status'] != 'OK':
                print(f"  {v['reserve']} | alms_charges={v['alms_charges']:.2f} vs lms={v['lms_charges']:.2f} | balance={v['alms_balance']:+.2f}")
    else:
        print("✅ All samples verified - charges match LMS and balances are ~0")
    
    print()
    print(f"Details: {OUTPUT_VERIFY}")
    
    alms_cur.close()
    alms_conn.close()
    lms_cur.close()
    lms_conn.close()


if __name__ == "__main__":
    main()
