#!/usr/bin/env python
"""Propose GL code remapping for GL 6900 entries."""
import psycopg2, os

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD','***REMOVED***')

# Mapping proposal: GL 6900 → proper GL codes
GL_MAPPINGS = {
    'Unknown': '9999',  # Keep unknown as 9999 (miscellaneous/review needed)
    'Banking': '5400',  # Bank fees & transfers → GL 5400 (Bank Charges)
    'Driver Payment': '5000',  # Driver payments → GL 5000 (Salary & Wages)
    'Income - Card Payments': '4100',  # Card revenue → GL 4100 (Revenue - Card Payments)
    '(uncategorized)': '9999',  # Uncategorized → 9999
    'Taxes': '2200',  # Tax accruals → GL 2200 (Accrued Taxes)
    'Office Staff': '5100',  # Office staff → GL 5100 (Office Salaries)
    'Accounting': '6200',  # Accounting → GL 6200 (Professional Services)
    'Personal Draws': '3500',  # Owner draws → GL 3500 (Owner Draws)
    'Bank Fees': '5400',  # Bank fees → GL 5400 (Bank Charges)
}

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("=" * 100)
    print("GL 6900 REMAPPING PROPOSAL")
    print("=" * 100)
    
    total_remapped = 0
    for cat, new_gl in GL_MAPPINGS.items():
        if cat == '(uncategorized)':
            cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '6900' AND category IS NULL")
        else:
            cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '6900' AND category = %s", (cat,))
        cnt = cur.fetchone()[0]
        total_remapped += cnt
        print(f"\n{cnt:4d} receipts | {cat:25s} → GL {new_gl}")
    
    print(f"\n{'=' * 100}")
    print(f"Total to remap: {total_remapped}")
    
    print("\n⚠️ NOTE: GL 9999 entries should be reviewed before finalizing")
    cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '6900' AND category = 'Unknown'")
    unknown_count = cur.fetchone()[0]
    print(f"   {unknown_count} Unknown entries need manual review/categorization")
    
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
