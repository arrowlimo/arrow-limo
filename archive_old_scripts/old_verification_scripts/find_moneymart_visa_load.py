import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', password='ArrowLimousine', dbname='almsdata')
cur = conn.cursor()

print("\n" + "="*80)
print("MONEY MART PREPAID VISA - Sept 12, 2012")
print("Searching for $900 payment and $750 cash transaction")
print("="*80 + "\n")

# Search for Money Mart transactions in September 2012
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           gl_account_code, gl_account_name, description, payment_method
    FROM receipts
    WHERE vendor_name ILIKE '%money%mart%'
    AND receipt_date BETWEEN '2012-09-01' AND '2012-09-30'
    ORDER BY receipt_date, receipt_id
""")

results = cur.fetchall()

if results:
    print(f"Found {len(results)} Money Mart transaction(s) in September 2012:\n")
    for rec_id, date, vendor, amount, gl_code, gl_name, desc, payment_method in results:
        print(f"Receipt ID: {rec_id}")
        print(f"Date: {date}")
        print(f"Vendor: {vendor}")
        print(f"Amount: ${amount:,.2f}")
        print(f"Payment Method: {payment_method or 'N/A'}")
        print(f"Current GL Code: {gl_code or 'NONE'} - {gl_name or 'NO NAME'}")
        print(f"Description: {desc or 'None'}")
        print("-" * 80 + "\n")
else:
    print("No Money Mart transactions found in September 2012\n")
    
    # Try searching all of 2012
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, gl_account_code
        FROM receipts
        WHERE vendor_name ILIKE '%money%mart%'
        AND EXTRACT(YEAR FROM receipt_date) = 2012
        ORDER BY receipt_date
        LIMIT 10
    """)
    
    all_2012 = cur.fetchall()
    if all_2012:
        print(f"Found {len(all_2012)} Money Mart transaction(s) in 2012:")
        for rec_id, date, amount, gl_code in all_2012:
            print(f"  {date}: Receipt {rec_id} - ${amount:,.2f} (GL {gl_code or 'NONE'})")
        print()

# Check if GL 1135 (Prepaid Visa Cards) exists
cur.execute("""
    SELECT account_code, account_name, is_active 
    FROM chart_of_accounts 
    WHERE account_code = '1135'
""")
gl_1135 = cur.fetchone()

print("\n" + "="*80)
print("GL CODE CHECK")
print("="*80)

if gl_1135:
    print(f"✓ GL 1135 exists: {gl_1135[1]}")
    print(f"  Active: {gl_1135[2]}")
else:
    print("✗ GL 1135 (Prepaid Visa Cards) does NOT exist - need to create it")

print("\n" + "="*80)
print("HOW TO HANDLE PREPAID VISA CARD LOADS")
print("="*80)
print("""
Prepaid Visa card loads at Money Mart are ASSET TRANSFERS, not expenses.

CORRECT Accounting Treatment:
────────────────────────────
When you load money onto the prepaid Visa card:
  Debit:  GL 1135 Prepaid Visa Cards (Asset ↑)
  Credit: GL 1010 Cash & Bank Accounts (Asset ↓)

This is like taking $100 from your wallet and putting it in your pocket.
You still have $100, just in a different place. NO EXPENSE.

Later, when you SPEND from the prepaid card (gas, supplies, etc.):
  Debit:  GL 5XXX (Expense - fuel, meals, etc.) (Expense ↑)
  Credit: GL 1135 Prepaid Visa Cards (Asset ↓)

NOW it becomes an expense and hits your Profit & Loss.

Your Transaction ($900 + $750):
────────────────────────────
If both are card loads:
  Total loaded: $1,650 onto prepaid Visa
  GL Entry: Debit 1135 for $1,650, Credit 1010 for $1,650

If $750 is a fee (unlikely - that's 83%!):
  Prepaid load: $900
  Fee: $750
  GL Entry: Debit 1135 for $900, Debit 5710 (Bank Fees) for $750, Credit 1010 for $1,650
""")

conn.close()

print("\n" + "="*80)
print("END OF REPORT")
print("="*80 + "\n")
