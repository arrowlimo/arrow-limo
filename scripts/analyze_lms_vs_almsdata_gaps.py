#!/usr/bin/env python3
"""
LMS vs ALMSDATA Gap Analysis
Identifies missing/different data between LMS2026 staging and production almsdata
"""
import psycopg2
from datetime import datetime

PG_HOST = "localhost"
PG_DB = "almsdata"
PG_USER = "postgres"
PG_PASSWORD = "***REDACTED***"

def connect():
    return psycopg2.connect(host=PG_HOST, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)

def analyze_reserve_gaps():
    """Find charters that exist in LMS but not in almsdata or have differences"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("CHARTER GAPS ANALYSIS (LMS → ALMSDATA)")
    print("=" * 80)
    
    # Missing charters
    cur.execute("""
        SELECT COUNT(*)
        FROM lms2026_reserves lms
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = lms.reserve_no
        )
    """)
    missing_count = cur.fetchone()[0]
    print(f"\n1. Charters in LMS but NOT in almsdata: {missing_count:,}")
    
    if missing_count > 0:
        cur.execute("""
            SELECT lms.reserve_no, lms.account_no, lms.pu_date, lms.client_name, lms.total, lms.status
            FROM lms2026_reserves lms
            WHERE NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = lms.reserve_no
            )
            ORDER BY lms.pu_date DESC
            LIMIT 20
        """)
        print("\n  Sample missing charters:")
        for row in cur.fetchall():
            total = row[4] if row[4] is not None else 0.0
            name = (row[3] or '')[:30]
            status = row[5] or 'N/A'
            print(f"    {row[0]} | {row[1]} | {row[2]} | {name:30} | ${total:,.2f} | {status}")
    
    # Amount discrepancies
    cur.execute("""
        SELECT COUNT(*)
        FROM lms2026_reserves lms
        JOIN charters c ON c.reserve_number = lms.reserve_no
        WHERE ABS(COALESCE(lms.total, 0) - COALESCE(c.total_amount_due, 0)) > 0.02
    """)
    amount_diff = cur.fetchone()[0]
    print(f"\n2. Charters with different totals (LMS ≠ almsdata): {amount_diff:,}")
    
    if amount_diff > 0:
        cur.execute("""
            SELECT c.reserve_number, lms.total as lms_total, c.total_amount_due as alms_total,
                   lms.total - c.total_amount_due as difference
            FROM lms2026_reserves lms
            JOIN charters c ON c.reserve_number = lms.reserve_no
            WHERE ABS(COALESCE(lms.total, 0) - COALESCE(c.total_amount_due, 0)) > 0.02
            ORDER BY ABS(lms.total - c.total_amount_due) DESC
            LIMIT 20
        """)
        print("\n  Top amount discrepancies:")
        for row in cur.fetchall():
            lms_total = row[1] if row[1] is not None else 0.0
            alms_total = row[2] if row[2] is not None else 0.0
            diff = row[3] if row[3] is not None else 0.0
            print(f"    {row[0]} | LMS: ${lms_total:,.2f} | ALMS: ${alms_total:,.2f} | Diff: ${diff:,.2f}")
    
    # Balance discrepancies
    cur.execute("""
        SELECT COUNT(*)
        FROM lms2026_reserves lms
        JOIN charters c ON c.reserve_number = lms.reserve_no
        WHERE ABS(COALESCE(lms.balance, 0) - COALESCE(c.balance, 0)) > 0.02
    """)
    balance_diff = cur.fetchone()[0]
    print(f"\n3. Charters with different balances (LMS ≠ almsdata): {balance_diff:,}")
    
    # Status differences
    cur.execute("""
        SELECT COUNT(*)
        FROM lms2026_reserves lms
        JOIN charters c ON c.reserve_number = lms.reserve_no
        WHERE LOWER(COALESCE(lms.status, '')) != LOWER(COALESCE(c.status, ''))
    """)
    status_diff = cur.fetchone()[0]
    print(f"\n4. Charters with different status (LMS ≠ almsdata): {status_diff:,}")
    
    conn.close()

def analyze_payment_gaps():
    """Find payments in LMS but not in almsdata"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("PAYMENT GAPS ANALYSIS (LMS → ALMSDATA)")
    print("=" * 80)
    
    # Missing payments
    cur.execute("""
        SELECT COUNT(*), SUM(lms.amount)
        FROM lms2026_payments lms
        WHERE lms.reserve_no IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.reserve_number = lms.reserve_no
              AND ABS(p.amount - lms.amount) < 0.02
          )
    """)
    row = cur.fetchone()
    missing_count, missing_amount = row[0], row[1] or 0
    print(f"\n1. Payments in LMS but NOT matched in almsdata: {missing_count:,} (${missing_amount:,.2f})")
    
    if missing_count > 0:
        cur.execute("""
            SELECT lms.reserve_no, lms.payment_date, lms.amount, lms.payment_method
            FROM lms2026_payments lms
            WHERE lms.reserve_no IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.reserve_number = lms.reserve_no
                  AND ABS(p.amount - lms.amount) < 0.02
              )
            ORDER BY lms.payment_date DESC
            LIMIT 20
        """)
        print("\n  Sample missing payments:")
        for row in cur.fetchall():
            amount = row[2] if row[2] is not None else 0.0
            method = row[3] or 'N/A'
            print(f"    {row[0]} | {row[1]} | ${amount:,.2f} | {method}")
    
    # Payment totals comparison
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            SUM(lms_total) as lms_total,
            SUM(alms_total) as alms_total,
            SUM(lms_total - alms_total) as difference
        FROM (
            SELECT 
                lms.reserve_no,
                SUM(lms.amount) as lms_total,
                COALESCE((
                    SELECT SUM(p.amount) 
                    FROM payments p 
                    WHERE p.reserve_number = lms.reserve_no
                ), 0) as alms_total
            FROM lms2026_payments lms
            WHERE lms.reserve_no IS NOT NULL
            GROUP BY lms.reserve_no
        ) comparison
        WHERE ABS(lms_total - alms_total) > 0.02
    """)
    row = cur.fetchone()
    if row and row[0]:
        print(f"\n2. Charters with payment total mismatches: {row[0]:,}")
        print(f"   LMS total: ${row[1]:,.2f}")
        print(f"   ALMS total: ${row[2]:,.2f}")
        print(f"   Difference: ${row[3]:,.2f}")
    
    conn.close()

def analyze_charge_gaps():
    """Find charges in LMS but not in almsdata"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("CHARGE GAPS ANALYSIS (LMS → ALMSDATA)")
    print("=" * 80)
    
    # Missing charges
    cur.execute("""
        SELECT COUNT(*), SUM(lms.amount)
        FROM lms2026_charges lms
        WHERE lms.reserve_no IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM charter_charges cc 
            JOIN charters c ON c.charter_id = cc.charter_id
            WHERE c.reserve_number = lms.reserve_no
              AND cc.description = lms.description
              AND ABS(cc.amount - lms.amount) < 0.02
          )
    """)
    row = cur.fetchone()
    missing_count, missing_amount = row[0], row[1] or 0
    print(f"\n1. Charges in LMS but NOT in almsdata: {missing_count:,} (${missing_amount:,.2f})")
    
    if missing_count > 0:
        cur.execute("""
            SELECT lms.reserve_no, lms.description, lms.amount, lms.is_closed
            FROM lms2026_charges lms
            WHERE lms.reserve_no IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM charter_charges cc 
                JOIN charters c ON c.charter_id = cc.charter_id
                WHERE c.reserve_number = lms.reserve_no
                  AND cc.description = lms.description
                  AND ABS(cc.amount - lms.amount) < 0.02
              )
            ORDER BY lms.amount DESC
            LIMIT 20
        """)
        print("\n  Sample missing charges:")
        for row in cur.fetchall():
            closed = "CLOSED" if row[3] else "OPEN"
            amount = row[2] if row[2] is not None else 0.0
            desc = (row[1] or '')[:40]
            print(f"    {row[0]} | {desc:40} | ${amount:,.2f} | {closed}")
    
    # Cancelled charges that should be removed
    cur.execute("""
        SELECT COUNT(*), SUM(lms.amount)
        FROM lms2026_charges lms
        JOIN lms2026_reserves r ON r.reserve_no = lms.reserve_no
        WHERE r.status IN ('Cancelled', 'Cancel')
          AND lms.is_closed = FALSE
    """)
    row = cur.fetchone()
    cancelled_charges = row[0] or 0
    if cancelled_charges > 0:
        print(f"\n2. Charges on CANCELLED charters (should be closed): {cancelled_charges:,} (${row[1]:,.2f})")
    
    conn.close()

