"""Apply optimized GST calculations to charity_trade_charters table.

Adds columns for:
- gratuity_amount (GST-exempt voluntary payments)
- gst_base_amount (taxable base after gratuity separation)
- gst_amount_optimized (actual GST liability)
- optimization_strategy (documentation of approach)
"""
import psycopg2
from decimal import Decimal

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("Adding GST optimization columns to charity_trade_charters...")
    
    # Add new columns
    cur.execute("""
        ALTER TABLE charity_trade_charters
        ADD COLUMN IF NOT EXISTS gratuity_amount DECIMAL(12,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS gst_base_amount DECIMAL(12,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS gst_amount_optimized DECIMAL(12,2) DEFAULT 0,
        ADD COLUMN IF NOT EXISTS optimization_strategy TEXT;
        
        COMMENT ON COLUMN charity_trade_charters.gratuity_amount IS 
            'GST-EXEMPT: Voluntary payment after service completion. Not subject to GST per CRA guidelines.';
        COMMENT ON COLUMN charity_trade_charters.gst_base_amount IS 
            'Taxable base after gratuity separation. payments_total - gratuity_amount = gst_base_amount.';
        COMMENT ON COLUMN charity_trade_charters.gst_amount_optimized IS 
            'Actual GST liability using optimized classification (gratuity exempt, donations exempt, etc).';
        COMMENT ON COLUMN charity_trade_charters.optimization_strategy IS 
            'Documentation of GST optimization approach for CRA audit trail.';
    """)
    conn.commit()
    print("✓ Columns added")
    
    # Update each record with optimized GST calculation
    cur.execute("""
        SELECT 
            id,
            charter_id,
            reserve_number,
            classification,
            is_tax_locked,
            rate,
            payments_total,
            beverage_service
        FROM charity_trade_charters
        ORDER BY id
    """)
    
    rows = cur.fetchall()
    updated_count = 0
    
    for row in rows:
        record_id = row[0]
        charter_id = row[1]
        reserve_number = row[2]
        classification = row[3]
        is_tax_locked = row[4]
        rate = Decimal(str(row[5])) if row[5] else Decimal('0')
        payments_total = Decimal(str(row[6]))
        beverage_service = row[7]
        
        # Apply optimization strategy
        if classification == 'full_donation' or classification == 'donated_unredeemed_or_unpaid':
            gratuity_amount = Decimal('0')
            gst_base = Decimal('0')
            gst_optimized = Decimal('0')
            strategy = 'No consideration received - pure donation. NO GST liability.'
            
        elif classification == 'partial_trade':
            # Entire payment is gratuity (voluntary for donated service)
            gratuity_amount = payments_total
            gst_base = Decimal('0')
            gst_optimized = Decimal('0')
            strategy = 'Service donated. Payment classified as GRATUITY (voluntary, post-service). GST-EXEMPT per CRA.'
            
        elif classification == 'partial_trade_extras':
            # If beverage service, split 20% beverage (w/GST) + 80% gratuity
            if beverage_service == 'Y':
                beverage_base = payments_total * Decimal('0.20')
                gst_base = beverage_base
                gst_optimized = beverage_base * Decimal('0.05') / Decimal('1.05')
                gratuity_amount = payments_total * Decimal('0.80')
                strategy = 'Donated base service. Payment: 20% beverage charges (GST-included) + 80% gratuity (GST-exempt).'
            else:
                # No beverage, entire payment is gratuity
                gratuity_amount = payments_total
                gst_base = Decimal('0')
                gst_optimized = Decimal('0')
                strategy = 'Donated base service. Extras payment classified as GRATUITY (voluntary). GST-EXEMPT.'
                
        elif classification == 'paid_full':
            # If overpaid, excess is gratuity
            if payments_total > rate:
                excess = payments_total - rate
                gratuity_amount = excess
                gst_base = rate
                gst_optimized = rate * Decimal('0.05') / Decimal('1.05')
                strategy = f'Promotional rate ${rate:.2f} (GST-included). Overpayment ${excess:.2f} = GRATUITY (GST-exempt).'
            else:
                # Payment <= rate, full promotional service with GST
                gratuity_amount = Decimal('0')
                gst_base = payments_total
                gst_optimized = payments_total * Decimal('0.05') / Decimal('1.05')
                strategy = f'Promotional discounted rate (GST-included). No gratuity component.'
                
        else:  # mixed_or_uncertain
            # Conservative: 50% service, 50% gratuity
            gratuity_amount = payments_total * Decimal('0.50')
            gst_base = payments_total * Decimal('0.50')
            gst_optimized = gst_base * Decimal('0.05') / Decimal('1.05')
            strategy = 'Uncertain classification. Conservative split: 50% service (GST-included) + 50% gratuity (GST-exempt).'
        
        # Update the record
        cur.execute("""
            UPDATE charity_trade_charters
            SET 
                gratuity_amount = %s,
                gst_base_amount = %s,
                gst_amount_optimized = %s,
                optimization_strategy = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            float(gratuity_amount),
            float(gst_base),
            float(gst_optimized),
            strategy,
            record_id
        ))
        updated_count += 1
    
    conn.commit()
    print(f"✓ Updated {updated_count} records with optimized GST calculations")
    
    # Generate summary
    print("\n" + "=" * 100)
    print("GST OPTIMIZATION SUMMARY:")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            SUM(payments_total) as total_payments,
            SUM(gratuity_amount) as total_gratuity,
            SUM(gst_base_amount) as total_gst_base,
            SUM(gst_amount_optimized) as total_gst_optimized,
            SUM(payments_total * 0.05 / 1.05) as total_gst_before_optimization
        FROM charity_trade_charters
    """)
    
    row = cur.fetchone()
    total_payments = row[0]
    total_gratuity = row[1]
    total_gst_base = row[2]
    total_gst_optimized = row[3]
    total_gst_before = row[4]
    
    print(f"\nTotal Payments: ${total_payments:,.2f}")
    print(f"Reclassified as Gratuity (GST-exempt): ${total_gratuity:,.2f} ({total_gratuity/total_payments*100:.1f}%)")
    print(f"GST Taxable Base: ${total_gst_base:,.2f}")
    print(f"\nGST Before Optimization: ${total_gst_before:,.2f}")
    print(f"GST After Optimization: ${total_gst_optimized:,.2f}")
    print(f"GST SAVINGS: ${total_gst_before - total_gst_optimized:,.2f}")
    
    # By tax-lock status
    print("\n" + "-" * 100)
    print("BY TAX-LOCK STATUS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            CASE WHEN is_tax_locked THEN 'Pre-2012 (TAX-LOCKED)' ELSE 'Post-2011 (EDITABLE)' END as period,
            COUNT(*) as count,
            SUM(payments_total) as total_payments,
            SUM(gratuity_amount) as total_gratuity,
            SUM(gst_amount_optimized) as total_gst,
            SUM(payments_total * 0.05 / 1.05) as gst_before
        FROM charity_trade_charters
        GROUP BY is_tax_locked
        ORDER BY is_tax_locked DESC
    """)
    
    for row in cur.fetchall():
        period = row[0]
        count = row[1]
        payments = row[2]
        gratuity = row[3]
        gst_opt = row[4]
        gst_before = row[5]
        savings = gst_before - gst_opt
        
        print(f"\n{period}:")
        print(f"  Charters: {count}")
        print(f"  Payments: ${payments:,.2f}")
        print(f"  Gratuity: ${gratuity:,.2f}")
        print(f"  GST (optimized): ${gst_opt:,.2f}")
        print(f"  GST Savings: ${savings:,.2f}")
        if period.startswith('Pre-2012'):
            print(f"  [WARN]  Cannot amend filed returns (already with CRA)")
    
    # Update the view to include new columns
    print("\n" + "=" * 100)
    print("Updating charity_trade_charters_view...")
    
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
            -- NEW: GST optimization fields
            ctc.gratuity_amount,
            ctc.gst_base_amount,
            ctc.gst_amount_optimized,
            ctc.optimization_strategy,
            -- Computed: donated value
            CASE 
                WHEN ctc.classification = 'full_donation' THEN ctc.rate
                WHEN ctc.classification = 'partial_trade' THEN ctc.rate - ctc.payments_total
                WHEN ctc.classification = 'partial_trade_extras' THEN ctc.rate
                ELSE 0
            END as donated_value,
            c.notes as charter_notes,
            c.booking_notes,
            c.client_notes,
            ctc.source,
            ctc.created_at,
            ctc.updated_at
        FROM charity_trade_charters ctc
        INNER JOIN charters c ON ctc.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        ORDER BY c.charter_date DESC, ctc.reserve_number;
        
        COMMENT ON VIEW charity_trade_charters_view IS 
            'Charity/trade charters with optimized GST calculations. Gratuity amounts are GST-exempt per CRA guidelines.';
    """)
    conn.commit()
    print("✓ View updated with GST optimization columns")
    
    print("\n" + "=" * 100)
    print("DATABASE UPDATED SUCCESSFULLY")
    print("=" * 100)
    print("\nNew columns in charity_trade_charters:")
    print("  - gratuity_amount: GST-exempt voluntary payments")
    print("  - gst_base_amount: Taxable base after gratuity separation")
    print("  - gst_amount_optimized: Actual GST liability")
    print("  - optimization_strategy: Documentation for CRA audit")
    print("\nExample queries:")
    print("  -- View all gratuity reclassifications")
    print("  SELECT reserve_number, client_name, payments_total, gratuity_amount, gst_amount_optimized")
    print("  FROM charity_trade_charters_view WHERE gratuity_amount > 0;")
    print()
    print("  -- Calculate total GST savings")
    print("  SELECT SUM(payments_total * 0.05 / 1.05 - gst_amount_optimized) as gst_savings")
    print("  FROM charity_trade_charters;")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
