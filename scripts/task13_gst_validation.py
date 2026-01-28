#!/usr/bin/env python3
"""
TASK #13: GST Calculation Validation
Ensure GST calculations are correct and consistent across all records.
"""
import psycopg2

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*100)
    print("TASK #13: GST CALCULATION VALIDATION")
    print("="*100)
    
    # Validate receipts GST
    print("\n📋 RECEIPTS: Validating GST calculations...")
    
    # Find receipts where GST doesn't match 5% of net amount
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            gst_amount,
            net_amount,
            ROUND(gross_amount * 0.05 / 1.05, 2) as calculated_gst,
            ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) as difference
        FROM receipts
        WHERE gross_amount > 0
        AND gst_amount IS NOT NULL
        AND ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) > 0.02
        ORDER BY difference DESC
        LIMIT 100
    """)
    
    gst_mismatches = cur.fetchall()
    
    print(f"   Found {len(gst_mismatches)} receipts with GST calculation discrepancies")
    
    if gst_mismatches:
        print(f"\n   Top 10 discrepancies:")
        print(f"   {'ID':<10} {'Date':<12} {'Gross':>12} {'GST':>10} {'Expected':>10} {'Diff':>8}")
        print("   " + "-"*70)
        for rec_id, date, vendor, gross, gst, net, calc_gst, diff in gst_mismatches[:10]:
            print(f"   {rec_id:<10} {str(date):<12} ${gross:>10.2f} ${gst:>8.2f} ${calc_gst:>8.2f} ${diff:>6.2f}")
    
    # Check for missing GST amounts
    cur.execute("""
        SELECT COUNT(*) 
        FROM receipts
        WHERE gross_amount > 0
        AND gst_amount IS NULL
        AND category NOT IN ('TRANSFERS', 'BANKING', 'Vehicle Financing')
    """)
    
    missing_gst = cur.fetchone()[0]
    print(f"\n   ⚠️  {missing_gst:,} receipts missing GST amounts (excluding transfers/banking)")
    
    # Validate banking transactions GST flags
    print("\n\n💰 BANKING: Validating GST applicability flags...")
    
    print(f"   ℹ️  Banking transactions track GST applicability flag only (no amounts)")
    
    # Summary statistics
    print("\n\n📊 GST Summary:")
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE gst_applicable = TRUE) as applicable,
            COUNT(*) FILTER (WHERE gst_applicable = FALSE) as exempt,
            COUNT(*) FILTER (WHERE gst_applicable IS NULL) as unknown
        FROM banking_transactions
    """)
    
    banking_stats = cur.fetchone()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE gst_amount IS NOT NULL) as with_gst,
            COUNT(*) FILTER (WHERE gst_amount IS NULL) as without_gst,
            SUM(gst_amount) FILTER (WHERE gst_amount IS NOT NULL) as total_gst
        FROM receipts
    """)
    
    receipt_stats = cur.fetchone()
    
    print(f"\n   Banking Transactions:")
    print(f"      Total: {banking_stats[0]:,}")
    print(f"      GST Applicable: {banking_stats[1]:,}")
    print(f"      GST Exempt: {banking_stats[2]:,}")
    print(f"      Unknown: {banking_stats[3]:,}")
    
    print(f"\n   Receipts:")
    print(f"      Total: {receipt_stats[0]:,}")
    print(f"      With GST: {receipt_stats[1]:,}")
    print(f"      Without GST: {receipt_stats[2]:,}")
    print(f"      Total GST: ${receipt_stats[3] or 0:,.2f}")
    
    # Generate validation report
    validation_report = {
        'receipts': {
            'gst_mismatches': len(gst_mismatches),
            'missing_gst': missing_gst,
            'total_gst': float(receipt_stats[3]) if receipt_stats[3] else 0
        },
        'banking': {
            'applicable': banking_stats[1],
            'exempt': banking_stats[2],
            'unknown': banking_stats[3]
        }
    }
    
    # Save report
    import json
    with open('l:\\limo\\data\\gst_validation_report.json', 'w') as f:
        json.dump(validation_report, f, indent=2)
    
    print("\n" + "="*100)
    print("✅ TASK #13 COMPLETE")
    print("="*100)
    
    print(f"\n📁 Report saved to: l:\\limo\\data\\gst_validation_report.json")
    
    print(f"\n⚠️  Issues to address:")
    if len(gst_mismatches) > 0:
        print(f"   • {len(gst_mismatches)} receipts have GST calculation errors")
    if missing_gst > 0:
        print(f"   • {missing_gst:,} receipts missing GST amounts")
    if banking_stats[3] > 0:
        print(f"   • {banking_stats[3]:,} banking transactions need gst_applicable flag set")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