def analyze_customer_gaps():
    """Find customers in LMS but not in almsdata"""
    conn = connect()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("CUSTOMER GAPS ANALYSIS (LMS → ALMSDATA)")
    print("=" * 80)
    
    # Missing customers
    cur.execute("""
        SELECT COUNT(*)
        FROM lms2026_customers lms
        WHERE NOT EXISTS (
            SELECT 1 FROM clients c WHERE c.account_number = lms.account_no
        )
    """)
    missing_count = cur.fetchone()[0]
    print(f"\n1. Customers in LMS but NOT in almsdata: {missing_count:,}")
    
    if missing_count > 0:
        cur.execute("""
            SELECT lms.account_no, lms.primary_name, lms.company_name, lms.email, lms.cell_phone
            FROM lms2026_customers lms
            WHERE NOT EXISTS (
                SELECT 1 FROM clients c WHERE c.account_number = lms.account_no
            )
            LIMIT 20
        """)
        print("\n  Sample missing customers:")
        for row in cur.fetchall():
            name = (row[1] or '')[:30]
            company = (row[2] or 'N/A')[:30]
            email = (row[3] or 'N/A')[:30]
            print(f"    {row[0]} | {name:30} | {company:30} | {email:30}")
    
    # Email mismatches
    cur.execute("""
        SELECT COUNT(*)
        FROM lms2026_customers lms
        JOIN clients c ON c.account_number = lms.account_no
        WHERE LOWER(COALESCE(lms.email, '')) != LOWER(COALESCE(c.email, ''))
          AND lms.email IS NOT NULL
          AND lms.email != ''
    """)
    email_diff = cur.fetchone()[0]
    if email_diff > 0:
        print(f"\n2. Customers with different emails (LMS has newer data): {email_diff:,}")
    
    conn.close()

