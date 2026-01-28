"""
Import Scotia Bank March 2013 transactions from manual entry.
Based on statement screenshots showing transactions from Mar 1-21, 2013.
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
    if 'AUTO LEASE' in desc_upper or 'HEFFNER' in desc_upper or 'RENT/LEASES' in desc_upper:
        return 'EXPENSE_LEASE'
    
    # Insurance
    if 'INSURANCE' in desc_upper or 'JEVCO' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    # Fuel
    if any(x in desc_upper for x in ['FAS GAS', 'CENTEX', 'PETRO', 'SHELL', 'ESSO', 'SUMMIT ESSO']):
        return 'EXPENSE_FUEL'
    
    # Point of sale purchases
    if 'POINT OF SALE' in desc_upper or 'POS PURCHASE' in desc_upper:
        if any(x in desc_upper for x in ['SUSHI', 'RESTAURANT', 'FOOD', 'BUFFET']):
            return 'EXPENSE_MEALS'
        elif any(x in desc_upper for x in ['604 - LB', 'GAETZ', 'MONEY MART', 'WAL-MART', 'ELMAC AUTO']):
            return 'EXPENSE_SUPPLIES'
        elif any(x in desc_upper for x in ['GLENDALE SHELL', 'THE RANCH HOUSE']):
            return 'EXPENSE_GENERAL'
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
    if 'ABM WITHDRAWAL' in desc_upper or 'CASH WD' in desc_upper or 'SHARED ABM' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    # Payments
    if 'MISC PAYMENT' in desc_upper:
        if 'AMEX' in desc_upper:
            return 'CREDIT_CARD_PAYMENT'
        return 'PAYMENT'
    
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
    if 'GLENDALE SHELL' in desc_upper:
        return 'Glendale Shell'
    if 'SUMMIT ESSO' in desc_upper:
        return 'Summit Esso'
    
    # Auto services
    if 'HEFFNER AUTO' in desc_upper:
        return 'Heffner Auto Finance'
    if 'JACK CARTER' in desc_upper:
        return 'Jack Carter'
    if 'ACE TRUCK' in desc_upper:
        return 'Ace Truck Rentals'
    if 'ELMAC AUTO' in desc_upper:
        return 'Elmac Auto Electric'
    
    # Insurance
    if 'JEVCO' in desc_upper:
        return 'Jevco Insurance'
    
    # Retail
    if '604 - LB' in desc_upper or 'GAETZ' in desc_upper:
        return 'Gaetz & 67th'
    if 'WAL-MART' in desc_upper:
        return 'Wal-Mart'
    if 'SUSHI' in desc_upper:
        return 'Sushi Restaurant'
    if 'THE RANCH HOUSE' in desc_upper:
        return 'The Ranch House'
    if "MCDONALD'S" in desc_upper:
        return "McDonald's"
    
    # Cash/ATM
    if 'RED DEER BRANCH' in desc_upper or 'LANCASTER CENTER' in desc_upper:
        return 'Scotiabank ATM'
    if 'SHARED ABM' in desc_upper and 'INTERAC' in desc_upper:
        return 'Interac ATM'
    
    # Generic by cheque number
    if desc_upper.startswith('CHQ '):
        import re
        chq_match = re.search(r'CHQ (\d+)', desc_upper)
        if chq_match:
            return f'Cheque #{chq_match.group(1)}'
    
    return None

# Transaction data from March 2013 statements
transactions = [
    # Feb 28 Balance Forward (shown on Mar statement)
    ('2013-02-28', 'DEPOSIT GAETZ AND 67TH STREET 51409 002', None, 137.336),
    ('2013-02-28', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 214.50),
    ('2013-02-28', 'ABM WITHDRAWAL GAETZ & 67TH 3 RED DEER AB', -800.00, None),
    ('2013-02-28', 'RENT/LEASES A0001<DEFTPYMT> ACE TRUCK RENTALS LTD.', -269.540, None),
    ('2013-02-28', 'AUTO LEASE HEFFNER AUTO FC', -88.987, None),
    ('2013-02-28', 'AUTO LEASE HEFFNER AUTO FC', -471.98, None),
    ('2013-02-28', 'CHQ 149 3700272814', -200.00, None),
    ('2013-03-01', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 118.00),
    ('2013-03-01', 'OVERDRAWN HANDLING CHGS', -20.00, None),
    ('2013-03-01', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 231.00),
    ('2013-03-01', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 250.60),
    ('2013-03-01', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 336.20),
    ('2013-03-01', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 171.00),
    ('2013-03-01', 'MISC PAYMENT 0873847000019 PAYMENTECH CA VISA DEP DR', -483.03, None),
    ('2013-03-01', 'MISC PAYMENT 0973847000019 PAYMENTECH CA MCARD FEE DR', -174.52, None),
    ('2013-03-04', 'RETURNED NSF CHEQUE 0973847000019', None, 174.52),
    ('2013-03-04', 'RETURNED NSF CHEQUE 0973847000019', None, 483.03),
    ('2013-03-05', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1329.20),
    ('2013-03-06', 'DEPOSIT', None, 1311.98),
    ('2013-03-06', 'SERVICE CHARGE', -13.21, None),
    ('2013-03-06', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 537.00),
    ('2013-03-06', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-03-06', 'CHQ 152 3700095729', -1000.00, None),
    ('2013-03-06', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 380.24),
    ('2013-03-07', 'POINT OF SALE PURCHASE C44059 GLENDALE SHELL RED DEER ABCA', -145.24, None),
    ('2013-03-07', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -109.26, None),
    ('2013-03-07', 'POINT OF SALE PURCHASE SUMMIT ESSO 88004388 RED DEER ABCA', -56.00, None),
    ('2013-03-07', 'SERVICE CHARGE', -71.79, None),
    ('2013-03-07', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1081.00),
    ('2013-03-07', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 410.00),
    ('2013-03-08', 'ABM WITHDRAWAL GAETZ & 67TH 3 RED DEER AB', -300.00, None),
    ('2013-03-08', 'CHQ 150 3700209780', -600.00, None),
    ('2013-03-08', 'CHQ 151 3700220763', -1049.50, None),
    ('2013-03-08', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', -110.18, None),
    ('2013-03-08', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE', -210.01, None),
    ('2013-03-13', 'POINT OF SALE PURCHASE ELMAC AUTO ELECTRIC LT RED DEER ABCA', -20.80, None),
    ('2013-03-13', 'POINT OF SALE PURCHASE THE RANCH HOUSE RED DEER ABCA', -39.28, None),
    ('2013-03-13', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -84.72, None),
    ('2013-03-13', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -36.66, None),
    ('2013-03-13', 'DEPOSIT', None, 405.00),
    ('2013-03-13', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 205.00),
    ('2013-03-13', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -427.25, None),
    ('2013-03-13', 'CHQ 153 3700515136', -900.00, None),
    ('2013-03-14', 'POINT OF SALE PURCHASE ESSO 880246 WESTSIDE RED DEER ABCA', -100.02, None),
    ('2013-03-14', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -49.01, None),
    ('2013-03-14', 'POINT OF SALE PURCHASE WAL-MART #3075 RED DEER ABCA', -17.61, None),
    ('2013-03-14', 'DEPOSIT', None, 538.22),
    ('2013-03-14', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 350.00),
    ('2013-03-14', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 430.00),
    ('2013-03-14', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -482.50, None),
    ('2013-03-15', 'ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB', -200.00, None),
    ('2013-03-15', 'AUTO LEASE L08136 JACK CARTER', -188.565, None),
    ('2013-03-15', 'AUTO LEASE HEFFNER AUTO FC', -252.525, None),
    # Mar 18
    ('2013-03-18', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 169.950),
    ('2013-03-18', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -1006.88, None),
    ('2013-03-18', 'CREDIT MEMO RETURN PIC NSF OTHER', None, 88.988),
    ('2013-03-18', 'CREDIT MEMO RETURN PIC NSF OTHER', None, 188.565),
    ('2013-03-18', 'CREDIT MEMO RETURN PIC NSF OTHER', None, 252.525),
    ('2013-03-18', 'DEPOSIT', None, 2131.50),
    ('2013-03-19', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -40.00, None),
    ('2013-03-19', 'ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB', -20.00, None),
    ('2013-03-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 143.501),
    ('2013-03-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 410.00),
    ('2013-03-19', 'SHARED ABM WITHDRAWAL VIA INTERAC', -62.00, None),
    ('2013-03-19', 'CHQ* 31 300127361', -252.525, None),
    ('2013-03-20', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', -155.00, None),
    ('2013-03-20', 'POINT OF SALE PURCHASE MCDONALD\'S #9062 RED DEER ABCA', -54.5, None),
    ('2013-03-20', 'RENT/LEASES ABM FEE', -1.50, None),
    ('2013-03-20', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -100.00, None),
    ('2013-03-21', 'CHQ 100 3700373856', -300.00, None),
    ('2013-03-21', 'POINT OF SALE PURCHASE SUSHI SUSHI INTERAC RED DEER ABCA', -27.05, None),
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
    print("Scotia Bank March 2013 Import")
    print("=" * 80)
    print(f"Account: 903990106011")
    print(f"Period: February 28 - March 21, 2013")
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
