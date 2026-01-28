"""
Import Scotia Bank February 2013 transactions from manual entry.
Based on statement screenshots showing transactions from Feb 11-28, 2013.
"""

import psycopg2
from datetime import date
from decimal import Decimal
import hashlib
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"{date_str}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def categorize_transaction(description):
    """Categorize transaction based on description patterns."""
    desc_upper = description.upper()
    
    # Merchant settlements (credits)
    if any(x in desc_upper for x in ['DEP CR', 'DEBITCD DEP CR', 'MCARD DEP CR', 'VISA DEP CR']):
        return 'MERCHANT_SETTLEMENT_CREDIT'
    
    # NSF related
    if 'NSF' in desc_upper:
        if 'RETURNED' in desc_upper or 'CHEQUE' in desc_upper:
            return 'REVENUE_REVERSAL'
        elif 'CHARGE' in desc_upper or 'FEE' in desc_upper:
            return 'BANK_FEE'
    
    # Bank fees
    if any(x in desc_upper for x in ['SERVICE CHARGE', 'OVERDRAFT', 'OVERDRAWN']):
        return 'BANK_FEE'
    
    # Lease payments
    if 'AUTO LEASE' in desc_upper or 'HEFFNER' in desc_upper:
        return 'EXPENSE_LEASE'
    
    # Insurance
    if 'INSURANCE' in desc_upper or 'JEVCO' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    # Fuel
    if any(x in desc_upper for x in ['FAS GAS', 'CENTEX', 'PETRO', 'SHELL', 'ESSO']):
        return 'EXPENSE_FUEL'
    
    # Point of sale purchases
    if 'POINT OF SALE' in desc_upper or 'POS PURCHASE' in desc_upper:
        if any(x in desc_upper for x in ['CINEPLEX', 'RESTAURANT', 'FOOD', 'SUSHI', 'BUFFET']):
            return 'EXPENSE_MEALS'
        elif any(x in desc_upper for x in ['604 - LB', 'GAETZ', 'MONEY MART', 'COMMUNICATIONS', 'PHARMACY', 'DRUG']):
            return 'EXPENSE_SUPPLIES'
        elif any(x in desc_upper for x in ['ERLES AUTO', 'JIFFY LUBE']):
            return 'EXPENSE_MAINTENANCE'
        return 'EXPENSE_GENERAL'
    
    # Cheques
    if desc_upper.startswith('CHQ ') or 'CHEQUE' in desc_upper:
        return 'EXPENSE_CHEQUE'
    
    # Debit/Credit memos
    if 'DEBIT MEMO' in desc_upper:
        return 'JOURNAL_ENTRY_DEBIT'
    if 'CREDIT MEMO' in desc_upper:
        return 'JOURNAL_ENTRY_CREDIT'
    
    # Cash withdrawals
    if 'ABM WITHDRAWAL' in desc_upper or 'CASH WD' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    # Payments
    if 'MISC PAYMENT' in desc_upper or 'AMEX' in desc_upper:
        return 'CREDIT_CARD_PAYMENT'
    
    # Deposits
    if 'DEPOSIT' in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    return 'UNCATEGORIZED'

def extract_vendor(description):
    """Extract vendor name from description."""
    desc_upper = description.upper()
    
    # Merchant processor
    if 'CHASE PAYMENTECH' in desc_upper:
        return 'Chase Paymentech'
    
    # Banks
    if 'AMEX BANK' in desc_upper:
        return 'Amex Bank of Canada'
    
    # Gas stations
    if 'FAS GAS' in desc_upper:
        return 'Fas Gas'
    if 'CENTEX' in desc_upper:
        return 'Centex'
    
    # Auto services
    if 'HEFFNER AUTO' in desc_upper:
        return 'Heffner Auto Finance'
    if 'JACK CARTER' in desc_upper:
        return 'Jack Carter'
    if 'ACE TRUCK' in desc_upper:
        return 'Ace Truck Rentals'
    if 'ERLES AUTO' in desc_upper:
        return 'Erles Auto Repair'
    if 'JIFFY LUBE' in desc_upper:
        return 'Jiffy Lube'
    
    # Insurance
    if 'JEVCO' in desc_upper:
        return 'Jevco Insurance'
    
    # Retail
    if 'CINEPLEX' in desc_upper:
        return 'Cineplex'
    if '604 - LB' in desc_upper or 'GAETZ' in desc_upper:
        return 'Gaetz & 67th'
    if 'MONEY MART' in desc_upper or 'MONEYMART' in desc_upper:
        return 'Money Mart'
    if 'COMMUNICATIONS GROUP' in desc_upper:
        return 'Communications Group'
    if 'PHARMACY' in desc_upper or 'DRUG' in desc_upper:
        return 'Pharmacy Drug Store'
    if 'SUSHI' in desc_upper:
        return 'Sushi Restaurant'
    if 'BUFFET' in desc_upper:
        return 'Buffet Restaurant'
    if 'ROGERS' in desc_upper:
        return 'Rogers'
    if 'MR SUDS' in desc_upper:
        return 'Mr Suds Inc'
    if 'NATIONAL MONEYMART' in desc_upper:
        return 'National MoneyMart'
    
    # Cash/ATM
    if 'RED DEER BRANCH' in desc_upper or 'LANCASTER CENTER' in desc_upper:
        return 'Scotiabank ATM'
    
    # Generic by cheque number
    if desc_upper.startswith('CHQ '):
        import re
        chq_match = re.search(r'CHQ (\d+)', desc_upper)
        if chq_match:
            return f'Cheque #{chq_match.group(1)}'
    
    return None

