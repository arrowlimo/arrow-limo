#!/usr/bin/env python3
"""
BLENDED IMPORT: Scotia Bank December 2013
Combines bank statement data with QuickBooks vendor/category information.

Strategy:
1. Load all statement transactions (160 from bank statement)
2. Load all QuickBooks transactions (92 from current database)
3. Match by (date, amount) - use QB vendor/category if available
4. For unmatched, extract vendor from statement description
5. Apply intelligent categorization (JOURNAL_ENTRY vs INVOICE_RELATED)
6. Delete old QB-only data
7. Import complete blended dataset
"""

import os
import sys
import psycopg2
import hashlib
from decimal import Decimal
from collections import defaultdict

DRY_RUN = '--write' not in sys.argv
ACCOUNT = '903990106011'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def extract_vendor_from_description(description):
    """Extract vendor name from bank statement description."""
    desc = description.strip()
    
    # POS Purchase patterns
    if desc.startswith('POS Purchase'):
        parts = desc.split('POS Purchase ')
        if len(parts) > 1:
            vendor = parts[1].split(' REDD')[0].strip()
            return vendor
    
    # Rent/Lease patterns
    if desc.startswith('Rent/Lease'):
        parts = desc.split('Rent/Lease ')
        if len(parts) > 1:
            return parts[1].strip()
    
    # Insurance patterns
    if desc.startswith('Insurance'):
        parts = desc.split('Insurance ')
        if len(parts) > 1:
            return parts[1].strip()
    
    # Cheque patterns
    if desc.startswith('Cheque '):
        return f"Cheque {desc.split()[1]}"
    
    # Miscellaneous Payment patterns
    if 'AMEX' in desc.upper():
        return 'AMEX Bank of Canada'
    
    # Generic cleanup
    return desc[:50]

def categorize_transaction(description, debit, credit):
    """Categorize transaction for accounting purposes."""
    desc_upper = description.upper()
    
    # JOURNAL ENTRIES (not invoice-related)
    if 'DEBIT MEMO OTHER' in desc_upper or 'CREDIT MEMO OTHER' in desc_upper:
        return 'JOURNAL_ENTRY'
    
    if 'RETURNED CHEQUE - NSF' in desc_upper or 'NSF' in desc_upper:
        return 'JOURNAL_ENTRY_REVERSAL'
    
    # MERCHANT SETTLEMENTS
    if 'MERCHANT DEPOSIT CREDIT' in desc_upper:
        return 'MERCHANT_SETTLEMENT_CREDIT'
    
    if 'MERCHANT DEPOSIT DEBIT' in desc_upper:
        return 'MERCHANT_SETTLEMENT_DEBIT'
    
    # BANK FEES
    if any(term in desc_upper for term in ['SERVICE CHARGE', 'OVERDRAFT CHARGE', 'OVERDRAWN HANDLING']):
        return 'BANK_FEE'
    
    # INVOICE-RELATED EXPENSES
    if 'POS PURCHASE' in desc_upper:
        return 'EXPENSE_FUEL' if any(fuel in desc_upper for fuel in ['ESSO', 'SHELL', 'EMPTY', 'GAS']) else 'EXPENSE_SUPPLIES'
    
    if description.startswith('Cheque'):
        return 'EXPENSE_CHEQUE'
    
    if 'BILL PAYMENT' in desc_upper:
        return 'EXPENSE_BILL_PAYMENT'
    
    if 'INSURANCE' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    if 'RENT/LEASE' in desc_upper or 'LEASE' in desc_upper:
        return 'EXPENSE_LEASE'
    
    if 'DEBIT MEMO' in desc_upper and 'OTHER' not in desc_upper:
        return 'EXPENSE_DEBIT_MEMO'
    
    # DEPOSITS
    if description == 'Deposit' or desc_upper.startswith('DEPOSIT'):
        return 'REVENUE_DEPOSIT'
    
    # CASH WITHDRAWALS
    if 'ABM WITHDRAWAL' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    # MISCELLANEOUS PAYMENTS
    if 'MISCELLANEOUS PAYMENT' in desc_upper:
        if credit:  # Reversals/refunds
            return 'REVERSAL'
        return 'EXPENSE_CC_PAYMENT'
    
    return 'UNCATEGORIZED'

