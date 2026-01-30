"""Create view for charity/trade charters with full charter and client details."""
import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("Creating charity_trade_charters_view...")
    
    cur.execute("""
        DROP VIEW IF EXISTS charity_trade_charters_view CASCADE;
        
        CREATE VIEW charity_trade_charters_view AS
        SELECT 
            ctc.id,
            ctc.reserve_number,
            ctc.classification,
            ctc.is_tax_locked,
            c.charter_date,
            c.pickup_time,
            c.pickup_address,
            c.dropoff_address,
            c.passenger_count,
            c.vehicle,
            c.driver,
            c.status as charter_status,
            c.cancelled,
            cl.client_name,
            cl.email as client_email,
            ctc.rate,
            ctc.payments_total,
            ctc.refunds_total,
            ctc.deposit,
            ctc.balance,
            ctc.beverage_service,
            ctc.payment_count,
            ctc.payment_methods,
            c.notes as charter_notes,
            c.booking_notes,
            c.client_notes,
            ctc.source,
            ctc.created_at,
            ctc.updated_at,
            -- Computed fields for analysis
            CASE 
                WHEN ctc.classification = 'full_donation' THEN ctc.rate
                WHEN ctc.classification = 'partial_trade' THEN ctc.rate - ctc.payments_total
                WHEN ctc.classification = 'partial_trade_extras' THEN ctc.rate  -- Assuming full rate was donated
                ELSE 0
            END as donated_value,
            CASE 
                WHEN ctc.classification IN ('partial_trade_extras', 'paid_full') 
                    THEN ctc.payments_total * 0.05 / 1.05  -- GST included calculation
                ELSE 0
            END as gst_collected
        FROM charity_trade_charters ctc
        INNER JOIN charters c ON ctc.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        ORDER BY c.charter_date DESC, ctc.reserve_number;
        
        COMMENT ON VIEW charity_trade_charters_view IS 
            'Full details of charity/trade/promo charters with computed donated_value and gst_collected fields. Source: LMS Pymt_Type promo/trade (authoritative).';
    """)
    
    conn.commit()
    print("✓ View created: charity_trade_charters_view")
    
    # Test the view with a sample query
    print("\n=== SAMPLE: Recent Charity/Trade Charters ===")
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            client_name,
            classification,
            is_tax_locked,
            rate,
            payments_total,
            donated_value,
            gst_collected
        FROM charity_trade_charters_view
        WHERE charter_date >= '2024-01-01'
        ORDER BY charter_date DESC
        LIMIT 10
    """)
    
    print(f"\n{'Reserve':<10} {'Date':<12} {'Client':<25} {'Classification':<25} {'Lock':<6} {'Rate':<10} {'Paid':<10} {'Donated':<10} {'GST':<8}")
    print("-" * 130)
    
    for row in cur.fetchall():
        lock = "YES" if row[4] else "NO"
        print(f"{row[0]:<10} {str(row[1]):<12} {(row[2] or '')[:25]:<25} {row[3]:<25} {lock:<6} ${row[5] or 0:>8.2f} ${row[6]:>8.2f} ${row[7]:>8.2f} ${row[8]:>6.2f}")
    
    cur.close()
    conn.close()
    
    print("\n✓ Charity/trade charters successfully integrated into almsdata database")
    print("\nAvailable objects:")
    print("  - Table: charity_trade_charters (116 records)")
    print("  - View: charity_trade_charters_view (with full charter/client details)")
    print("\nExample queries:")
    print("  SELECT * FROM charity_trade_charters WHERE classification = 'full_donation';")
    print("  SELECT * FROM charity_trade_charters WHERE is_tax_locked = true;")
    print("  SELECT * FROM charity_trade_charters_view WHERE charter_date >= '2024-01-01';")

if __name__ == '__main__':
    main()