# Transaction data from February 2013 statements
transactions = [
    # Feb 11
    ('2013-02-11', 'CHQ 146 3700210850', -1865.36, None),
    ('2013-02-11', 'CHQ 147 3700210851', -27.30, None),
    ('2013-02-11', 'POINT OF SALE PURCHASE CINEPLEX #3132 QPS RED DEER ABCD', -63.59, None),
    ('2013-02-11', 'POINT OF SALE PURCHASE FAS GAS WESTPARK SVC # RED DEER ABCA', -41.58, None),
    ('2013-02-11', 'OVERDRAWN HANDLING CHGS', -25.00, None),
    ('2013-02-11', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 200.00),
    ('2013-02-12', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -2171.25, None),
    ('2013-02-12', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-02-12', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 885.00),
    ('2013-02-13', 'DEBIT MEMO GAETZ AND 67TH STREET 51409 002 CASH WD OTHER', -145.00, None),
    ('2013-02-13', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 720.00),
    ('2013-02-13', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 1332.50),
    ('2013-02-13', 'ABM WITHDRAWAL GAETZ & 67TH 2 RED DEER AB', -160.00, None),
    ('2013-02-13', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -100.00, None),
    ('2013-02-14', 'CHQ 130 3700442842', -770.40, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -58.01, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -59.01, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -53.29, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE FAS GAS EASTHILL SVC # RED DEER ABCA', -50.00, None),
    ('2013-02-14', 'AUTO LEASE L08136 JACK CARTER', -188.565, None),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', -252.525, None),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', -147.525, None),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', -190.050, None),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', -88.988, None),
    ('2013-02-14', 'AUTO LEASE HEFFNER AUTO FC', -471.97, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -37.00, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -105.11, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', -45.00, None),
    ('2013-02-14', 'POINT OF SALE PURCHASE PHARMACY REXALL DRUG STO RED DEER ABCA', -136.69, None),
    ('2013-02-15', 'OVERDRAWN HANDLING CHGS', -35.00, None),
    ('2013-02-15', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 1093.38),
    ('2013-02-15', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 468.00),
    ('2013-02-15', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1591.00),
    ('2013-02-15', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 51.30),
    ('2013-02-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 865.45),
    ('2013-02-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 655.20),
    ('2013-02-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 253.75),
    ('2013-02-19', 'CREDIT MEMO RETURN ITEM OTHER', None, 190.050),
    ('2013-02-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 178.000),
    ('2013-02-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 873.15),
    ('2013-02-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 866.25),
    ('2013-02-20', 'CHQ 141 3900276265', -117.729, None),
    ('2013-02-20', 'DEBIT MEMO DRAFT PURCHASE', -165.000, None),
    ('2013-02-20', 'SERVICE CHARGE', -7.50, None),
    ('2013-02-20', 'OVERDRAWN HANDLING CHGS', -5.00, None),
    ('2013-02-20', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 175.00),
    ('2013-02-20', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 250.00),
    ('2013-02-21', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -277.44, None),
    ('2013-02-21', 'CHQ 136 3700216207', -250.00, None),
    ('2013-02-21', 'OVERDRAWN HANDLING CHGS', -5.00, None),
    ('2013-02-21', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 218.75),
    ('2013-02-22', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 471.90),
    ('2013-02-25', 'DEPOSIT', None, 1494.00),
    ('2013-02-25', 'DEPOSIT 0973847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 192.50),
    ('2013-02-25', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 689.22),
    ('2013-02-25', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 1322.00),
    ('2013-02-25', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 582.50),
    ('2013-02-25', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 811.00),
    ('2013-02-25', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -800.00, None),
    ('2013-02-25', 'ABM WITHDRAWAL GAETZ & 67TH 2 RED DEER AB', -400.00, None),
    ('2013-02-25', 'AUTO INSURANCE JEVCO INSURANCE COMPANY', -726.29, None),
    ('2013-02-25', 'CHQ 144 3700362179', -500.00, None),
    ('2013-02-25', 'CHQ 148 3700432126', -752.70, None),
    ('2013-02-25', 'CHQ 143 3700432506', -636.12, None),
    ('2013-02-25', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -120.23, None),
    ('2013-02-25', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -37.99, None),
    ('2013-02-25', 'POINT OF SALE PURCHASE MONEY MART #1205 RED DEER ABCA', -400.00, None),
    ('2013-02-25', 'POINT OF SALE PURCHASE ROGERS 5680 RED DEER ABCD', -31.49, None),
    ('2013-02-25', 'POINT OF SALE PURCHASE MR SUDS INC. RED DEER ABCA', -47.5, None),
    ('2013-02-25', 'POINT OF SALE PURCHASE NATIONAL MONEYMART #12 RED DEER ABCA', -200.00, None),
    ('2013-02-25', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 200.00),
    ('2013-02-25', 'RETURNED NSF CHEQUE', None, 752.70),
    ('2013-02-25', 'RETURNED NSF CHEQUE', None, 636.12),
    ('2013-02-26', 'NSF SERVICE CHARGE', -42.50, None),
    ('2013-02-27', 'SERVICE CHARGE', -42.50, None),
    ('2013-02-27', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 450.00),
    ('2013-02-27', 'CHQ 134 3700174773', -824.74, None),
    ('2013-02-27', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 150.00),
    ('2013-02-27', 'POINT OF SALE PURCHASE SUSHI SUSHI INTERAC RED DEER ABCA', -27.28, None),
    ('2013-02-28', 'OVERDRAWN HANDLING CHGS', -5.00, None),
    ('2013-02-28', 'SERVICE CHARGE', -122.80, None),
    ('2013-02-28', 'OVERDRAFT INTEREST CHG', -38.13, None),
]

def import_transactions(dry_run=True):
    """Import transactions to banking_transactions table."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    account_number = '903990106011'
    
    # Check for existing hashes
    cur.execute("SELECT source_hash FROM banking_transactions WHERE source_hash IS NOT NULL")
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    imported = 0
    skipped = 0
    
    for trans_date, description, debit, credit in transactions:
        # Determine amount and type
        if debit is not None:
            amount = Decimal(str(debit))
            debit_amount = abs(amount)
            credit_amount = None
        else:
            amount = Decimal(str(credit))
            debit_amount = None
            credit_amount = amount
        
        # Generate hash
        source_hash = generate_hash(trans_date, description, amount)
        
        if source_hash in existing_hashes:
            skipped += 1
            continue
        
        # Categorize and extract vendor
        category = categorize_transaction(description)
        vendor = extract_vendor(description)
        
        if not dry_run:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, category, vendor_extracted,
                    source_hash, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (account_number, trans_date, description, debit_amount, credit_amount,
                  category, vendor, source_hash))
            
            existing_hashes.add(source_hash)
        
        imported += 1
    
    if not dry_run:
        conn.commit()
    
    cur.close()
    conn.close()
    
    return imported, skipped

if __name__ == '__main__':
    import sys
    
    dry_run = '--write' not in sys.argv
    
    print("=" * 80)
    print("Scotia Bank February 2013 Import")
    print("=" * 80)
    print(f"Account: 903990106011")
    print(f"Period: February 11-28, 2013")
    print(f"Mode: {'DRY RUN' if dry_run else 'WRITE'}")
    print()
    
    imported, skipped = import_transactions(dry_run)
    
    print(f"Transactions to import: {imported}")
    print(f"Duplicates skipped: {skipped}")
    print(f"Total in dataset: {len(transactions)}")
    
    if dry_run:
        print()
        print("=" * 80)
        print("Run with --write to import to database")
    else:
        print()
        print("=" * 80)
        print("Import complete!")
