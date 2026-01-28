#!/usr/bin/env python3
"""
Analyze refund linkage status - how many refunds are applied to charter runs
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("REFUND LINKAGE ANALYSIS")
    print("=" * 80)
    
    # Overall stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_refunds,
            COUNT(charter_id) as linked_refunds,
            COUNT(*) - COUNT(charter_id) as unlinked_refunds,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as linked_amount,
            SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unlinked_amount
        FROM charter_refunds
    """)
    
    total, linked, unlinked, total_amt, linked_amt, unlinked_amt = cur.fetchone()
    
    print(f"\n📊 OVERALL STATUS:")
    print(f"   Total Refunds: {total:,} refunds = ${total_amt:,.2f}")
    print(f"   [OK] Linked to Charters: {linked:,} ({linked/total*100:.1f}%) = ${linked_amt:,.2f} ({linked_amt/total_amt*100:.1f}%)")
    print(f"   [FAIL] Unlinked (No Charter): {unlinked:,} ({unlinked/total*100:.1f}%) = ${unlinked_amt:,.2f} ({unlinked_amt/total_amt*100:.1f}%)")
    
    # Breakdown by source
    print(f"\n📁 BREAKDOWN BY SOURCE:")
    cur.execute("""
        SELECT 
            source_file,
            COUNT(*) as refund_count,
            COUNT(charter_id) as linked_count,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as linked_amount
        FROM charter_refunds
        GROUP BY source_file
        ORDER BY total_amount DESC
    """)
    
    for source, count, linked_cnt, amt, linked_amt in cur.fetchall():
        link_pct = (linked_cnt/count*100) if count > 0 else 0
        amt_pct = (linked_amt/amt*100) if amt > 0 else 0
        print(f"   {source}:")
        print(f"      {count:,} refunds, {linked_cnt:,} linked ({link_pct:.1f}%)")
        print(f"      ${amt:,.2f} total, ${linked_amt:,.2f} linked ({amt_pct:.1f}%)")
    
    # Check for reserve_number matches that aren't linked
    print(f"\n🔍 POTENTIAL LINKAGE OPPORTUNITIES:")
    cur.execute("""
        SELECT COUNT(*) 
        FROM charter_refunds r
        WHERE r.reserve_number IS NULL 
        AND r.reserve_number IS NOT NULL
        AND EXISTS (SELECT 1 FROM charters c WHERE c.reserve_number = r.reserve_number)
    """)
    fixable = cur.fetchone()[0]
    
    if fixable > 0:
        print(f"   [WARN]  {fixable:,} unlinked refunds have reserve_numbers that match existing charters!")
        print(f"      These can be automatically linked.")
        
        # Show examples
        cur.execute("""
            SELECT r.id, r.reserve_number, r.amount, r.refund_date, r.customer
            FROM charter_refunds r
            WHERE r.reserve_number IS NULL 
            AND r.reserve_number IS NOT NULL
            AND EXISTS (SELECT 1 FROM charters c WHERE c.reserve_number = r.reserve_number)
            ORDER BY r.amount DESC
            LIMIT 10
        """)
        
        print(f"\n   Top 10 examples:")
        for refund_id, reserve, amt, date, customer in cur.fetchall():
            print(f"      Refund #{refund_id}: {reserve} - ${amt:,.2f} on {date} ({customer})")
    else:
        print(f"   [OK] All refunds with valid reserve_numbers are already linked")
    
    # Top unlinked refunds
    print(f"\n💰 TOP 10 UNLINKED REFUNDS (by amount):")
    cur.execute("""
        SELECT id, reserve_number, amount, refund_date, customer, description
        FROM charter_refunds
        WHERE reserve_number IS NULL
        ORDER BY amount DESC
        LIMIT 10
    """)
    
    for refund_id, reserve, amt, date, customer, desc in cur.fetchall():
        reserve_str = reserve if reserve else "NO RESERVE #"
        desc_str = desc[:50] if desc else ""
        print(f"   #{refund_id}: ${amt:,.2f} - {reserve_str} - {customer} ({date})")
        if desc_str:
            print(f"           {desc_str}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
