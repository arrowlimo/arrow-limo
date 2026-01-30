"""List all GST-exempt charters (full donations and other zero-GST classifications)."""
import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("GST-EXEMPT CHARTERS SUMMARY")
    print("=" * 100)
    print()
    
    # Get all charters with zero GST
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            client_name,
            classification,
            rate,
            payments_total,
            gratuity_amount,
            gst_amount_optimized,
            optimization_strategy
        FROM charity_trade_charters_view
        WHERE gst_amount_optimized = 0
        ORDER BY classification, charter_date
    """)
    
    rows = cur.fetchall()
    
    print(f"Total GST-Exempt Charters: {len(rows)}")
    print()
    
    # Group by classification
    by_classification = {}
    for row in rows:
        classification = row[3]
        if classification not in by_classification:
            by_classification[classification] = []
        by_classification[classification].append(row)
    
    for classification, charters in by_classification.items():
        print("=" * 100)
        print(f"{classification.upper().replace('_', ' ')} ({len(charters)} charters)")
        print("=" * 100)
        print()
        
        total_rate = sum(float(r[4]) if r[4] else 0 for r in charters)
        total_payments = sum(float(r[5]) for r in charters)
        total_gratuity = sum(float(r[6]) for r in charters)
        
        print(f"Total Rate Value: ${total_rate:,.2f}")
        print(f"Total Payments: ${total_payments:,.2f}")
        print(f"Total Gratuity (GST-exempt): ${total_gratuity:,.2f}")
        print(f"GST Liability: $0.00 (100% exempt)")
        print()
        
        print(f"{'Reserve':<12} {'Date':<12} {'Client':<30} {'Rate':<12} {'Payments':<12} {'Gratuity':<12}")
        print("-" * 100)
        
        for row in charters:
            reserve = row[0]
            date = str(row[1])
            client = (row[2] or 'Unknown')[:28]
            rate = float(row[4]) if row[4] else 0
            payments = float(row[5])
            gratuity = float(row[6])
            
            print(f"{reserve:<12} {date:<12} {client:<30} ${rate:>10.2f} ${payments:>10.2f} ${gratuity:>10.2f}")
        
        print()
        print("Strategy:", charters[0][8] if charters else "")
        print()
    
    # Summary by reason
    print("=" * 100)
    print("GST EXEMPTION BREAKDOWN")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            classification,
            COUNT(*) as count,
            SUM(payments_total) as total_payments,
            SUM(gratuity_amount) as total_gratuity
        FROM charity_trade_charters
        WHERE gst_amount_optimized = 0
        GROUP BY classification
        ORDER BY count DESC
    """)
    
    print(f"{'Classification':<30} {'Count':<10} {'Payments':<15} {'Gratuity (Exempt)':<20}")
    print("-" * 100)
    
    total_exempt_payments = 0
    total_exempt_gratuity = 0
    
    for row in cur.fetchall():
        classification = row[0]
        count = row[1]
        payments = float(row[2])
        gratuity = float(row[3])
        
        total_exempt_payments += payments
        total_exempt_gratuity += gratuity
        
        print(f"{classification.replace('_', ' ').title():<30} {count:<10} ${payments:>12,.2f}  ${gratuity:>15,.2f}")
    
    print("-" * 100)
    print(f"{'TOTAL GST-EXEMPT':<30} {len(rows):<10} ${total_exempt_payments:>12,.2f}  ${total_exempt_gratuity:>15,.2f}")
    print()
    
    # Overall GST summary
    print("=" * 100)
    print("OVERALL GST SUMMARY (All 116 Charity/Trade Charters)")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            SUM(payments_total) as total_payments,
            SUM(gst_amount_optimized) as total_gst,
            COUNT(CASE WHEN gst_amount_optimized = 0 THEN 1 END) as exempt_count,
            COUNT(CASE WHEN gst_amount_optimized > 0 THEN 1 END) as taxable_count
        FROM charity_trade_charters
    """)
    
    row = cur.fetchone()
    total_charters = row[0]
    total_payments = float(row[1])
    total_gst = float(row[2])
    exempt_count = row[3]
    taxable_count = row[4]
    
    print(f"Total Charters: {total_charters}")
    print(f"GST-Exempt Charters: {exempt_count} ({exempt_count/total_charters*100:.1f}%)")
    print(f"GST-Taxable Charters: {taxable_count} ({taxable_count/total_charters*100:.1f}%)")
    print()
    print(f"Total Payments: ${total_payments:,.2f}")
    print(f"GST-Exempt Payments: ${total_exempt_payments:,.2f} ({total_exempt_payments/total_payments*100:.1f}%)")
    print(f"Total GST: ${total_gst:,.2f}")
    print()
    
    print("=" * 100)
    print("✓ GST-EXEMPT CHARTERS IDENTIFIED")
    print("=" * 100)
    print()
    print(f"{exempt_count} charters with $0.00 GST liability:")
    print(f"  - full_donation: Pure donations, no consideration")
    print(f"  - partial_trade: Donated service, payment = gratuity only")
    print(f"  - partial_trade_extras: Donated base, extras = gratuity")
    print(f"  - donated_unredeemed_or_unpaid: Certificate not redeemed")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
