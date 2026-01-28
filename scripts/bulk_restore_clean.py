#!/usr/bin/env python3
"""
Clean approach: delete all existing charges for the 8,504 candidates, 
then bulk insert fresh LMS charges for all of them.
This avoids duplicates and ensures clean data.
"""

import csv
import os
from datetime import datetime
import psycopg2
import pyodbc

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

LMS_PATH = r"L:\limo\backups\lms.mdb"

CANDIDATES_CSV = r"L:\limo\reports\CANDIDATES_FOR_CHARGE_RESTORE.csv"
OUTPUT_LOG = r"L:\limo\reports\BULK_RESTORE_CLEAN.log"


def get_lms_charges(reserve_number, lms_cur):
    """Fetch all charges for a reserve from LMS."""
    charges = []
    try:
        lms_cur.execute("SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
        
        reserve_field = None
        amount_field = None
        desc_field = None
        
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
            if "desc" in cl:
                desc_field = col
        
        if not reserve_field or not amount_field:
            return charges
        
        desc_select = f"[{desc_field}]" if desc_field else "NULL"
        lms_cur.execute(
            f"SELECT [{amount_field}], {desc_select} FROM Charge WHERE [{reserve_field}] = ? ORDER BY Amount DESC",
            (reserve_number,)
        )
        
        for row in lms_cur.fetchall():
            amount = float(row[0] or 0)
            desc = (str(row[1]).strip() if row[1] is not None else "") if len(row) > 1 else ""
            charges.append({"amount": amount, "description": desc[:200]})
    except Exception as e:
        pass
    
    return charges


def main():
    alms_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    lms_conn = pyodbc.connect(lms_conn_str)
    
    alms_cur = alms_conn.cursor()
    lms_cur = lms_conn.cursor()
    
    log_lines = []
    
    # Read candidates
    with open(CANDIDATES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        candidates = list(reader)
    
    log_lines.append(f"Starting clean bulk restore of {len(candidates)} candidates at {datetime.now()}")
    
    # Step 1: Delete existing charges for all candidates
    reserves_list = [c['reserve'] for c in candidates]
    placeholders = ','.join(['%s'] * len(reserves_list))
    
    try:
        alms_cur.execute(f"DELETE FROM charter_charges WHERE reserve_number IN ({placeholders})", reserves_list)
        alms_conn.commit()
        deleted_count = alms_cur.rowcount
        log_lines.append(f"Deleted {deleted_count} existing charges for {len(candidates)} reserves")
    except Exception as e:
        log_lines.append(f"ERROR during delete: {e}")
        alms_conn.close()
        lms_conn.close()
        return
    
    # Step 2: Bulk insert fresh LMS charges
    inserted = 0
    failed = 0
    total_amount = 0.0
    
    now = datetime.utcnow().isoformat()
    
    for i, row in enumerate(candidates, 1):
        reserve = row['reserve']
        
        if i % 500 == 0:
            log_lines.append(f"  Processing {i}/{len(candidates)}...")
        
        # Get charter_id
        try:
            alms_cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
            charter_row = alms_cur.fetchone()
            if not charter_row:
                failed += 1
                continue
            charter_id = charter_row[0]
        except Exception as e:
            failed += 1
            continue
        
        # Get LMS charges
        try:
            lms_charges = get_lms_charges(reserve, lms_cur)
            if not lms_charges:
                failed += 1
                continue
        except Exception as e:
            failed += 1
            continue
        
        # Insert charges
        sql = (
            "INSERT INTO charter_charges (reserve_number, charter_id, amount, gst_amount, description, created_at, last_updated_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)"
        )
        
        try:
            for charge in lms_charges:
                alms_cur.execute(
                    sql,
                    (reserve, charter_id, charge['amount'], 0.0, charge['description'], now, 'bulk_restore_clean')
                )
            
            # Update charter total
            charges_sum = sum(c['amount'] for c in lms_charges)
            alms_cur.execute(
                "UPDATE charters SET total_amount_due = %s WHERE charter_id = %s",
                (charges_sum, charter_id)
            )
            
            alms_conn.commit()
            inserted += 1
            total_amount += charges_sum
        except Exception as e:
            alms_conn.rollback()
            failed += 1
    
    log_lines.append(f"Completed at {datetime.now()}")
    log_lines.append(f"Inserted: {inserted}")
    log_lines.append(f"Failed: {failed}")
    log_lines.append(f"Total amount restored: ${total_amount:,.2f}")
    
    # Write log
    with open(OUTPUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
    
    alms_cur.close()
    alms_conn.close()
    lms_cur.close()
    lms_conn.close()
    
    # Print summary
    for line in log_lines[-5:]:
        print(line)
    print(f"Log: {OUTPUT_LOG}")


if __name__ == "__main__":
    main()
