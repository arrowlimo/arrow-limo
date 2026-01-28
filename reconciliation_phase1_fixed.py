"""
CRITICAL RECONCILIATION AUDIT: Charter-Payment-Banking Matching
Phase 1: Banking payments → Charter matching
========================================================================

SCHEMA REFERENCE:
- banking_transactions: transaction_id, credit_amount (deposits), debit_amount (withdrawals)
- payments: payment_id, reserve_number (KEY!), amount, payment_date
- charters: charter_id, reserve_number, total_amount_due, balance

BUSINESS RULE: reserve_number is the business key for charter-payment linking
"""

import os
import psycopg2
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("RECONCILIATION AUDIT PHASE 1: Banking → Payments → Charters")
print("=" * 120)

# ============================================================================
# STEP 1: Get all banking deposits (credit_amount > 0)
# ============================================================================

print("\n[STEP 1] BANKING DEPOSITS (Source of Truth)")
print("-" * 120)

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        credit_amount,
        description,
        vendor_extracted,
        category
    FROM banking_transactions
    WHERE credit_amount > 0
        AND transaction_date >= '2012-01-01'
    ORDER BY transaction_date DESC
    LIMIT 1000
""")

banking_deposits = cur.fetchall()
print(f"✅ Found {len(banking_deposits)} banking deposits")

# ============================================================================
# STEP 2: Try to match each banking deposit to a payment
# ============================================================================

print("\n[STEP 2] MATCH BANKING DEPOSITS → PAYMENTS")
print("-" * 120)

matched_count = 0
unmatched_deposits = []
overpayments = []

for trans_id, trans_date, amount, desc, vendor, category in banking_deposits:
    # Find payment matching this amount (within $0.01) and within 7 days
    cur.execute("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.amount,
            p.payment_date,
            p.payment_method
        FROM payments p
        WHERE ABS(p.amount - %s) < 0.01
            AND ABS(p.payment_date - %s) <= 7
        LIMIT 1
    """, (amount, trans_date))
    
    payment = cur.fetchone()
    
    if payment:
        pmt_id, reserve, pmt_amt, pmt_date, pmt_method = payment
        matched_count += 1
        
        # Now check if this charter is overpaid
        cur.execute("""
            SELECT 
                c.charter_id,
                c.total_amount_due,
                COALESCE(SUM(p2.amount), 0) as total_payments
            FROM charters c
            LEFT JOIN payments p2 ON p2.reserve_number = c.reserve_number
            WHERE c.reserve_number = %s
            GROUP BY c.charter_id, c.total_amount_due
        """, (reserve,))
        
        charter_data = cur.fetchone()
        if charter_data:
            charter_id, due, total_paid = charter_data
            # Convert to float for comparison
            due_f = float(due) if due else 0
            total_paid_f = float(total_paid) if total_paid else 0
            
            if total_paid_f > due_f + 0.01:
                overpayments.append({
                    'banking_id': trans_id,
                    'banking_date': trans_date,
                    'banking_amount': float(amount),
                    'charter_id': charter_id,
                    'reserve': reserve,
                    'due': due_f,
                    'total_paid': total_paid_f,
                    'overpayment': total_paid_f - due_f
                })
    else:
        # Banking deposit has NO matching payment - CRITICAL ISSUE
        unmatched_deposits.append({
            'banking_id': trans_id,
            'date': trans_date,
            'amount': amount,
            'description': desc,
            'vendor': vendor,
            'category': category
        })

print(f"✅ Matched to payments: {matched_count}")
print(f"⚠️  UNMATCHED deposits (no payment found): {len(unmatched_deposits)}")
print(f"⚠️  Overpayment charters: {len(overpayments)}")

# ============================================================================
# STEP 3: Show unmatched banking deposits (CRITICAL)
# ============================================================================

if unmatched_deposits:
    print("\n[CRITICAL] UNMATCHED BANKING DEPOSITS")
    print("-" * 120)
    print(f"{'BankID':<8} {'Date':<12} {'Amount':<15} {'Description':<45} {'Vendor':<20}")
    print("-" * 120)
    
    total_unmatched = 0
    for item in unmatched_deposits[:30]:
        desc_short = str(item['description'])[:43]
        vendor_short = str(item['vendor'])[:18] if item['vendor'] else "UNKNOWN"
        print(f"{item['banking_id']:<8} {str(item['date']):<12} ${item['amount']:>13.2f} {desc_short:<45} {vendor_short:<20}")
        total_unmatched += item['amount']
    
    if len(unmatched_deposits) > 30:
        print(f"... and {len(unmatched_deposits) - 30} more")
    print(f"\nTotal unmatched amount: ${total_unmatched:,.2f}")

