"""
Detailed analysis of charter_charges discrepancies to understand the data patterns
before applying fixes.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def analyze_charge_patterns():
    """Analyze charter_charges patterns."""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("DETAILED CHARTER_CHARGES ANALYSIS")
    print("=" * 80)
    print()
    
    # 1. Overall statistics
    print("1. OVERALL STATISTICS")
    print("=" * 80)
    
    cur.execute("SELECT COUNT(*) as total FROM charters WHERE reserve_number IS NOT NULL")
    total_charters = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(DISTINCT charter_id) as with_charges FROM charter_charges")
    charters_with_charges = cur.fetchone()['with_charges']
    
    cur.execute("SELECT COUNT(*) as total_charges FROM charter_charges")
    total_charge_records = cur.fetchone()['total_charges']
    
    print(f"Total charters: {total_charters:,}")
    print(f"Charters with charges: {charters_with_charges:,} ({charters_with_charges/total_charters*100:.1f}%)")
    print(f"Total charter_charge records: {total_charge_records:,}")
    print(f"Avg charges per charter (with charges): {total_charge_records/charters_with_charges:.1f}")
    
    # 2. Discrepancy patterns
    print(f"\n2. DISCREPANCY PATTERNS")
    print("=" * 80)
    
    cur.execute("""
        WITH charge_totals AS (
            SELECT 
                charter_id,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT 
            CASE 
                WHEN ct.total_charges IS NULL THEN 'No charges'
                WHEN ct.total_charges = 0 THEN 'Zero charges'
                WHEN c.total_amount_due = ct.total_charges THEN 'Match'
                WHEN c.total_amount_due > ct.total_charges THEN 'Under-charged'
                WHEN c.total_amount_due < ct.total_charges THEN 'Over-charged'
            END as pattern,
            COUNT(*) as count,
            SUM(c.total_amount_due) as total_due_sum,
            SUM(COALESCE(ct.total_charges, 0)) as charges_sum,
            SUM(c.total_amount_due - COALESCE(ct.total_charges, 0)) as discrepancy_sum
        FROM charters c
        LEFT JOIN charge_totals ct ON ct.charter_id = c.charter_id
        WHERE c.reserve_number IS NOT NULL
        GROUP BY pattern
        ORDER BY count DESC
    """)
    
    patterns = cur.fetchall()
    for row in patterns:
        print(f"\n{row['pattern']}:")
        print(f"  Count: {row['count']:,} charters")
        print(f"  Total due: ${row['total_due_sum']:,.2f}")
        print(f"  Total charges: ${row['charges_sum']:,.2f}")
        print(f"  Discrepancy: ${row['discrepancy_sum']:,.2f}")
    
    # 3. No charges analysis
    print(f"\n3. CHARTERS WITH NO CHARGES")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date)::int as year,
            COUNT(*) as count,
            SUM(total_amount_due) as total_due,
            SUM(paid_amount) as total_paid
        FROM charters c
        WHERE c.reserve_number IS NOT NULL
        AND c.charter_id NOT IN (SELECT DISTINCT charter_id FROM charter_charges)
        AND charter_date IS NOT NULL
        GROUP BY year
        ORDER BY year DESC
    """)
    
    no_charges_by_year = cur.fetchall()
    print("\nBy year:")
    for row in no_charges_by_year:
        print(f"  {row['year']}: {row['count']:,} charters, ${row['total_due']:,.2f} due, ${row['total_paid']:,.2f} paid")
    
    # 4. Over-charged analysis
    print(f"\n4. OVER-CHARGED CHARTERS (charges > total_due)")
    print("=" * 80)
    
    cur.execute("""
        WITH charge_totals AS (
            SELECT 
                charter_id,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT 
            c.reserve_number,
            c.charter_date,
            COALESCE(cl.client_name, c.account_number) as client,
            c.total_amount_due,
            ct.total_charges,
            ct.total_charges - c.total_amount_due as excess
        FROM charters c
        JOIN charge_totals ct ON ct.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE ct.total_charges > c.total_amount_due + 0.01
        ORDER BY excess DESC
        LIMIT 10
    """)
    
    over_charged = cur.fetchall()
    if over_charged:
        print(f"\nFound {cur.rowcount} over-charged charters. Top 10:")
        for idx, row in enumerate(over_charged, 1):
            print(f"\n{idx}. Charter {row['reserve_number']} ({row['charter_date']})")
            print(f"   Client: {row['client']}")
            print(f"   Total due: ${row['total_amount_due']:,.2f}")
            print(f"   Charges: ${row['total_charges']:,.2f}")
            print(f"   Excess: ${row['excess']:,.2f}")
    
    # 5. Sample charter_charges
    print(f"\n5. SAMPLE CHARTER_CHARGES RECORDS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            cc.charge_id,
            cc.charter_id,
            c.reserve_number,
            cc.description,
            cc.amount,
            cc.charge_type
        FROM charter_charges cc
        JOIN charters c ON c.charter_id = cc.charter_id
        ORDER BY cc.charge_id DESC
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    print("\nRecent charter_charges:")
    for row in samples:
        print(f"\n  Charge ID {row['charge_id']} (Charter {row['reserve_number']})")
        print(f"    Description: {row['description']}")
        print(f"    Amount: ${row['amount']:,.2f}")
        print(f"    Type: {row['charge_type']}")
    
    # 6. Recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print("=" * 80)
    
    print("\n⚠️  CRITICAL FINDINGS:")
    print(f"  - {len([p for p in patterns if p['pattern'] == 'No charges'])} charters have NO charter_charges")
    print(f"  - {len([p for p in patterns if p['pattern'] == 'Over-charged'])} charters have EXCESS charges")
    print(f"  - Net discrepancy: ${sum(Decimal(str(p['discrepancy_sum'])) for p in patterns):,.2f}")
    
    print("\n✅ SAFE APPROACH:")
    print("  1. Only add charges for charters with $0.00 charges (missing entirely)")
    print("  2. Skip charters that are over-charged (need manual investigation)")
    print("  3. Review recent charters (2025) first before touching historical data")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    analyze_charge_patterns()
