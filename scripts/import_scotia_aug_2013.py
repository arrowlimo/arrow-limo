"""
Import Scotia Bank August 2013 transactions from pasted statement data.

This script processes the manually pasted transaction data to import into banking_transactions.
Includes vendor extraction, categorization, and duplicate prevention.
"""

import psycopg2
import hashlib
import re
from datetime import datetime
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def generate_hash(date, description, amount):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def extract_vendor_from_description(description):
    """Extract vendor name from transaction description."""
    if not description:
        return None
    
    # POS Purchase patterns
    if 'POS Purchase' in description or 'POS PURCHASE' in description.upper():
        match = re.search(r'(?:POS Purchase|POS PURCHASE)\s+(.+?)(?:\s+RED D|\s+EDMON|\s+CALGA|\s+SYLVA|\s+COMPARED D|$)', description, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
            # Remove trailing location codes
            vendor = re.sub(r'\s+(RED D|EDMON|CALGA|SYLVA|COMPARED D)$', '', vendor, flags=re.IGNORECASE)
            return vendor
    
    # Rent/Lease patterns
    if 'Rent/Lease' in description or 'RenULease' in description:
        match = re.search(r'(?:Rent/Lease|RenULease)\s+(.+?)$', description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Insurance patterns
    if 'Insurance' in description:
        match = re.search(r'Insurance\s+(.+?)$', description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Bill Payment patterns
    if 'Bill Payment' in description:
        match = re.search(r'Bill Payment\s+PC-(.+?)\s+\d+', description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Cheque patterns
    if 'Cheque' in description:
        match = re.search(r'Cheque\s+(\d+)', description, re.IGNORECASE)
        if match:
            return f"Cheque {match.group(1)}"
    
    # Merchant Deposit patterns
    if 'Merchant Deposit' in description:
        match = re.search(r'(\d+)\s+00001\s+(VISA|MCARD|DEBITCD)', description)
        if match:
            return f"Merchant {match.group(2)}"
    
    # Miscellaneous Payment patterns (AMEX, etc)
    if 'Miscellaneous Payment' in description:
        match = re.search(r'Miscellaneous Payment\s+(.+?)$', description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def categorize_transaction(description):
    """Categorize transaction based on description patterns."""
    desc_upper = description.upper()
    
    # Bank fees and charges
    if any(x in desc_upper for x in ['SERVICE CHARGE', 'OVERDRAFT CHARGE', 'OVERDRAWN HANDLING', 'NSF']):
        return 'BANK_FEE'
    
    # Returned cheques / NSF
    if 'RETURNED CHEQUE' in desc_upper or 'NSF' in desc_upper:
        return 'JOURNAL_ENTRY_REVERSAL'
    
    # Credit/Debit memos (reversals or corrections)
    if 'CREDIT MEMO' in desc_upper or 'DEBIT MEMO' in desc_upper:
        if 'EMAIL MONEY' in desc_upper or 'DRAFT PURCHASE' in desc_upper:
            return 'JOURNAL_ENTRY'
        return 'JOURNAL_ENTRY'
    
    # Merchant settlements
    if 'MERCHANT DEPOSIT CREDIT' in desc_upper:
        return 'MERCHANT_SETTLEMENT_CREDIT'
    if 'MERCHANT DEPOSIT DEBIT' in desc_upper:
        return 'MERCHANT_SETTLEMENT_DEBIT'
    
    # Rent/Lease
    if 'RENT/LEASE' in desc_upper or 'RENULEASE' in desc_upper:
        return 'EXPENSE_LEASE'
    
    # Insurance
    if 'INSURANCE' in desc_upper or 'CO OPERATORS' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    # Bill payments
    if 'BILL PAYMENT' in desc_upper or 'BR BILL PAYMENT' in desc_upper:
        return 'EXPENSE_BILL_PAYMENT'
    
    # Fuel purchases
    if any(x in desc_upper for x in ['CENTEX', 'PETRO-CANADA', 'PETRO SNACKS', 'SHELL', 'ESSO', 'HUSKY', "RUN'N ON EMPTY", 'FAS GAS', 'SAFEWAY GAS', 'HUGHES PETROLEUM', 'KHAN GAS']):
        return 'EXPENSE_FUEL'
    
    # Office supplies
    if any(x in desc_upper for x in ['STAPLES', 'PRAIRIE OFFICE']):
        return 'EXPENSE_SUPPLIES'
    
    # Cheque payments
    if 'CHEQUE' in desc_upper and 'RETURNED' not in desc_upper:
        return 'EXPENSE_CHEQUE'
    
    # Miscellaneous payments (AMEX, credit card payments)
    if 'MISCELLANEOUS PAYMENT' in desc_upper:
        if 'AMEX' in desc_upper:
            return 'CREDIT_CARD_PAYMENT'
        if 'PAYMENTECH' in desc_upper:
            return 'MERCHANT_SETTLEMENT_DEBIT'
        return 'EXPENSE_BILL_PAYMENT'
    
    # POS purchases
    if 'POS PURCHASE' in desc_upper:
        return 'EXPENSE_SUPPLIES'
    
    # ABM Withdrawals and Deposits
    if 'ABM WITHDRAWAL' in desc_upper:
        return 'CASH_WITHDRAWAL'
    if 'ABM DEPOSIT' in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    # Deposits
    if 'DEPOSIT' in description and 'MERCHANT' not in desc_upper and 'ABM' not in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    return 'UNCATEGORIZED'

# Transaction data from pasted statement (August 2013)
TRANSACTIONS = [
    ('2013-08-26', 'Bill Payment PC-CAPITAL ONE MASTERCARD 71202596', 250.00, 0),
    ('2013-08-26', 'Service Charge DRAFT PURCHASE', 7.50, 0),
    ('2013-08-26', 'Debit Memo DRAFT PURCHASE', 2757.00, 0),
    ('2013-08-26', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 109.54, 0),
    ('2013-08-26', 'POS Purchase 604 - LB 67TH ST. RED D', 482.12, 0),
    ('2013-08-26', 'POS Purchase C05896 PETRO SNACKS RO ROCKY', 57.51, 0),
    ('2013-08-26', 'POS Purchase FAS GAS EASTHILL SVC# RED D', 80.59, 0),
    ('2013-08-26', 'ABM Withdrawal', 200.00, 0),
    ('2013-08-26', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 2608.44),
    ('2013-08-26', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 552.25),
    ('2013-08-26', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 431.82),
    ('2013-08-26', 'Deposit', 0, 500.00),
    ('2013-08-23', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 280.00),
    ('2013-08-23', 'Deposit', 0, 760.00),
    ('2013-08-22', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-08-22', 'Cheque 226', 831.00, 0),
    ('2013-08-22', 'Cheque 225', 200.00, 0),
    ('2013-08-22', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1013.65),
    ('2013-08-22', 'ABM Deposit', 0, 40.00),
    ('2013-08-21', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 205.00),
    ('2013-08-21', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 332.50),
    ('2013-08-20', 'Overdrawn Handling Chg.', 5.00, 0),
    ('2013-08-20', 'Cheque 224', 1575.00, 0),
    ('2013-08-20', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 575.00),
    ('2013-08-20', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 525.00),
    ('2013-08-19', 'Miscellaneous Payment AMEX BANK OF CANADA', 435.21, 0),
    ('2013-08-19', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 794.78),
    ('2013-08-19', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 2848.02),
    ('2013-08-19', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 933.01),
    ('2013-08-19', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 500.00),
    ('2013-08-19', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 124.03),
    ('2013-08-19', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 479.08),
    ('2013-08-16', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 811.13),
    ('2013-08-16', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 175.00),
    ('2013-08-15', 'Overdrawn Handling Chg.', 30.00, 0),
    ('2013-08-15', 'Rent/Lease HEFFNER AUTO FC', 471.97, 0),
    ('2013-08-15', 'Rent/Lease HEFFNER AUTO FC', 889.88, 0),
    ('2013-08-15', 'Rent/Lease HEFFNER AUTO FC', 1900.50, 0),
    ('2013-08-15', 'Rent/Lease HEFFNER AUTO FC', 1475.25, 0),
    ('2013-08-15', 'Rent/Lease HEFFNER AUTO FC', 2525.25, 0),
    ('2013-08-15', 'Rent/Lease JACK CARTER', 1885.65, 0),
    ('2013-08-15', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 195.00),
    ('2013-08-14', 'Cheque 223', 200.00, 0),
    ('2013-08-14', 'Bill Payment PC-IFS FINANCIAL SERVICES 48933856', 400.00, 0),
    ('2013-08-14', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 65.30, 0),
    ('2013-08-14', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 32.00, 0),
    ('2013-08-14', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 68.07, 0),
    ('2013-08-14', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1177.69),
    ('2013-08-14', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 205.00),
    ('2013-08-13', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 82.69),
    ('2013-08-13', 'Bill Payment PC-IFS FINANCIAL SERVICES 47838937', 2074.74, 0),
    ('2013-08-13', 'POS Purchase CRYSTAL GLASS CANADA L RED D', 274.14, 0),
    ('2013-08-13', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 261.53),
    ('2013-08-13', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 652.14),
    ('2013-08-13', 'Deposit', 0, 1200.00),
    ('2013-08-12', 'Cheque 222', 1095.09, 0),
    ('2013-08-12', 'Service Charge', 1.50, 0),
    ('2013-08-12', 'Service Charge', 1.50, 0),
    ('2013-08-12', 'Service Charge DRAFT PURCHASE', 7.50, 0),
    ('2013-08-12', 'Debit Memo DRAFT PURCHASE', 2000.00, 0),
    ('2013-08-12', 'POS Purchase PET PLANET - RED DEER RED D', 61.94, 0),
    ('2013-08-12', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 31.00, 0),
    ('2013-08-12', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 9.00, 0),
    ('2013-08-12', 'POS Purchase C00367- KHAN GAS COMPARED D', 130.07, 0),
    ('2013-08-12', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 117.00, 0),
    ('2013-08-12', 'ABM Withdrawal', 201.50, 0),
    ('2013-08-12', 'ABM Withdrawal', 162.00, 0),
    ('2013-08-12', 'ABM Withdrawal', 200.00, 0),
    ('2013-08-12', 'Miscellaneous Payment AMEX BANK OF CANADA', 421.25, 0),
    ('2013-08-12', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1167.59),
    ('2013-08-12', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 489.00),
    ('2013-08-12', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 744.50),
    ('2013-08-12', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 218.40),
    ('2013-08-09', 'POS Purchase FAS GAS WESTPARK SVC# RED D', 44.21, 0),
    ('2013-08-09', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 351.98),
    ('2013-08-09', 'POS Purchase STAPLES#285 RED D', 13.65, 0),
    ('2013-08-09', 'POS Purchase 604 - LB 67TH ST. RED D', 195.17, 0),
    ('2013-08-09', 'POS Purchase SUMMIT ESSO RED D', 65.01, 0),
    ('2013-08-08', 'POS Purchase GEORGE\'S PIZZA AND STE RED D', 44.31, 0),
    ('2013-08-08', 'POS Purchase CO OPERATORS #11022 RED D', 129.00, 0),
    ('2013-08-08', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 780.79),
    ('2013-08-07', 'Cheque 221', 2156.81, 0),
    ('2013-08-07', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 59.00, 0),
    ('2013-08-07', 'POS Purchase ERLES AUTO REPAIR RED D', 1000.00, 0),
    ('2013-08-07', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 472.06),
    ('2013-08-07', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 205.00),
    ('2013-08-06', 'Miscellaneous Payment AMEX BANK OF CANADA', 477.55, 0),
    ('2013-08-06', 'POS Purchase 604 - LB 67TH ST. RED D', 281.90, 0),
    ('2013-08-06', 'POS Purchase CENTEX EASTVIEW(C-STOR RED D', 29.38, 0),
    ('2013-08-06', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 480.00),
    ('2013-08-06', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1196.02),
    ('2013-08-06', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 55.00),
    ('2013-08-06', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 205.00),
    ('2013-08-06', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 346.50),
    ('2013-08-02', 'Miscellaneous Payment PAYMENTECH CA MCARD FEE DR', 314.24, 0),
    ('2013-08-02', 'Miscellaneous Payment PAYMENTECH CA VISA DEP DR', 711.12, 0),
    ('2013-08-02', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 436.53),
    ('2013-08-01', 'POS Purchase FAS GAS WESTPARK SVC# RED D', 55.00, 0),
    ('2013-08-01', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 207.85),
    ('2013-08-01', 'Cheque 220', 500.00, 0),
    ('2013-08-01', 'Rent/Lease HEFFNER AUTO FC', 471.98, 0),
    ('2013-08-01', 'Rent/Lease HEFFNER AUTO FC', 889.87, 0),
    ('2013-08-01', 'Rent/Lease ACE TRUCK RENTALS LTD.', 2695.40, 0),
    ('2013-08-01', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 1810.00),
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia August 2013 transactions')
    parser.add_argument('--write', action='store_true', help='Actually write to database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check for existing transactions to prevent duplicates
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2013-08-01'
        AND transaction_date <= '2013-08-31'
    """)
    existing_hashes = {row[0] for row in cur.fetchall() if row[0]}
    
    print(f"Found {len(existing_hashes)} existing transactions in database for August 2013")
    
    # Process transactions
    to_import = []
    duplicates = 0
    
    for date_str, description, debit, credit in TRANSACTIONS:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        amount = debit if debit > 0 else credit
        source_hash = generate_hash(date, description, amount)
        
        if source_hash in existing_hashes:
            duplicates += 1
            continue
        
        vendor = extract_vendor_from_description(description)
        category = categorize_transaction(description)
        
        to_import.append({
            'date': date,
            'description': description,
            'debit': debit if debit > 0 else None,
            'credit': credit if credit > 0 else None,
            'vendor': vendor,
            'category': category,
            'hash': source_hash
        })
    
    print(f"\nTransactions to import: {len(to_import)}")
    print(f"Duplicates skipped: {duplicates}")
    
    # Category breakdown
    categories = {}
    for txn in to_import:
        cat = txn['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nCategory breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count}")
    
    # Financial totals
    total_debits = sum(txn['debit'] or 0 for txn in to_import)
    total_credits = sum(txn['credit'] or 0 for txn in to_import)
    print(f"\nTotal debits: ${total_debits:,.2f}")
    print(f"Total credits: ${total_credits:,.2f}")
    print(f"Net: ${total_credits - total_debits:,.2f}")
    
    if args.write:
        print("\n*** WRITING TO DATABASE ***")
        for txn in to_import:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, vendor_extracted, category,
                    source_file, source_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                '903990106011',
                txn['date'],
                txn['description'],
                txn['debit'],
                txn['credit'],
                txn['vendor'],
                txn['category'],
                'STATEMENT_PASTE_AUG_2013',
                txn['hash']
            ))
        
        conn.commit()
        print(f"Successfully imported {len(to_import)} transactions")
    else:
        print("\n*** DRY RUN - Use --write to actually import ***")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
