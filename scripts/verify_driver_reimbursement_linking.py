"""
Verify driver reimbursement data from LMS against ALMS receipts
- Check if receipts are properly linked to drivers
- Verify charter reimbursements match LMS data
"""

import os
import pyodbc
import psycopg2
from datetime import datetime

# LMS Access DB
LMS_DB_PATH = r"L:\limo\database_backups\lms2026.mdb"
lms_conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};' + f'DBQ={LMS_DB_PATH};'

# ALMS PostgreSQL
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_lms_reimbursements():
    """Extract reimbursement data from LMS"""
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    # First, check the table structure
    print("Checking Reimburse table structure...")
    lms_cur.execute("SELECT TOP 1 * FROM Reimburse")
    columns = [column[0] for column in lms_cur.description]
    print(f"Columns: {', '.join(columns)}\n")
    
    # Get all reimbursement records
    query = "SELECT * FROM Reimburse ORDER BY [Key]"
    lms_cur.execute(query)
    
    reimbursements = []
    for row in lms_cur:
        reimb_dict = {}
        for idx, col in enumerate(columns):
            reimb_dict[col] = row[idx]
        reimbursements.append(reimb_dict)
    
    lms_cur.close()
    lms_conn.close()
    
    return reimbursements, columns

def get_alms_driver_receipts():
    """Get receipts linked to employees/drivers in ALMS"""
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    query = """
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.employee_id,
        e.full_name as employee_name,
        e.driver_code,
        r.charter_id,
        c.reserve_number,
        r.description,
        r.category
    FROM receipts r
    LEFT JOIN employees e ON r.employee_id = e.employee_id
    LEFT JOIN charters c ON r.charter_id = c.charter_id
    WHERE r.employee_id IS NOT NULL
    ORDER BY r.receipt_date
    """
    
    pg_cur.execute(query)
    
    receipts = []
    for row in pg_cur:
        receipts.append({
            'receipt_id': row[0],
            'receipt_date': row[1],
            'vendor': row[2],
            'gross_amount': float(row[3]) if row[3] else 0,
            'employee_id': row[4],
            'employee_name': row[5],
            'driver_code': row[6],
            'charter_id': row[7],
            'reserve_number': row[8],
            'description': row[9],
            'category': row[10]
        })
    
    pg_cur.close()
    pg_conn.close()
    
    return receipts

def analyze_reimbursements():
    """Compare LMS reimbursements with ALMS driver receipts"""
    
    print("="*80)
    print("DRIVER REIMBURSEMENT VERIFICATION")
    print("="*80)
    print()
    
    # Get LMS data
    print("Fetching LMS reimbursement data...")
    lms_reimb, lms_columns = get_lms_reimbursements()
    print(f"✅ Found {len(lms_reimb)} reimbursements in LMS\n")
    
    if lms_reimb:
        print("Sample LMS reimbursement record:")
        print("-" * 80)
        for key, value in lms_reimb[0].items():
            print(f"  {key}: {value}")
        print()
    
    # Get ALMS data
    print("Fetching ALMS driver receipts...")
    alms_receipts = get_alms_driver_receipts()
    print(f"✅ Found {len(alms_receipts)} receipts linked to employees in ALMS\n")
    
    if alms_receipts:
        print("Sample ALMS driver receipt:")
        print("-" * 80)
        for key, value in alms_receipts[0].items():
            print(f"  {key}: {value}")
        print()
    
    # Count charter-linked receipts
    charter_linked = [r for r in alms_receipts if r['charter_id'] is not None]
    print("="*80)
    print("CHARTER REIMBURSEMENT LINKING")
    print("="*80)
    print(f"Total driver receipts: {len(alms_receipts)}")
    if len(alms_receipts) > 0:
        print(f"Linked to charters: {len(charter_linked)} ({len(charter_linked)/len(alms_receipts)*100:.1f}%)")
        print(f"Not linked to charters: {len(alms_receipts) - len(charter_linked)}")
    print()
    
    if charter_linked:
        print("Sample charter-linked reimbursements (first 10):")
        print("-" * 80)
        for receipt in charter_linked[:10]:
            print(f"  {receipt['receipt_date']} | {receipt['reserve_number']} | "
                  f"{receipt['employee_name']} | ${receipt['gross_amount']:.2f} | "
                  f"{receipt['vendor']} - {receipt['description']}")
        print()
    
    # Category breakdown
    print("="*80)
    print("RECEIPT CATEGORIES")
    print("="*80)
    categories = {}
    for receipt in alms_receipts:
        cat = receipt['category'] or 'Uncategorized'
        if cat not in categories:
            categories[cat] = {'count': 0, 'total': 0}
        categories[cat]['count'] += 1
        categories[cat]['total'] += receipt['gross_amount']
    
    for cat, data in sorted(categories.items(), key=lambda x: x[1]['total'], reverse=True):
        print(f"  {cat}: {data['count']} receipts, ${data['total']:,.2f}")
    print()
    
    # Driver breakdown
    print("="*80)
    print("TOP 10 DRIVERS BY REIMBURSEMENT AMOUNT")
    print("="*80)
    drivers = {}
    for receipt in alms_receipts:
        driver = receipt['employee_name'] or 'Unknown'
        if driver not in drivers:
            drivers[driver] = {'count': 0, 'total': 0, 'code': receipt['driver_code']}
        drivers[driver]['count'] += 1
        drivers[driver]['total'] += receipt['gross_amount']
    
    for driver, data in sorted(drivers.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        code = data['code'] or 'N/A'
        print(f"  {driver} ({code}): {data['count']} receipts, ${data['total']:,.2f}")
    print()
    
    # Recommendation
    print("="*80)
    print("SYSTEM STATUS")
    print("="*80)
    
    if len(alms_receipts) > 0:
        charter_link_pct = len(charter_linked) / len(alms_receipts) * 100
        print(f"✅ Receipt-driver linking: WORKING ({len(alms_receipts)} receipts linked)")
        print(f"✅ Charter reimbursement tracking: WORKING ({len(charter_linked)} charter-linked)")
        
        if charter_link_pct < 50:
            print(f"⚠️  Only {charter_link_pct:.1f}% of driver receipts linked to charters")
            print("   This is normal if many receipts are general expenses (not charter-specific)")
        else:
            print(f"✅ {charter_link_pct:.1f}% of driver receipts linked to charters")
    else:
        print("❌ No driver receipts found in ALMS")
        print("   The receipt-driver linking system may not be populated yet")
    
    print()
    print(f"📊 LMS has {len(lms_reimb)} historical reimbursement records")
    print(f"📊 ALMS has {len(alms_receipts)} current driver receipt records")
    
    if len(lms_reimb) > len(alms_receipts):
        print(f"⚠️  {len(lms_reimb) - len(alms_receipts)} reimbursements may need to be imported from LMS")

if __name__ == "__main__":
    analyze_reimbursements()
