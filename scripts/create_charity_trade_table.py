"""Create charity_trade_charters table and populate from corrected CSV."""
import psycopg2
import csv
from datetime import datetime

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    # Create the charity_trade_charters table
    print("Creating charity_trade_charters table...")
    cur.execute("""
        DROP TABLE IF EXISTS charity_trade_charters CASCADE;
        
        CREATE TABLE charity_trade_charters (
            id SERIAL PRIMARY KEY,
            charter_id INTEGER REFERENCES charters(charter_id),
            reserve_number VARCHAR(20) NOT NULL,
            classification VARCHAR(100) NOT NULL,
            is_tax_locked BOOLEAN DEFAULT FALSE,
            rate DECIMAL(12,2),
            payments_total DECIMAL(12,2),
            refunds_total DECIMAL(12,2),
            deposit DECIMAL(12,2),
            balance DECIMAL(12,2),
            beverage_service CHAR(1),
            payment_count INTEGER,
            payment_methods TEXT,
            booking_excerpt TEXT,
            client_excerpt TEXT,
            notes_excerpt TEXT,
            source VARCHAR(50) DEFAULT 'LMS_Promo_Trade',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_reserve_charity UNIQUE (reserve_number)
        );
        
        CREATE INDEX idx_charity_classification ON charity_trade_charters(classification);
        CREATE INDEX idx_charity_tax_locked ON charity_trade_charters(is_tax_locked);
        CREATE INDEX idx_charity_reserve ON charity_trade_charters(reserve_number);
        
        COMMENT ON TABLE charity_trade_charters IS 
            'Authoritative list of charity/trade/promo charters from LMS Pymt_Type field. Pre-2012 entries are tax-locked (CRA filing complete).';
        COMMENT ON COLUMN charity_trade_charters.classification IS 
            'full_donation, partial_trade, partial_trade_extras, paid_full, donated_unredeemed_or_unpaid, mixed_or_uncertain';
        COMMENT ON COLUMN charity_trade_charters.is_tax_locked IS 
            'TRUE if charter_date < 2012-01-01. These entries are immutable (CRA tax filing complete).';
    """)
    conn.commit()
    print("✓ Table created with indexes")
    
    # Read the corrected CSV
    print("\nReading charity_runs_CORRECTED.csv...")
    csv_path = r'L:\limo\reports\charity_runs_CORRECTED.csv'
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Found {len(rows)} charity/trade charters to import")
    
    # Insert each row
    insert_count = 0
    skipped_count = 0
    
    for row in rows:
        reserve_number = row['reserve_number']
        classification_raw = row['classification']
        
        # Extract tax_locked flag from classification string
        is_tax_locked = '[TAX_LOCKED]' in classification_raw
        classification = classification_raw.replace(' [TAX_LOCKED]', '')
        
        # Get charter_id from reserve_number
        cur.execute(
            "SELECT charter_id FROM charters WHERE reserve_number = %s",
            (reserve_number,)
        )
        charter_result = cur.fetchone()
        charter_id = charter_result[0] if charter_result else None
        
        if not charter_id:
            print(f"[WARN]  Reserve {reserve_number}: No charter_id found in charters table")
            skipped_count += 1
            continue
        
        # Parse numeric fields (remove commas first)
        rate = float(row['rate'].replace(',', '')) if row['rate'] else None
        payments_total = float(row['payments_total'].replace(',', '')) if row['payments_total'] else 0.0
        refunds_total = float(row['refunds_total'].replace(',', '')) if row['refunds_total'] else 0.0
        deposit = float(row['deposit'].replace(',', '')) if row['deposit'] else None
        balance = float(row['balance'].replace(',', '')) if row['balance'] else None
        pay_count = int(row['pay_count']) if row['pay_count'] else 0
        
        # Insert into table
        cur.execute("""
            INSERT INTO charity_trade_charters (
                charter_id, reserve_number, classification, is_tax_locked,
                rate, payments_total, refunds_total, deposit, balance,
                beverage_service, payment_count, payment_methods,
                booking_excerpt, client_excerpt, notes_excerpt
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (reserve_number) DO UPDATE SET
                charter_id = EXCLUDED.charter_id,
                classification = EXCLUDED.classification,
                is_tax_locked = EXCLUDED.is_tax_locked,
                rate = EXCLUDED.rate,
                payments_total = EXCLUDED.payments_total,
                refunds_total = EXCLUDED.refunds_total,
                deposit = EXCLUDED.deposit,
                balance = EXCLUDED.balance,
                beverage_service = EXCLUDED.beverage_service,
                payment_count = EXCLUDED.payment_count,
                payment_methods = EXCLUDED.payment_methods,
                booking_excerpt = EXCLUDED.booking_excerpt,
                client_excerpt = EXCLUDED.client_excerpt,
                notes_excerpt = EXCLUDED.notes_excerpt,
                updated_at = CURRENT_TIMESTAMP
        """, (
            charter_id, reserve_number, classification, is_tax_locked,
            rate, payments_total, refunds_total, deposit, balance,
            row['beverage_service'] or None,
            pay_count,
            row['payment_methods'] or None,
            row['booking_excerpt'] or None,
            row['client_excerpt'] or None,
            row['notes_excerpt'] or None
        ))
        insert_count += 1
    
    conn.commit()
    
    # Generate summary statistics
    print(f"\n✓ Imported {insert_count} charity/trade charters")
    if skipped_count > 0:
        print(f"[WARN]  Skipped {skipped_count} records (no matching charter_id)")
    
    print("\n=== SUMMARY BY CLASSIFICATION ===")
    cur.execute("""
        SELECT 
            classification,
            is_tax_locked,
            COUNT(*) as count,
            SUM(rate) as total_rate,
            SUM(payments_total) as total_payments,
            SUM(refunds_total) as total_refunds,
            SUM(payments_total - refunds_total) as net_amount
        FROM charity_trade_charters
        GROUP BY classification, is_tax_locked
        ORDER BY is_tax_locked DESC, count DESC
    """)
    
    for row in cur.fetchall():
        tax_flag = " [TAX-LOCKED]" if row[1] else ""
        print(f"\n{row[0]}{tax_flag}:")
        print(f"  Count: {row[2]}")
        print(f"  Total Rate: ${row[3]:,.2f}")
        print(f"  Total Payments: ${row[4]:,.2f}")
        print(f"  Total Refunds: ${row[5]:,.2f}")
        print(f"  Net Amount: ${row[6]:,.2f}")
    
    print("\n=== TAX-LOCK STATUS ===")
    cur.execute("""
        SELECT 
            CASE WHEN is_tax_locked THEN 'Pre-2012 (Tax-Locked)' ELSE 'Post-2011 (Editable)' END as period,
            COUNT(*) as count,
            SUM(payments_total - refunds_total) as net_amount
        FROM charity_trade_charters
        GROUP BY is_tax_locked
        ORDER BY is_tax_locked DESC
    """)
    
    for row in cur.fetchall():
        print(f"\n{row[0]}:")
        print(f"  Count: {row[1]}")
        print(f"  Net Amount: ${row[2]:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n✓ Database updated successfully")
    print("\nTable: charity_trade_charters")
    print("Source: reports/charity_runs_CORRECTED.csv (116 confirmed from LMS Pymt_Type promo/trade)")

if __name__ == '__main__':
    main()
