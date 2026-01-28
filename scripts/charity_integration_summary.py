"""Generate final summary report of charity/trade integration."""
import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("CHARITY/TRADE CHARTERS - DATABASE INTEGRATION COMPLETE")
    print("=" * 80)
    print(f"Date: November 7, 2025")
    print(f"Source: LMS Pymt_Type 'promo' or 'trade' (authoritative)")
    print(f"Records: 116 confirmed charity/trade/promo charters")
    print()
    
    # Overall statistics
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(DISTINCT charter_id) as unique_charters,
            SUM(rate) as total_rate,
            SUM(payments_total) as total_payments,
            SUM(refunds_total) as total_refunds,
            SUM(payments_total - refunds_total) as net_revenue
        FROM charity_trade_charters
    """)
    row = cur.fetchone()
    
    print("OVERALL STATISTICS:")
    print(f"  Total Charters: {row[0]}")
    print(f"  Unique Charters: {row[1]}")
    print(f"  Total Rate Value: ${row[2]:,.2f}")
    print(f"  Total Payments: ${row[3]:,.2f}")
    print(f"  Total Refunds: ${row[4]:,.2f}")
    print(f"  Net Revenue: ${row[5]:,.2f}")
    print()
    
    # By classification
    print("BREAKDOWN BY CLASSIFICATION:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            classification,
            COUNT(*) as count,
            SUM(rate) as total_rate,
            SUM(payments_total) as total_payments,
            SUM(payments_total - refunds_total) as net_amount,
            ROUND(AVG(rate), 2) as avg_rate,
            ROUND(AVG(payments_total), 2) as avg_payment
        FROM charity_trade_charters
        GROUP BY classification
        ORDER BY count DESC
    """)
    
    for row in cur.fetchall():
        print(f"\n{row[0]}:")
        print(f"  Count: {row[1]}")
        print(f"  Total Rate: ${row[2]:,.2f}")
        print(f"  Total Payments: ${row[3]:,.2f}")
        print(f"  Net Amount: ${row[4]:,.2f}")
        print(f"  Avg Rate: ${row[5]:,.2f}")
        print(f"  Avg Payment: ${row[6]:,.2f}")
    
    print()
    print("-" * 80)
    
    # Tax-lock status
    print("\nTAX-LOCK STATUS:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            CASE WHEN is_tax_locked THEN 'Pre-2012 (TAX-LOCKED - CRA Filed)' 
                 ELSE 'Post-2011 (Editable)' END as period,
            COUNT(*) as count,
            SUM(rate) as total_rate,
            SUM(payments_total - refunds_total) as net_amount
        FROM charity_trade_charters
        GROUP BY is_tax_locked
        ORDER BY is_tax_locked DESC
    """)
    
    for row in cur.fetchall():
        print(f"\n{row[0]}:")
        print(f"  Count: {row[1]}")
        print(f"  Total Rate: ${row[2]:,.2f}")
        print(f"  Net Amount: ${row[3]:,.2f}")
    
    print()
    print("-" * 80)
    
    # Date range
    print("\nDATE RANGE:")
    cur.execute("""
        SELECT 
            MIN(c.charter_date) as earliest,
            MAX(c.charter_date) as latest,
            COUNT(DISTINCT EXTRACT(YEAR FROM c.charter_date)) as year_count
        FROM charity_trade_charters ctc
        JOIN charters c ON ctc.charter_id = c.charter_id
    """)
    row = cur.fetchone()
    print(f"  Earliest Charter: {row[0]}")
    print(f"  Latest Charter: {row[1]}")
    print(f"  Years Span: {row[2]}")
    print()
    
    # Top clients
    print("TOP 10 CLIENTS (by payment value):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            cl.client_name,
            COUNT(*) as charter_count,
            SUM(ctc.payments_total) as total_payments,
            STRING_AGG(DISTINCT ctc.classification, ', ') as classifications
        FROM charity_trade_charters ctc
        JOIN charters c ON ctc.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        GROUP BY cl.client_name
        ORDER BY total_payments DESC
        LIMIT 10
    """)
    
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"{i:2}. {(row[0] or 'Unknown')[:40]:<40} {row[1]:>3} charters  ${row[2]:>10,.2f}  ({row[3]})")
    
    print()
    print("=" * 80)
    print("DATABASE OBJECTS CREATED:")
    print("=" * 80)
    print("  1. Table: charity_trade_charters")
    print("     - 116 records from LMS Pymt_Type promo/trade")
    print("     - Columns: charter_id, reserve_number, classification, is_tax_locked,")
    print("                rate, payments_total, refunds_total, deposit, balance,")
    print("                beverage_service, payment_count, payment_methods")
    print()
    print("  2. View: charity_trade_charters_view")
    print("     - Full charter and client details")
    print("     - Computed fields: donated_value, gst_collected")
    print()
    print("EXAMPLE QUERIES:")
    print("  -- All charity/trade charters")
    print("  SELECT * FROM charity_trade_charters ORDER BY reserve_number;")
    print()
    print("  -- Full donations only")
    print("  SELECT * FROM charity_trade_charters WHERE classification = 'full_donation';")
    print()
    print("  -- Tax-locked entries (pre-2012)")
    print("  SELECT * FROM charity_trade_charters WHERE is_tax_locked = true;")
    print()
    print("  -- Recent charters with full details")
    print("  SELECT * FROM charity_trade_charters_view WHERE charter_date >= '2024-01-01';")
    print()
    print("  -- Donated value calculation")
    print("  SELECT reserve_number, client_name, classification, donated_value")
    print("  FROM charity_trade_charters_view")
    print("  WHERE donated_value > 0")
    print("  ORDER BY donated_value DESC;")
    print()
    print("=" * 80)
    print("INTEGRATION COMPLETE ✓")
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
