#!/usr/bin/env python3
"""
Fix decimal point errors in auto-generated receipts.
Amounts were imported 100x too large.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("FIXING DECIMAL POINT ERRORS IN AUTO-GENERATED RECEIPTS")
    print("="*80)
    
    # Find all auto-generated receipts with suspiciously large amounts
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            gst_amount,
            net_amount,
            gl_account_code
        FROM receipts
        WHERE (description ILIKE '%auto-generated from%banking%'
            OR description ILIKE '%auto-gen from banking%')
        AND gross_amount > 10000
        ORDER BY gross_amount DESC
    """)
    
    affected = cur.fetchall()
    
    print(f"\nFound {len(affected)} receipts with potential decimal errors")
    print(f"\nTop 20:")
    print("="*80)
    
    total_before = 0
    total_after = 0
    
    for i, receipt in enumerate(affected[:20], 1):
        receipt_id = receipt[0]
        date = receipt[1]
        vendor = (receipt[2] or 'Unknown')[:40]
        amount = float(receipt[3])
        gst = float(receipt[4] or 0)
        net = float(receipt[5] or 0)
        gl_code = receipt[6]
        
        corrected = amount / 100
        corrected_gst = gst / 100
        corrected_net = net / 100
        
        total_before += amount
        total_after += corrected
        
        print(f"{i:2d}. {date} | {vendor:40s}")
        print(f"    ${amount:12,.2f} → ${corrected:10,.2f} | GL: {gl_code}")
    
    print(f"\n{'='*80}")
    print(f"Total affected:")
    print(f"  Before: ${sum(float(r[3]) for r in affected):,.2f}")
    print(f"  After:  ${sum(float(r[3])/100 for r in affected):,.2f}")
    print(f"  Difference: ${sum(float(r[3]) for r in affected) - sum(float(r[3])/100 for r in affected):,.2f}")
    print(f"{'='*80}")
    
    # Show impact by GL code
    cur.execute("""
        SELECT 
            gl_account_code,
            COUNT(*) as count,
            SUM(gross_amount) as total_wrong,
            SUM(gross_amount) / 100 as total_corrected
        FROM receipts
        WHERE (description ILIKE '%auto-generated from%banking%'
            OR description ILIKE '%auto-gen from banking%')
        AND gross_amount > 10000
        GROUP BY gl_account_code
        ORDER BY SUM(gross_amount) DESC
    """)
    
    by_gl = cur.fetchall()
    
    print(f"\nImpact by GL Account:")
    print("="*80)
    
    for gl_data in by_gl:
        gl_code = gl_data[0] or 'NULL'
        count = gl_data[1]
        wrong = float(gl_data[2])
        corrected = float(gl_data[3])
        reduction = wrong - corrected
        
        print(f"{gl_code}: {count:4d} receipts | ${wrong:12,.2f} → ${corrected:10,.2f} (reduce ${reduction:,.2f})")
    
    print(f"\nApply corrections? (yes/no): ", end='')
    response = input().strip().lower()
    
    if response != 'yes':
        print("Cancelled")
        conn.close()
        return
    
    # Apply corrections
    print("\nApplying corrections...")
    
    cur.execute("""
        UPDATE receipts
        SET gross_amount = gross_amount / 100,
            gst_amount = gst_amount / 100,
            net_amount = net_amount / 100
        WHERE (description ILIKE '%auto-generated from%banking%'
            OR description ILIKE '%auto-gen from banking%')
        AND gross_amount > 10000
    """)
    
    updated = cur.rowcount
    conn.commit()
    
    print(f"✓ Corrected {updated:,} receipts")
    
    # Show new totals
    print(f"\n{'='*80}")
    print(f"CORRECTED 2012 EXPENSE TOTALS")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT 
            gl_account_code,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code ~ '^5'
        GROUP BY gl_account_code
        ORDER BY gl_account_code
    """)
    
    expenses = cur.fetchall()
    total_expenses = 0
    
    for expense in expenses:
        gl_code = expense[0]
        count = expense[1]
        amount = float(expense[2])
        total_expenses += amount
        print(f"{gl_code}: {count:5d} receipts = ${amount:12,.2f}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL 2012 EXPENSES: ${total_expenses:,.2f}")
    print(f"{'='*80}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