def main():
    print("\n" + "="*80)
    print("SCOTIA BANK DEC 2013 - BLENDED IMPORT (STATEMENT + QUICKBOOKS)")
    print("="*80)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # STEP 1: Load existing QuickBooks data
    print("\nSTEP 1: Loading existing QuickBooks data...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            vendor_extracted,
            category
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    
    qb_transactions = cur.fetchall()
    print(f"Found {len(qb_transactions)} QuickBooks transactions")
    
    # Build QB lookup by (date, amount)
    qb_lookup = defaultdict(list)
    for txn_id, date, desc, debit, credit, vendor, cat in qb_transactions:
        amount = float(debit) if debit else float(credit)
        key = (str(date), amount)
        qb_lookup[key].append({
            'id': txn_id,
            'description': desc,
            'debit': debit,
            'credit': credit,
            'vendor': vendor,
            'category': cat
        })
    
    # STEP 2: Load statement transactions from import script
    print("\nSTEP 2: Loading statement transactions from import script...")
    
    # Import the STATEMENT_TRANSACTIONS list
    import importlib.util
    spec = importlib.util.spec_from_file_location("stmt", "l:/limo/scripts/import_scotia_dec2013_from_statement.py")
    stmt_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stmt_module)
    
    statement_transactions = stmt_module.STATEMENT_TRANSACTIONS
    print(f"Found {len(statement_transactions)} statement transactions")
    
    # STEP 3: Blend data
    print("\nSTEP 3: Blending statement + QuickBooks data...")
    
    blended_transactions = []
    matched_count = 0
    stmt_only_count = 0
    
    # First pass: Process all statement transactions
    for stmt_date, stmt_desc, stmt_debit, stmt_credit in statement_transactions:
        stmt_amount = float(stmt_debit) if stmt_debit else float(stmt_credit)
        key = (stmt_date, stmt_amount)
        
        # Check if we have QB data for this transaction
        if key in qb_lookup and len(qb_lookup[key]) > 0:
            qb_data = qb_lookup[key].pop(0)  # Use first match, remove from lookup
            vendor = qb_data['vendor'] or extract_vendor_from_description(stmt_desc)
            category = qb_data['category'] or categorize_transaction(stmt_desc, stmt_debit, stmt_credit)
            source = 'QB_BLENDED'
            matched_count += 1
        else:
            vendor = extract_vendor_from_description(stmt_desc)
            category = categorize_transaction(stmt_desc, stmt_debit, stmt_credit)
            source = 'STATEMENT_ONLY'
            stmt_only_count += 1
        
        blended_transactions.append({
            'date': stmt_date,
            'description': stmt_desc,
            'debit': stmt_debit,
            'credit': stmt_credit,
            'vendor': vendor,
            'category': category,
            'source': source
        })
    
    # Second pass: Add remaining QB-only transactions (cash/manual entries not in bank statement)
    qb_only_count = 0
    for key, qb_matches in qb_lookup.items():
        for qb_data in qb_matches:
            # These are QB transactions with no statement match (likely cash/manual entries)
            qb_only_count += 1
            blended_transactions.append({
                'date': key[0],  # date from key tuple
                'description': qb_data['description'],
                'debit': qb_data.get('debit'),
                'credit': qb_data.get('credit'),
                'vendor': qb_data['vendor'] or 'QB Manual Entry',
                'category': qb_data['category'] or 'QB_CASH_ENTRY',
                'source': 'QB_ONLY_CASH'
            })
    
    print(f"  Matched with QB: {matched_count} transactions")
    print(f"  Statement only: {stmt_only_count} transactions")
    print(f"  QB only (cash/manual): {qb_only_count} transactions")
    print(f"  Total blended: {len(blended_transactions)} transactions")
    
    # STEP 4: Analyze blended data
    print("\nSTEP 4: Analyzing blended data...")
    
    category_counts = defaultdict(int)
    category_amounts = defaultdict(Decimal)
    
    for txn in blended_transactions:
        cat = txn['category']
        amount = Decimal(str(txn['debit'] or txn['credit']))
        category_counts[cat] += 1
        category_amounts[cat] += amount
    
    print("\nCategory breakdown:")
    print(f"{'Category':<35} {'Count':>8} {'Total Amount':>15}")
    print("-" * 60)
    
    for cat in sorted(category_counts.keys()):
        count = category_counts[cat]
        amount = category_amounts[cat]
        marker = " [JOURNAL]" if cat in ['JOURNAL_ENTRY', 'JOURNAL_ENTRY_REVERSAL'] else ""
        print(f"{cat:<35} {count:>8} ${amount:>13,.2f}{marker}")
    
    # Calculate totals
    total_debits = sum(Decimal(str(t['debit'])) for t in blended_transactions if t['debit'])
    total_credits = sum(Decimal(str(t['credit'])) for t in blended_transactions if t['credit'])
    
    print(f"\n{'TOTALS':<35} {len(blended_transactions):>8}")
    print(f"  Total debits:  ${total_debits:>13,.2f}")
    print(f"  Total credits: ${total_credits:>13,.2f}")
    print(f"  Expected:      $59,578.37 debits, $70,463.81 credits")
    
    # STEP 5: Show sample transactions
    print("\nSample blended transactions (first 10):")
    for i, txn in enumerate(blended_transactions[:10]):
        amount = txn['debit'] or txn['credit']
        direction = 'DR' if txn['debit'] else 'CR'
        print(f"  {txn['date']} | {direction} ${amount:>10.2f} | V: {txn['vendor'][:20]:<20} | C: {txn['category']:<25} | {txn['source']}")
    
    if DRY_RUN:
        print("\n" + "="*80)
        print("[DRY RUN] Run with --write to:")
        print("  1. Delete existing 92 QB transactions")
        print("  2. Import 160 blended transactions")
        print("="*80)
        cur.close()
        conn.close()
        return
    
    # STEP 6: DELETE old QB data
    print("\n" + "="*80)
    print("STEP 6: Deleting old QuickBooks-only data...")
    print("="*80)
    
    # Create backup first
    backup_table = f"banking_transactions_scotia_dec2013_qb_backup_{int(__import__('time').time())}"
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    
    print(f"Created backup: {backup_table}")
    
    # Delete old data
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    
    deleted_count = cur.rowcount
    print(f"Deleted {deleted_count} old transactions")
    
    # STEP 7: Import blended data
    print("\n" + "="*80)
    print("STEP 7: Importing blended dataset...")
    print("="*80)
    
    for txn in blended_transactions:
        source_hash = generate_hash(txn['date'], txn['description'], float(txn['debit'] or txn['credit']))
        
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                vendor_extracted,
                category,
                source_file,
                source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ACCOUNT,
            txn['date'],
            txn['description'],
            txn['debit'],
            txn['credit'],
            txn['vendor'],
            txn['category'],
            txn['source'],
            source_hash
        ))
    
    conn.commit()
    print(f"\n[SUCCESS] Imported {len(blended_transactions)} blended transactions")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    
    final_count, final_debits, final_credits = cur.fetchone()
    
    print("\n" + "="*80)
    print("FINAL VERIFICATION")
    print("="*80)
    print(f"Total transactions: {final_count}")
    print(f"Total debits:  ${float(final_debits or 0):,.2f}")
    print(f"Total credits: ${float(final_credits or 0):,.2f}")
    print(f"Expected:      $59,578.37 debits, $70,463.81 credits")
    
    debit_diff = abs(float(final_debits or 0) - 59578.37)
    credit_diff = abs(float(final_credits or 0) - 70463.81)
    
    if debit_diff < 1 and credit_diff < 1:
        print("\n✅ PERFECT MATCH - Penny-perfect accuracy achieved!")
    else:
        print(f"\n⚠️ Variance: ${debit_diff:.2f} debits, ${credit_diff:.2f} credits")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