# ============================================================================
# STEP 4: Check for overpayments
# ============================================================================

if overpayments:
    print("\n[OVERPAYMENTS] Charters with payments > due")
    print("-" * 120)
    print(f"{'BankID':<8} {'Charter':<10} {'Reserve':<10} {'Due':<12} {'Paid':<12} {'Overpay':<12}")
    print("-" * 120)
    
    total_overpay = 0
    for item in overpayments[:20]:
        print(f"{item['banking_id']:<8} {item['charter_id']:<10} {item['reserve']:<10} ${item['due']:>10.2f} ${item['total_paid']:>10.2f} ${item['overpayment']:>10.2f}")
        total_overpay += item['overpayment']
    
    if len(overpayments) > 20:
        print(f"... and {len(overpayments) - 20} more")
    print(f"\nTotal overpayment amount: ${total_overpay:,.2f}")

# ============================================================================
# STEP 5: Reverse check - Charters with payments but no banking match
# ============================================================================

print("\n[STEP 5] REVERSE CHECK: Payments with no banking deposit")
print("-" * 120)

cur.execute("""
    SELECT 
        p.payment_id,
        p.reserve_number,
        p.amount,
        p.payment_date,
        c.charter_id,
        c.total_amount_due
    FROM payments p
    LEFT JOIN charters c ON p.reserve_number = c.reserve_number
    WHERE p.payment_date >= '2012-01-01'
        AND NOT EXISTS (
            SELECT 1 FROM banking_transactions bt
            WHERE ABS(bt.credit_amount - p.amount) < 0.01
                AND ABS(bt.transaction_date - p.payment_date) <= 7
        )
    LIMIT 100
""")

unmatched_payments = cur.fetchall()
print(f"⚠️  Payments with NO banking deposit: {len(unmatched_payments)}")

if unmatched_payments:
    print(f"\n{'PaymentID':<12} {'Reserve':<10} {'Amount':<12} {'Date':<12} {'Charter':<10} {'Due':<12}")
    print("-" * 120)
    for pmt_id, reserve, amount, pmt_date, charter_id, due in unmatched_payments[:20]:
        print(f"{pmt_id:<12} {reserve:<10} ${amount:>10.2f} {str(pmt_date):<12} {str(charter_id):<10} ${due:>10.2f}")
    
    if len(unmatched_payments) > 20:
        print(f"... and {len(unmatched_payments) - 20} more")

# ============================================================================
# STEP 6: Summary and next steps
# ============================================================================

print("\n" + "=" * 120)
print("PHASE 1 SUMMARY")
print("=" * 120)

print(f"""
FINDINGS:

1. BANKING DEPOSITS ANALYZED: {len(banking_deposits)}
   Matched to payments: {matched_count}
   UNMATCHED (critical): {len(unmatched_deposits)}
   
2. UNMATCHED DEPOSITS TOTAL: ${sum(d['amount'] for d in unmatched_deposits):,.2f}
   Action: These deposits are in the bank but no payment record exists
   Next: Find which charter(s) they belong to
   
3. OVERPAYMENTS FOUND: {len(overpayments)}
   Total overpay amount: ${sum(o['overpayment'] for o in overpayments):,.2f}
   Action: Verify these are retainers or legitimate
   
4. PAYMENTS WITHOUT BANKING: {len(unmatched_payments)}
   Action: These payments exist in DB but no bank deposit found
   Possible causes: Not yet deposited, manual entry error, or banking data missing
   
NEXT STEPS:
1. Continue to PHASE 2: Reverse reconciliation (Charter → Payment → Banking)
2. Categorize all overpayments as: retainer, rounding, or actual
3. Fix penny-rounding discrepancies ($0.01)
4. Restore any incorrectly deleted charges
5. Generate fix script for remaining issues
""")

print("=" * 120)

# Save unmatched for detailed review
now = datetime.now().strftime("%Y%m%d_%H%M%S")
with open(f"unmatched_deposits_{now}.csv", 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['BankingID', 'Date', 'Amount', 'Description', 'Vendor', 'Category'])
    for item in unmatched_deposits:
        writer.writerow([
            item['banking_id'],
            item['date'],
            item['amount'],
            item['description'],
            item['vendor'],
            item['category']
        ])
print(f"\n✅ Unmatched deposits saved to: unmatched_deposits_{now}.csv")

cur.close()
conn.close()