def generate_summary_report():
    """Create comprehensive gap analysis report"""
    conn = connect()
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"reports/LMS_ALMSDATA_GAP_ANALYSIS_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("LMS 2026 vs ALMSDATA GAP ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Record counts
        f.write("STAGING TABLE COUNTS:\n")
        f.write("-" * 80 + "\n")
        tables = ['lms2026_reserves', 'lms2026_payments', 'lms2026_charges', 'lms2026_customers']
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            f.write(f"  {table:30} {count:,}\n")
        
        f.write("\n\nALMSDATA TABLE COUNTS:\n")
        f.write("-" * 80 + "\n")
        tables = ['charters', 'payments', 'charter_charges', 'clients']
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            f.write(f"  {table:30} {count:,}\n")
        
        # Detailed gap lists
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("DETAILED GAP ANALYSIS\n")
        f.write("=" * 80 + "\n")
        
        # Missing charters
        f.write("\nMISSING CHARTERS (in LMS, not in almsdata):\n")
        f.write("-" * 80 + "\n")
        cur.execute("""
            SELECT lms.reserve_no, lms.pu_date, lms.client_name, lms.total, lms.status
            FROM lms2026_reserves lms
            WHERE NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = lms.reserve_no
            )
            ORDER BY lms.pu_date DESC
        """)
        for row in cur.fetchall():
            total = row[3] if row[3] is not None else 0.0
            status = row[4] or 'N/A'
            f.write(f"  {row[0]} | {row[1]} | {row[2][:40]:40} | ${total:,.2f} | {status}\n")
        
        # Amount mismatches
        f.write("\n\nAMOUNT MISMATCHES (LMS total ≠ almsdata total):\n")
        f.write("-" * 80 + "\n")
        cur.execute("""
            SELECT c.reserve_number, lms.total, c.total_amount_due, lms.total - c.total_amount_due
            FROM lms2026_reserves lms
            JOIN charters c ON c.reserve_number = lms.reserve_no
            WHERE ABS(lms.total - c.total_amount_due) > 0.02
            ORDER BY ABS(lms.total - c.total_amount_due) DESC
        """)
        for row in cur.fetchall():
            lms_amt = row[1] if row[1] is not None else 0.0
            alms_amt = row[2] if row[2] is not None else 0.0
            diff = row[3] if row[3] is not None else 0.0
            f.write(f"  {row[0]} | LMS: ${lms_amt:,.2f} | ALMS: ${alms_amt:,.2f} | Diff: ${diff:,.2f}\n")
    
    conn.close()
    print(f"\n✅ Report saved: {report_file}")

def main():
    print("=" * 80)
    print("LMS 2026 vs ALMSDATA GAP ANALYSIS")
    print("=" * 80)
    
    analyze_reserve_gaps()
    analyze_payment_gaps()
    analyze_charge_gaps()
    analyze_customer_gaps()
    generate_summary_report()
    
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("  1. Review the gap analysis report in reports/")
    print("  2. Decide which gaps to fill:")
    print("     - Missing charters: Import if legitimate bookings")
    print("     - Amount mismatches: Verify which is correct (LMS or almsdata)")
    print("     - Missing payments: Import to fix receivables")
    print("     - Cancelled charges: Close in almsdata to match LMS")
    print("  3. Run: python scripts/merge_lms_to_almsdata.py --dry-run")

if __name__ == "__main__":
    main()
