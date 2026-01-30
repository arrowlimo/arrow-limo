import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get WCB account ID
cur.execute("SELECT account_id FROM vendor_accounts WHERE canonical_vendor = 'WCB'")
vendor_account_id = cur.fetchone()[0]

print(f"WCB Vendor Account ID: {vendor_account_id}\n")

# Simulate what the desktop app shows (from vendor_invoice_manager.py line 1072-1080)
cur.execute("""
    SELECT 
        r.receipt_id,
        r.source_reference,
        r.receipt_date,
        r.gross_amount,
        COALESCE(r.gross_amount, 0) as original_amount
    FROM receipts r
    WHERE r.vendor_name = 'WCB'
    ORDER BY r.receipt_date, r.receipt_id
""")

invoices = cur.fetchall()

print(f"WCB Invoices (as shown in desktop app):\n")
print(f"{'Receipt ID':<12} {'Ref':<20} {'Date':<12} {'Amount':<12} {'Paid':<12} {'Balance':<12} {'Status'}")
print("-" * 110)

total_invoiced = 0.0
total_paid = 0.0
total_balance = 0.0

for inv in invoices:
    receipt_id, ref, date, amount, orig_amt = inv
    orig_amt = float(orig_amt) if orig_amt is not None else 0.0
    
    # Query vendor ledger for payments on this receipt
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_paid
        FROM vendor_account_ledger
        WHERE account_id = %s
        AND source_id = %s
        AND entry_type = 'PAYMENT'
    """, (vendor_account_id, str(receipt_id)))
    
    paid_result = cur.fetchone()
    paid = float(paid_result[0]) if paid_result and paid_result[0] else 0.0
    
    # Balance is what's left to pay (negative payment amounts are already payments)
    balance = orig_amt + paid  # paid is negative, so this gives us the remaining
    balance = max(balance, 0.0)  # Never negative
    
    status = "✅ Paid" if balance < 0.01 else "❌ Unpaid"
    
    ref_str = ref[:18] if ref else "N/A"
    total_invoiced += orig_amt
    total_paid += abs(paid) if paid < 0 else 0.0
    total_balance += balance
    
    print(f"{receipt_id:<12} {ref_str:<20} {date} ${orig_amt:>10,.2f} ${abs(paid):>10,.2f} ${balance:>10,.2f} {status}")

print("-" * 110)
print(f"{'TOTALS:':<54} ${total_invoiced:>10,.2f} ${total_paid:>10,.2f} ${total_balance:>10,.2f}")

cur.close()
conn.close()
