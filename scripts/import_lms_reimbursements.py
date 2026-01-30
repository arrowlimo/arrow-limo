"""
Import LMS reimbursement data to populate driver-receipt linking
- Creates receipts linked to employees and charters
- Establishes charter reimbursement tracking system
"""

import os
import pyodbc
import psycopg2
from datetime import datetime
from decimal import Decimal

# LMS Access DB
LMS_DB_PATH = r"L:\limo\database_backups\lms2026.mdb"
lms_conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};' + f'DBQ={LMS_DB_PATH};'

# ALMS PostgreSQL
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_driver_mapping():
    """Get driver_code to employee_id mapping from ALMS"""
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    # Get LMS driver codes
    pg_cur.execute("""
        SELECT DISTINCT driver_code 
        FROM lms2026_reserves 
        WHERE driver_code IS NOT NULL
    """)
    lms_codes = {row[0] for row in pg_cur.fetchall()}
    
    # Map to ALMS employee IDs
    driver_map = {}
    for lms_code in lms_codes:
        # Try exact match first
        pg_cur.execute("""
            SELECT employee_id, driver_code, full_name
            FROM employees
            WHERE driver_code = %s
        """, (lms_code.upper().replace('DR', 'DR'),))
        
        result = pg_cur.fetchone()
        if not result:
            # Try normalized match (Dr06 -> DR006)
            normalized = lms_code.upper().replace('DR', 'DR')
            if len(normalized) == 4:  # Dr06
                normalized = 'DR' + normalized[2:].zfill(3)  # DR006
            
            pg_cur.execute("""
                SELECT employee_id, driver_code, full_name
                FROM employees
                WHERE driver_code = %s
            """, (normalized,))
            result = pg_cur.fetchone()
        
        if result:
            driver_map[lms_code] = {
                'employee_id': result[0],
                'driver_code': result[1],
                'name': result[2]
            }
    
    pg_cur.close()
    pg_conn.close()
    
    return driver_map

def get_charter_mapping():
    """Get reserve_number to charter_id mapping"""
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    pg_cur.execute("""
        SELECT reserve_number, charter_id
        FROM charters
        WHERE reserve_number IS NOT NULL
    """)
    
    charter_map = {row[0]: row[1] for row in pg_cur.fetchall()}
    
    pg_cur.close()
    pg_conn.close()
    
    return charter_map

def import_reimbursements(dry_run=True):
    """Import LMS reimbursements as receipts"""
    
    print("="*80)
    print("LMS REIMBURSEMENT IMPORT")
    print("="*80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE IMPORT'}")
    print()
    
    # Get mappings
    print("Building driver mapping...")
    driver_map = get_driver_mapping()
    print(f"✅ Mapped {len(driver_map)} drivers\n")
    
    print("Building charter mapping...")
    charter_map = get_charter_mapping()
    print(f"✅ Mapped {len(charter_map)} charters\n")
    
    # Get LMS reimbursements
    print("Fetching LMS reimbursements...")
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    lms_cur.execute("""
        SELECT 
            AMOUNT,
            [DATE],
            NOTE,
            RESERVE_NO,
            TYPE
        FROM Reimburse
        ORDER BY [Key]
    """)
    
    reimbursements = lms_cur.fetchall()
    lms_cur.close()
    lms_conn.close()
    
    print(f"✅ Found {len(reimbursements)} reimbursements\n")
    
    # Process reimbursements
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    imported = 0
    skipped_no_driver = 0
    skipped_no_charter = 0
    skipped_duplicate = 0
    errors = []
    
    print("Processing reimbursements...")
    print("-" * 80)
    
    for reimb in reimbursements:
        amount = Decimal(str(reimb[0])) if reimb[0] else Decimal('0')
        receipt_date = reimb[1]
        note = reimb[2] or ''
        reserve_no = reimb[3]
        reimb_type = reimb[4] or 'Driver Reimbursement'
        
        # Get charter_id
        charter_id = charter_map.get(reserve_no)
        if not charter_id:
            skipped_no_charter += 1
            continue
        
        # Get employee_id from charter's assigned driver
        pg_cur.execute("""
            SELECT assigned_driver_id
            FROM charters
            WHERE charter_id = %s
        """, (charter_id,))
        
        result = pg_cur.fetchone()
        employee_id = result[0] if result and result[0] else None
        
        if not employee_id:
            skipped_no_driver += 1
            continue
        
        # Check for duplicate
        pg_cur.execute("""
            SELECT receipt_id
            FROM receipts
            WHERE charter_id = %s
              AND employee_id = %s
              AND receipt_date = %s
              AND gross_amount = %s
              AND description ILIKE %s
        """, (charter_id, employee_id, receipt_date, amount, f'%{reimb_type}%'))
        
        if pg_cur.fetchone():
            skipped_duplicate += 1
            continue
        
        # Insert receipt
        try:
            if not dry_run:
                pg_cur.execute("""
                    INSERT INTO receipts (
                        receipt_date,
                        vendor_name,
                        gross_amount,
                        gst_amount,
                        net_amount,
                        category,
                        description,
                        employee_id,
                        charter_id,
                        payment_method,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                """, (
                    receipt_date,
                    'Driver Reimbursement',
                    amount,
                    Decimal('0'),  # GST
                    amount,  # Net = gross for reimbursements
                    'Driver Expense',
                    f"{reimb_type}: {note}".strip(),
                    employee_id,
                    charter_id,
                    'reimbursement'
                ))
            
            imported += 1
            
            if imported <= 5:
                print(f"  ✅ {receipt_date} | {reserve_no} | ${amount:.2f} | {reimb_type}")
        
        except Exception as e:
            errors.append(f"{reserve_no}: {e}")
            if len(errors) <= 5:
                print(f"  ❌ {reserve_no}: {e}")
    
    if not dry_run:
        pg_conn.commit()
    
    pg_cur.close()
    pg_conn.close()
    
    # Summary
    print()
    print("="*80)
    print("IMPORT SUMMARY")
    print("="*80)
    print(f"Total LMS reimbursements: {len(reimbursements)}")
    print(f"✅ Imported: {imported}")
    print(f"⚠️  Skipped (no driver): {skipped_no_driver}")
    print(f"⚠️  Skipped (no charter): {skipped_no_charter}")
    print(f"⚠️  Skipped (duplicate): {skipped_duplicate}")
    print(f"❌ Errors: {len(errors)}")
    
    if not dry_run:
        print()
        print("✅ IMPORT COMPLETE - receipts committed to database")
    else:
        print()
        print("ℹ️  DRY RUN - no data written. Run with --write to commit.")

if __name__ == "__main__":
    import sys
    
    dry_run = '--write' not in sys.argv
    import_reimbursements(dry_run=dry_run)
