#!/usr/bin/env python3
"""
Investigate the $2.47M in maintenance expenses (5120) for 2012.
Check if some should be reclassified as vehicle purchases (assets).
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("INVESTIGATING $2.47M MAINTENANCE EXPENSES (Account 5120)")
    print("="*80)
    
    # Get all 5120 receipts sorted by amount
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            gst_amount,
            net_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code = '5120'
        ORDER BY gross_amount DESC
        LIMIT 50
    """)
    
    top_expenses = cur.fetchall()
    
    print(f"\nTOP 50 MAINTENANCE EXPENSES (out of 2,029 total):")
    print("="*80)
    
    total_top_50 = 0
    potential_assets = []
    
    for i, expense in enumerate(top_expenses, 1):
        receipt_id = expense[0]
        date = expense[1]
        vendor = (expense[2] or 'Unknown')[:40]
        description = (expense[3] or '')[:50]
        amount = float(expense[4])
        
        total_top_50 += amount
        
        # Flag potential vehicle purchases (>$20k likely asset not expense)
        is_asset = amount > 20000
        flag = "🚗 ASSET?" if is_asset else ""
        
        if is_asset:
            potential_assets.append({
                'receipt_id': receipt_id,
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'description': description
            })
        
        print(f"{i:2d}. {date} | {vendor:40s} | ${amount:10,.2f} {flag}")
        if description:
            print(f"    {description}")
    
    print(f"\n{'='*80}")
    print(f"Top 50 total: ${total_top_50:,.2f} ({total_top_50/2474628.63*100:.1f}% of all 5120)")
    print(f"{'='*80}")
    
    # Analyze potential assets
    if potential_assets:
        print(f"\n{'='*80}")
        print(f"POTENTIAL VEHICLE PURCHASES (Should be Assets, not Expenses)")
        print(f"{'='*80}")
        
        total_assets = sum(item['amount'] for item in potential_assets)
        
        for item in potential_assets:
            print(f"\n{item['date']} | {item['vendor']:40s} | ${item['amount']:,.2f}")
            if item['description']:
                print(f"  Description: {item['description']}")
        
        print(f"\n{'='*80}")
        print(f"Total potential assets: ${total_assets:,.2f}")
        print(f"If reclassified to 1500 (Vehicles):")
        print(f"  • Reduces expenses by ${total_assets:,.2f}")
        print(f"  • Changes P&L from loss to: ${-1117100.87 + total_assets:,.2f}")
        print(f"{'='*80}")
    
    # Check vendor patterns
    print(f"\n{'='*80}")
    print(f"VENDOR ANALYSIS (5120 Maintenance)")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT 
            COALESCE(vendor_name, 'Unknown') as vendor,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount,
            AVG(gross_amount) as avg_amount,
            MAX(gross_amount) as max_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND gl_account_code = '5120'
        GROUP BY COALESCE(vendor_name, 'Unknown')
        HAVING SUM(gross_amount) > 10000
        ORDER BY SUM(gross_amount) DESC
    """)
    
    vendors = cur.fetchall()
    
    for vendor_data in vendors:
        vendor = vendor_data[0][:40]
        count = vendor_data[1]
        total = float(vendor_data[2])
        avg = float(vendor_data[3])
        max_amt = float(vendor_data[4])
        
        print(f"\n{vendor:40s}")
        print(f"  {count:4d} receipts | Total: ${total:12,.2f} | Avg: ${avg:8,.2f} | Max: ${max_amt:10,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
