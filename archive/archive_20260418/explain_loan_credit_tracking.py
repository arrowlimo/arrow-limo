"""
Explain loan credit tracking - analyze HEFFNER transactions
"""
import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
cur = conn.cursor()

print("="*90)
print("LOAN CREDIT TRACKING EXPLANATION")
print("="*90)

print("\nCURRENT SITUATION:")
print("We moved 729 HEFFNER loan items to GL 6300 (Loan Principal)")
print("Of those, 290 are CREDITS (money received) = $98,746")
print()

print("[1] Sample HEFFNER CREDITS (money received from/by Heffner):")
cur.execute("""
    SELECT r.receipt_date, bt.credit_amount, bt.description, r.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0 
      AND r.vendor_name = 'HEFFNER AUTO FINANCE'
      AND r.gl_account_code = '6300'
    ORDER BY r.receipt_date
    LIMIT 15
""")
print(f"{'Date':<12} | {'Credit Amt':>12} | {'Bank Description'}")
print("-" * 90)
for date, amt, desc, rdesc in cur.fetchall():
    d_str = (desc or "")[:60]
    print(f"{date} | ${amt:>11,.2f} | {d_str}")

print("\n[2] Sample HEFFNER DEBITS (payments made to Heffner):")
cur.execute("""
    SELECT r.receipt_date, bt.debit_amount, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.debit_amount > 0 
      AND r.vendor_name = 'HEFFNER AUTO FINANCE'
      AND r.gl_account_code = '6300'
    ORDER BY r.receipt_date
    LIMIT 15
""")
print(f"{'Date':<12} | {'Debit Amt':>12} | {'Bank Description'}")
print("-" * 90)
for date, amt, desc in cur.fetchall():
    d_str = (desc or "")[:60]
    print(f"{date} | ${amt:>11,.2f} | {d_str}")

print("\n[3] HEFFNER SUMMARY:")
cur.execute("""
    SELECT 
        COUNT(CASE WHEN bt.credit_amount > 0 THEN 1 END) as credit_count,
        SUM(COALESCE(bt.credit_amount, 0)) as total_credits,
        COUNT(CASE WHEN bt.debit_amount > 0 THEN 1 END) as debit_count,
        SUM(COALESCE(bt.debit_amount, 0)) as total_debits
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'HEFFNER AUTO FINANCE'
      AND r.gl_account_code = '6300'
""")
cr_cnt, cr_amt, db_cnt, db_amt = cur.fetchone()
print(f"  Credits (money IN):  {cr_cnt:>3} transactions = ${cr_amt:>12,.2f}")
print(f"  Debits (money OUT):  {db_cnt:>3} transactions = ${db_amt:>12,.2f}")
print(f"  {'':21} {'-' * 30}")
print(f"  Net paid to Heffner: ${db_amt - cr_amt:>12,.2f}")

print("\n" + "="*90)
print("WHAT THE CREDITS COULD BE:")
print("="*90)
print("""
Option A: LOAN DISBURSEMENTS (company borrowed money)
   - Heffner gave company a vehicle loan
   - Company received cash (or Heffner paid dealer directly)
   - Proper accounting:
     * DEBIT: Cash or Vehicle Asset
     * CREDIT: Loan Payable (LIABILITY account, not expense)
   - These should NOT be in GL 6300 (expense), should be in liability account
   
Option B: NSF REVERSALS (payments bounced)
   - Company made a payment that bounced
   - Bank reversed it and returned the money
   - Proper accounting:
     * The credit reverses the debit payment
     * Net effect = payment didn't happen
   - Can leave in GL 6300, they offset the expense
   
Option C: REFUNDS/CORRECTIONS
   - Overpayments returned
   - Billing errors corrected
   - Can leave in GL 6300, they offset the expense

TRACKING PROPERLY means:
If these are loan disbursements (Option A), move them to a LIABILITY account like:
  - GL 2300: Loans Payable
  - GL 2350: Vehicle Loans Payable
  
If they're reversals/refunds (Options B or C), leave them in GL 6300 where they
offset the payments (reduces total expense).

The $98K difference matters for:
  - Accurate expense reporting (are expenses overstated by $98K?)
  - Loan liability tracking (do we owe Heffner more than we think?)
  - Cash flow analysis (was this money borrowed or money returned?)
""")

print("="*90)
print("NEXT STEPS: Check bank descriptions to determine which option applies")
print("="*90)

cur.close()
conn.close()
