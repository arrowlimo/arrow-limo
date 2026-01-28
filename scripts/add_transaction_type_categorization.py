#!/usr/bin/env python3
"""
Add transaction_type categorization to Scotia Bank Dec 2013 transactions.
Categorizes transactions as:
  - JOURNAL_ENTRY: Credit Memo OTHER, Debit Memo OTHER, NSF reversals
  - INVOICE_RELATED: POS Purchase, Cheque, Bill Payment, Insurance, Rent/Lease
  - MERCHANT_SETTLEMENT: Merchant Deposit Credit/Debit
  - BANK_FEE: Service Charge, Overdraft Charge, Overdrawn Handling
  - DEPOSIT: Customer deposits
  - CASH_WITHDRAWAL: ABM Withdrawal
  - MISC_PAYMENT: Miscellaneous Payment
"""

import os
import sys
import psycopg2

DRY_RUN = '--write' not in sys.argv
ACCOUNT = '903990106011'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def categorize_transaction(description):
    """
    Categorize transaction based on description pattern.
    Returns tuple: (category, is_journal_entry)
    """
    desc_upper = description.upper()
    
    # JOURNAL ENTRIES - These are NOT invoice-related, they are accounting entries
    if 'DEBIT MEMO OTHER' in desc_upper or 'CREDIT MEMO OTHER' in desc_upper:
        return ('JOURNAL_ENTRY', True)
    
    if 'RETURNED CHEQUE - NSF' in desc_upper or 'NSF' in desc_upper:
        return ('JOURNAL_ENTRY_REVERSAL', True)
    
    # MERCHANT SETTLEMENTS - Card batch processing
    if 'MERCHANT DEPOSIT CREDIT' in desc_upper:
        return ('MERCHANT_SETTLEMENT_CREDIT', False)
    
    if 'MERCHANT DEPOSIT DEBIT' in desc_upper:
        return ('MERCHANT_SETTLEMENT_DEBIT', False)
    
    # BANK FEES
    if any(term in desc_upper for term in ['SERVICE CHARGE', 'OVERDRAFT CHARGE', 'OVERDRAWN HANDLING']):
        return ('BANK_FEE', False)
    
    # INVOICE-RELATED - These are legitimate business expenses
    if 'POS PURCHASE' in desc_upper:
        return ('INVOICE_EXPENSE', False)
    
    if description.startswith('Cheque'):
        return ('INVOICE_EXPENSE_CHEQUE', False)
    
    if 'BILL PAYMENT' in desc_upper:
        return ('INVOICE_EXPENSE_PAYMENT', False)
    
    if 'INSURANCE' in desc_upper:
        return ('INVOICE_EXPENSE_INSURANCE', False)
    
    if 'RENT/LEASE' in desc_upper or 'LEASE' in desc_upper:
        return ('INVOICE_EXPENSE_LEASE', False)
    
    # DEBIT MEMO (non-OTHER) - These are also invoice-related
    if 'DEBIT MEMO' in desc_upper and 'OTHER' not in desc_upper:
        return ('INVOICE_EXPENSE_DEBIT_MEMO', False)
    
    # DEPOSITS
    if description == 'Deposit' or desc_upper.startswith('DEPOSIT'):
        return ('CUSTOMER_DEPOSIT', False)
    
    # CASH WITHDRAWALS
    if 'ABM WITHDRAWAL' in desc_upper:
        return ('CASH_WITHDRAWAL', False)
    
    # MISCELLANEOUS PAYMENTS (Amex, other credit card payments)
    if 'MISCELLANEOUS PAYMENT' in desc_upper:
        if 'AMEX' in desc_upper or 'CREDIT CARD' in desc_upper:
            return ('INVOICE_EXPENSE_CC_PAYMENT', False)
        return ('MISC_PAYMENT', False)
    
    # DEFAULT
    return ('UNCATEGORIZED', False)

def main():
    print("\n" + "="*80)
    print("ADD TRANSACTION TYPE CATEGORIZATION - SCOTIA BANK DEC 2013")
    print("="*80)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get Scotia Dec 2013 transactions
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            category
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_date, transaction_id
    """, (ACCOUNT,))
    
    transactions = cur.fetchall()
    
    print(f"\nTotal Scotia Dec 2013 transactions: {len(transactions)}")
    
    # Categorize
    category_counts = {}
    journal_entries = []
    invoice_related = []
    updates = []
    
    for txn_id, txn_date, description, debit, credit, current_category in transactions:
        new_category, is_journal = categorize_transaction(description)
        
        category_counts[new_category] = category_counts.get(new_category, 0) + 1
        
        if is_journal:
            journal_entries.append((txn_id, txn_date, description, debit, credit, new_category))
        else:
            invoice_related.append((txn_id, txn_date, description, debit, credit, new_category))
        
        # Queue update if category changed
        if current_category != new_category:
            updates.append((new_category, txn_id))
    
    # Print summary
    print("\n" + "="*80)
    print("CATEGORIZATION SUMMARY")
    print("="*80)
    
    print("\nJOURNAL ENTRIES (General Journal - NOT invoice-related):")
    journal_total = sum(1 for _, _, _, _, _, cat in journal_entries)
    print(f"  Total: {journal_total} transactions")
    
    for txn_id, txn_date, description, debit, credit, category in journal_entries:
        amount = debit if debit else credit
        direction = 'DR' if debit else 'CR'
        print(f"    {txn_date} | {direction:2s} ${amount:>10.2f} | {description[:50]:<50} | {category}")
    
    print("\nINVOICE-RELATED (Business expenses/revenue):")
    invoice_total = sum(1 for _, _, _, _, _, cat in invoice_related if not cat.startswith('MERCHANT_SETTLEMENT'))
    print(f"  Total: {invoice_total} transactions")
    
    print("\nCATEGORY BREAKDOWN:")
    print(f"{'Category':<40} {'Count':>10} {'% of Total':>12}")
    print("-"*65)
    
    for category in sorted(category_counts.keys()):
        count = category_counts[category]
        pct = count / len(transactions) * 100
        
        # Highlight journal entries
        marker = " [JOURNAL]" if any(cat for _, _, _, _, _, cat in journal_entries if cat == category) else ""
        
        print(f"{category:<40} {count:>10} {pct:>11.1f}%{marker}")
    
    print(f"\n{'TOTAL':<40} {len(transactions):>10} {100.0:>11.1f}%")
    
    # Show updates needed
    print("\n" + "="*80)
    print(f"UPDATES REQUIRED: {len(updates)} transactions need category update")
    print("="*80)
    
    if DRY_RUN:
        print("\n[DRY RUN] Run with --write to apply categorization.")
        cur.close()
        conn.close()
        return
    
    # Apply updates
    print("\nApplying updates...")
    
    for new_category, txn_id in updates:
        cur.execute("""
            UPDATE banking_transactions
            SET category = %s
            WHERE transaction_id = %s
        """, (new_category, txn_id))
    
    conn.commit()
    print(f"\n[SUCCESS] Updated {len(updates)} transactions with categorization")
    
    # Verify
    cur.execute("""
        SELECT category, COUNT(*)
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        GROUP BY category
        ORDER BY COUNT(*) DESC
    """, (ACCOUNT,))
    
    verification = cur.fetchall()
    
    print("\nVERIFICATION - Categories in database:")
    for category, count in verification:
        print(f"  {category or '(null)':<40} {count:>5} transactions")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
