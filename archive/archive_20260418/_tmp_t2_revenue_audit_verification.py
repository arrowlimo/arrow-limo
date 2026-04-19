#!/usr/bin/env python3
"""
Comprehensive T2 revenue recording and audit tracking system verification.
Check how 2012 revenue flows into T2 reporting and ensure income_ledger is populated.
"""

import psycopg2

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    print("\n" + "="*80)
    print("T2 REVENUE RECORDING & AUDIT TRACKING VERIFICATION")
    print("="*80)

    # 1. Check T2 extraction logic expectations
    print("\n=== 1. CURRENT T2 EXTRACTION LOGIC ===")
    print("Current code queries:")
    print("  - charters.total_amount_due (booked revenue)")
    print("  - receipts for expenses")
    print("  - banking_transactions for credits")
    print("\nPROBLEM: total_amount_due is BILLING, not CASH RECEIVED")
    print("  ✗ Does NOT extract from charter_payments (actual cash)")
    print("  ✓ Should use: SUM(charter_payments.amount) by year")

    # 2. Check income_ledger as single source of truth
    print("\n=== 2. INCOME_LEDGER AS SINGLE SOURCE OF TRUTH ===")
    print("Income ledger design:")
    query = """
    SELECT 
        (SELECT COUNT(*) FROM information_schema.columns WHERE table_name='income_ledger') as col_count,
        (SELECT COUNT(*) FROM income_ledger) as current_rows
    FROM (SELECT 1) t;
    """
    cur.execute(query)
    col_count, ledger_rows = cur.fetchone()
    print(f"  Columns defined: {col_count}")
    print(f"  Current rows: {ledger_rows}")
    if ledger_rows == 0:
        print("  ✗ EMPTY - Needs population from charter_payments")
    
    # 3. Check how revenue SHOULD flow
    print("\n=== 3. CORRECT REVENUE FLOW FOR T2 ===")
    print("Step 1: Record in income_ledger")
    print("  - Source: charter_payments table")
    print("  - Columns: payment_id, charter_id, reserve_number, amount → gross_amount")
    print("  - GST extraction: amount * 5 / 105 (AB rate)")
    print("  - Category: 'Operating Revenue' / 'Charter Services'")
    print("  - Fiscal year/quarter from payment_date")
    print("")
    print("Step 2: T2 extraction reads from income_ledger")
    print("  - Uses: SUM(gross_amount) WHERE fiscal_year = X")
    print("  - Excludes: is_taxable = false entries")
    print("  - Produces: net_amount for T2 reporting")
    print("")
    print("Step 3: Audit tracking in t2_deductibility_audit")
    print("  - Reconciles income_ledger against receipts GL codes")
    print("  - Tracks add-backs for non-deductible items")
    print("  - Links to T2 adjustments and Schedule 1")

    # 4. Check what's currently in 2012
    print("\n=== 4. CURRENT 2012 DATA STATUS ===")
    query = """
    SELECT 
        (SELECT COUNT(*) FROM charter_payments WHERE EXTRACT(YEAR FROM payment_date) = 2012) as cp_count,
        (SELECT COALESCE(SUM(amount), 0) FROM charter_payments WHERE EXTRACT(YEAR FROM payment_date) = 2012) as cp_total,
        (SELECT COUNT(*) FROM income_ledger WHERE fiscal_year = 2012) as il_count,
        (SELECT COALESCE(SUM(gross_amount), 0) FROM income_ledger WHERE fiscal_year = 2012) as il_total
    FROM (SELECT 1) t;
    """
    cur.execute(query)
    cp_count, cp_total, il_count, il_total = cur.fetchone()
    print(f"charter_payments (2012): {cp_count} rows, ${float(cp_total):,.2f}")
    print(f"income_ledger (2012):    {il_count} rows, ${float(il_total):,.2f}")
    if il_count == 0:
        print("\n✗ CRITICAL: income_ledger is EMPTY for 2012")
        print("   This means T2 extraction will produce incorrect revenue")

    # 5. Check t2_deductibility_audit table
    print("\n=== 5. AUDIT TRACKING TABLES ===")
    query = """
    SELECT 
        COUNT(*) as audit_record_count,
        COUNT(CASE WHEN fiscal_year = 2012 THEN 1 END) as audit_2012_count
    FROM t2_deductibility_audit;
    """
    try:
        cur.execute(query)
        audit_count, audit_2012 = cur.fetchone()
        print(f"t2_deductibility_audit: {audit_count} total records")
        print(f"  2012 audit records: {audit_2012}")
    except Exception as e:
        print(f"Error checking t2_deductibility_audit: {e}")

    # 6. Check t2_return_metadata
    print("\n=== 6. T2 RETURN METADATA ===")
    query = """
    SELECT COUNT(*), COUNT(CASE WHEN tax_year = 2012 THEN 1 END)
    FROM t2_return_metadata;
    """
    try:
        cur.execute(query)
        t2_count, t2_2012 = cur.fetchone()
        print(f"t2_return_metadata: {t2_count} total years")
        print(f"  2012 returns: {t2_2012}")
    except Exception as e:
        print(f"Error checking t2_return_metadata: {e}")

    # 7. Recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION: POPULATE INCOME_LEDGER FOR 2012")
    print("="*80)
    print(f"""
This will create the single source of truth for T2 revenue:

Charter Payments (2012):
  {cp_count} payments = ${float(cp_total):,.2f}

Should map to Income Ledger with:
  - revenue_category = 'Operating Revenue'
  - revenue_subcategory = 'Charter Services'  
  - is_taxable = true
  - fiscal_year = 2012
  - gst_collected = amount * 5 / 105
  - net_amount = amount - gst_collected

Then T2 extraction will read from income_ledger and produce:
  - Accurate business revenue
  - Proper GST reporting
  - Audit trail linking back to charter_payments
  - Schedule 1 add-backs from receipt GL analysis
""")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
