#!/usr/bin/env python
"""Group GL 9999 entries by vendor for manual categorization."""
import psycopg2, os, csv
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD',os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("=" * 100)
    print("GL 9999 (UNKNOWN) ENTRIES - GROUPED BY VENDOR")
    print("=" * 100)
    
    # Get vendor groups with counts
    cur.execute("""
        SELECT vendor_name, COUNT(*) cnt, SUM(gross_amount) total_amt
        FROM receipts
        WHERE gl_account_code = '9999'
        GROUP BY vendor_name
        ORDER BY cnt DESC
    """)
    
    vendors = cur.fetchall()
    print(f"\nTotal vendors: {len(vendors)}")
    print(f"Total receipts in GL 9999: {sum(v[1] for v in vendors)}")
    
    # Export detailed CSV for review
    csv_file = f"gl_9999_unknown_entries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Rank', 'Vendor', 'Count', 'Total Amount', 'Avg Amount', 'Sample Dates', 'Suggested GL'])
        
        for rank, (vendor, cnt, total_amt) in enumerate(vendors, 1):
            avg_amt = float(total_amt) / cnt if total_amt else 0
            
            # Get sample dates
            cur.execute("""
                SELECT DISTINCT receipt_date FROM receipts
                WHERE gl_account_code = '9999' AND vendor_name = %s
                ORDER BY receipt_date DESC LIMIT 3
            """, (vendor,))
            dates = [str(d[0]) for d in cur.fetchall()]
            
            writer.writerow([
                rank,
                vendor if vendor else '(NULL)',
                cnt,
                f"${total_amt:.2f}" if total_amt else '$0.00',
                f"${avg_amt:.2f}",
                ', '.join(dates),
                ''  # User will fill in suggested GL
            ])
    
    print(f"\n✅ Exported: {csv_file}")
    print("\nTop 30 vendors by count:")
    print(f"{'Rank':<6} {'Count':<6} {'Amount':<12} {'Vendor':<40}")
    print("-" * 70)
    for rank, (vendor, cnt, total_amt) in enumerate(vendors[:30], 1):
        vendor_name = (vendor if vendor else '(NULL)')[:38]
        print(f"{rank:<6} {cnt:<6} ${float(total_amt):>10.2f}  {vendor_name:<40}")
    
    if len(vendors) > 30:
        print(f"\n... and {len(vendors) - 30} more vendors")
    
    cur.close(); conn.close()
    
    print(f"\n📌 NEXT STEPS:")
    print(f"1. Open {csv_file} in Excel/Sheets")
    print(f"2. For each vendor, assign a GL code in the 'Suggested GL' column")
    print(f"3. Save and send back for batch update")

if __name__ == '__main__':
    main()
