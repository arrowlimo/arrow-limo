#!/usr/bin/env python3
"""
Bulk restore LMS charges into almsdata for 8,504 candidates.
- Idempotent: skips reserves that already have charges
- Reads candidates from CANDIDATES_FOR_CHARGE_RESTORE.csv
- Fetches LMS charges via pyodbc
- Inserts into almsdata charter_charges
- Updates charters.total_amount_due to match LMS totals
"""

import csv
import os
import sys
from datetime import datetime
import psycopg2
import pyodbc

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

LMS_PATH = r"L:\limo\backups\lms.mdb"

CANDIDATES_CSV = r"L:\limo\reports\CANDIDATES_FOR_CHARGE_RESTORE.csv"
OUTPUT_LOG = r"L:\limo\reports\BULK_RESTORE_LMS_CHARGES.log"


def get_lms_charges(reserve_number, lms_conn):
    """Fetch all charges for a reserve from LMS."""
    cur = lms_conn.cursor()
    charges = []
    try:
        # Introspect Charge table columns
        cur.execute("SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in cur.description] if cur.description else []
        
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
        
        # Fetch charges
        desc_select = f"[{desc_field}]" if desc_field else "NULL"
        cur.execute(
            f"SELECT [{amount_field}], {desc_select} FROM Charge WHERE [{reserve_field}] = ? ORDER BY Amount DESC",
            (reserve_number,)
        )
        
        for row in cur.fetchall():
            amount = float(row[0] or 0)
            desc = (str(row[1]).strip() if row[1] is not None else "") if len(row) > 1 else ""
            charges.append({"amount": amount, "description": desc[:200]})
    except Exception as e:
        pass
    finally:
        cur.close()
    
    return charges


def main():
    # Connect to both databases
    try:
        alms_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
        lms_conn = pyodbc.connect(lms_conn_str)
    except Exception as e:
        print(f"Connection failed: {e}")
        return
    
    alms_cur = alms_conn.cursor()
    
    log_lines = []
    
    # Read candidates
    with open(CANDIDATES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        candidates = list(reader)
    
    log_lines.append(f"Starting bulk restore of {len(candidates)} candidates at {datetime.now()}")
    
    inserted = 0
    skipped = 0
    failed = 0
    total_restored_amount = 0.0
    
    for i, row in enumerate(candidates, 1):
        reserve = row['reserve']
        
        if i % 500 == 0:
            log_lines.append(f"  Processed {i}/{len(candidates)}...")
        
        # Check if charges already exist
        try:
            alms_cur.execute("SELECT COUNT(*) FROM charter_charges WHERE reserve_number = %s", (reserve,))
            existing = alms_cur.fetchone()[0]
            if existing:
                skipped += 1
                continue
        except Exception as e:
            log_lines.append(f"  ERROR checking {reserve}: {e}")
            failed += 1
            continue
        
        # Get charter_id
        try:
            alms_cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
            charter_row = alms_cur.fetchone()
            if not charter_row:
                log_lines.append(f"  SKIP {reserve}: no charter found")
                failed += 1
                continue
            charter_id = charter_row[0]
        except Exception as e:
            log_lines.append(f"  ERROR fetching charter {reserve}: {e}")
            failed += 1
            continue
        
        # Get LMS charges
        try:
            lms_charges = get_lms_charges(reserve, lms_conn)
            if not lms_charges:
                log_lines.append(f"  SKIP {reserve}: no LMS charges found")
                failed += 1
                continue
        except Exception as e:
            log_lines.append(f"  ERROR fetching LMS charges {reserve}: {e}")
            failed += 1
            continue
        
        # Insert charges into almsdata
        now = datetime.utcnow().isoformat()
        sql = (
            "INSERT INTO charter_charges (reserve_number, charter_id, amount, gst_amount, description, created_at, last_updated_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)"
        )
        
        try:
            for charge in lms_charges:
                alms_cur.execute(
                    sql,
                    (reserve, charter_id, charge['amount'], 0.0, charge['description'], now, 'bulk_restore_lms')
                )
            
            # Update charter total_amount_due
            charges_sum = sum(c['amount'] for c in lms_charges)
            alms_cur.execute(
                "UPDATE charters SET total_amount_due = %s WHERE charter_id = %s",
                (charges_sum, charter_id)
            )
            
            alms_conn.commit()
            inserted += 1
            total_restored_amount += charges_sum
        except Exception as e:
            alms_conn.rollback()
            log_lines.append(f"  ERROR inserting charges {reserve}: {e}")
            failed += 1
    
    log_lines.append(f"Completed at {datetime.now()}")
    log_lines.append(f"Inserted: {inserted}")
    log_lines.append(f"Skipped (already exist): {skipped}")
    log_lines.append(f"Failed: {failed}")
    log_lines.append(f"Total amount restored: ${total_restored_amount:,.2f}")
    
    # Write log
    with open(OUTPUT_LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
    
    alms_cur.close()
    alms_conn.close()
    lms_conn.close()
    
    # Print summary
    for line in log_lines[-5:]:
        print(line)
    print(f"Log: {OUTPUT_LOG}")


if __name__ == "__main__":
    main()
