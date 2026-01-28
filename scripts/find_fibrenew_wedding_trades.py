import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find FIBRENEW payments linked to charters (wedding trades)
cur.execute("""
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.amount,
        p.payment_date,
        p.payment_method,
        c.pickup_time,
        c.client_display_name,
        c.total_amount_due
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE LOWER(p.payment_method) LIKE '%trade%'
       OR LOWER(p.payment_method) LIKE '%fibrenew%'
    ORDER BY p.payment_date
""")

print("Fibrenew/Trade Payments Linked to Charters (Wedding Trades):")
print(f"{'Payment ID':<12} {'Reserve#':<10} {'Amount':>10} {'Pmt Date':<12} {'Method':<30} {'Charter Time':<20} {'Customer':<30}")
print("-" * 145)

rows = cur.fetchall()

for r in rows:
    payment_id = r[0]
    reserve = r[1] or 'NULL'
    amount = r[2]
    pmt_date = r[3]
    method = (r[4] or '')[:29]
    charter_time = r[5] or 'NULL'
    customer = (r[6] or '')[:29]
    
    print(f"{payment_id:<12} {str(reserve):<10} ${amount:>9,.2f} {str(pmt_date):<12} {method:<30} {str(charter_time):<20} {customer:<30}")

print(f"\nTotal: {len(rows)} payments with 'trade' or 'fibrenew' in payment_method")

# Now find receipts matching these amounts and dates
if rows:
    print("\n" + "="*80)
    print("Searching for matching FIBRENEW GL 4110 receipts...")
    
    for r in rows:
        amount = r[2]
        pmt_date = r[3]
        
        cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount
            FROM receipts
            WHERE LOWER(vendor_name) LIKE '%fibrenew%'
              AND gl_account_code = '4110'
              AND ABS(gross_amount - %s) < 0.01
              AND ABS(EXTRACT(DAY FROM (receipt_date - %s::date))) <= 7
        """, (amount, pmt_date))
        
        matches = cur.fetchall()
        if matches:
            for m in matches:
                print(f"  Payment {r[0]} (${amount:,.2f} on {pmt_date}) → Receipt {m[0]} (${m[2]:,.2f} on {m[1]})")

cur.close()
conn.close()
