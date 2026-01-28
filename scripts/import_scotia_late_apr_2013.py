"""
Import Scotia Bank late April 2013 transactions from manual entry.
Based on statement screenshots showing transactions from Apr 15-29, 2013.
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
    
    if any(x in desc_upper for x in ['DEP CR', 'DEBITCD DEP CR', 'MCARD DEP CR', 'VISA DEP CR', 'DEP DR']):
        return 'MERCHANT_SETTLEMENT_CREDIT'
    
    if 'NSF' in desc_upper:
        if 'RETURNED' in desc_upper or 'CHEQUE' in desc_upper:
            return 'REVENUE_REVERSAL'
        elif 'CHARGE' in desc_upper or 'FEE' in desc_upper:
            return 'BANK_FEE'
    
    if any(x in desc_upper for x in ['SERVICE CHARGE', 'OVERDRAFT', 'OVERDRAWN', 'INTERAC ABM FEE']):
        return 'BANK_FEE'
    
    if 'AUTO LEASE' in desc_upper or 'HEFFNER' in desc_upper or 'RENT/LEASES' in desc_upper:
        return 'EXPENSE_LEASE'
    
    if 'INSURANCE' in desc_upper or 'JEVCO' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    if any(x in desc_upper for x in ['FAS GAS', 'CENTEX', 'PETRO', 'SHELL', 'ESSO']):
        return 'EXPENSE_FUEL'
    
    if 'POINT OF SALE' in desc_upper or 'POS PURCHASE' in desc_upper:
        if any(x in desc_upper for x in ['MCDONALD', 'SHOE', 'SAVE ON FOODS', 'PHIL', 'CHAPTERS', 'SOBEYS', 'ARBYS', 'SAFEWAY']):
            return 'EXPENSE_MEALS'
        elif any(x in desc_upper for x in ['604 - LB', '606 - LD', 'GAETZ', 'MONEY MART', 'CANADIAN TIRE', 'STAPLES', 'WAL-MART', 'CALGARY AIRPORT']):
            return 'EXPENSE_SUPPLIES'
        return 'EXPENSE_GENERAL'
    
    if desc_upper.startswith('CHQ ') or desc_upper.startswith('CHO ') or 'CHEQUE' in desc_upper:
        return 'EXPENSE_CHEQUE'
    
    if 'DEBIT MEMO' in desc_upper:
        return 'JOURNAL_ENTRY_DEBIT'
    if 'CREDIT MEMO' in desc_upper:
        return 'JOURNAL_ENTRY_CREDIT'
    
    if 'ABM WITHDRAWAL' in desc_upper or 'CASH' in desc_upper or 'SHARED ABM' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    if 'MISC PAYMENT' in desc_upper or 'PC BILL PAYMENT' in desc_upper:
        if 'AMEX' in desc_upper:
            return 'CREDIT_CARD_PAYMENT'
        return 'PAYMENT'
    
    if 'DEPOSIT' in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    return 'UNCATEGORIZED'

def extract_vendor(description):
    """Extract vendor name from description."""
    desc_upper = description.upper()
    
    if 'CHASE PAYMENTECH' in desc_upper or 'PAYMENTECH CA' in desc_upper:
        return 'Chase Paymentech'
    if 'AMEX BANK' in desc_upper:
        return 'Amex Bank of Canada'
    if 'FAS GAS' in desc_upper:
        return 'Fas Gas'
    if 'CENTEX' in desc_upper:
        return 'Centex'
    if 'HEFFNER AUTO' in desc_upper:
        return 'Heffner Auto Finance'
    if 'JACK CARTER' in desc_upper:
        return 'Jack Carter'
    if 'ACE TRUCK' in desc_upper:
        return 'Ace Truck Rentals'
    if 'JEVCO' in desc_upper:
        return 'Jevco Insurance'
    if 'IFS FINANCIAL' in desc_upper:
        return 'IFS Financial Services'
    if 'CAPITAL ONE' in desc_upper:
        return 'Capital One Mastercard'
    if '604 - LB' in desc_upper or '606 - LD' in desc_upper or 'GAETZ' in desc_upper:
        return 'Gaetz & 67th'
    if 'CANADIAN TIRE' in desc_upper:
        return 'Canadian Tire'
    if 'STAPLES' in desc_upper:
        return 'Staples'
    if 'SAFEWAY' in desc_upper or 'CANADA SAFEWAY' in desc_upper:
        return 'Safeway'
    if 'MONEY MART' in desc_upper:
        return 'Money Mart'
    if 'WAL-MART' in desc_upper:
        return 'Wal-Mart'
    if 'SHOE CHALET' in desc_upper:
        return 'Shoe Chalet'
    if 'MCDONALD' in desc_upper:
        return "McDonald's"
    if 'SAVE ON FOODS' in desc_upper:
        return 'Save On Foods'
    if 'PHIL' in desc_upper and 'RESTAURANT' in desc_upper:
        return 'Phils Restaurant'
    if 'CHAPTERS' in desc_upper:
        return 'Chapters'
    if 'SOBEYS' in desc_upper:
        return 'Sobeys'
    if 'ARBYS' in desc_upper or 'ARBY' in desc_upper:
        return "Arby's"
    if 'CALGARY AIRPORT' in desc_upper:
        return 'Calgary Airport'
    if 'COMMUNICATIONS GROUP' in desc_upper:
        return 'Communications Group'
    if 'RED DEER BRANCH' in desc_upper or 'LANCASTER CENTER' in desc_upper:
        return 'Scotiabank ATM'
    if 'SHARED ABM' in desc_upper and 'INTERAC' in desc_upper:
        return 'Interac ATM'
    
    if desc_upper.startswith('CHQ ') or desc_upper.startswith('CHO '):
        import re
        chq_match = re.search(r'CH[QO]\*?\s+(\d+)', desc_upper)
        if chq_match:
            return f'Cheque #{chq_match.group(1)}'
    
    return None

# Transaction data from late April 2013 statements
transactions = [
    # Apr 15 continuation
    ('2013-04-15', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 457.50),
    ('2013-04-15', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 557.50),
    ('2013-04-15', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1032.50),
    ('2013-04-15', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 606.00),
    ('2013-04-15', 'AUTO LEASE L08136 JACK CARTER', -188.565, None),
    ('2013-04-15', 'AUTO LEASE HEFFNER AUTO FC', -252.525, None),
    ('2013-04-15', 'AUTO LEASE HEFFNER AUTO FC', -147.525, None),
    ('2013-04-15', 'AUTO LEASE HEFFNER AUTO FC', -190.050, None),
    ('2013-04-15', 'AUTO LEASE HEFFNER AUTO FC', -88.988, None),
    ('2013-04-15', 'AUTO LEASE HEFFNER AUTO FC', -471.97, None),
    ('2013-04-15', 'PC BILL PAYMENT IFS FINANCIAL SERVICES 87383701', -2474.74, None),
    ('2013-04-15', 'PC BILL PAYMENT CAPITAL ONE MASTERCARD 87393966', -160.00, None),
    ('2013-04-15', 'OVERDRAWN HANDLING CHGS', -25.00, None),
    ('2013-04-15', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 250.00),
    ('2013-04-15', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-04-16', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 350.00),
    ('2013-04-16', 'CREDIT MEMO RETURN PICS OTHER', None, 88.988),
    ('2013-04-16', 'CREDIT MEMO RETURN PICS OTHER', None, 190.050),
    ('2013-04-16', 'CREDIT MEMO RETURN PICS OTHER', None, 147.525),
    ('2013-04-16', 'CREDIT MEMO RETURN PICS OTHER', None, 252.525),
    ('2013-04-16', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 205.00),
    ('2013-04-17', 'POINT OF SALE PURCHASE FAS GAS EASTHILL SVC # RED DEER ABCA', -50.00, None),
    ('2013-04-17', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -10.06, None),
    ('2013-04-17', 'POINT OF SALE PURCHASE CANADIAN TIRE #329 RED DEER ABCA', -34.64, None),
    ('2013-04-17', 'DEPOSIT', None, 487.50),
    ('2013-04-17', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 367.49),
    ('2013-04-17', 'POINT OF SALE PURCHASE MCDONALD\'S #9200 RED DEER ABCA', -8.32, None),
    ('2013-04-17', 'POINT OF SALE PURCHASE MONEY MART #1205 RED DEER ABCA', -240.00, None),
    ('2013-04-17', 'POINT OF SALE PURCHASE STAPLES#285 RED DEER ABCA', -125.69, None),
    ('2013-04-17', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -46.00, None),
    ('2013-04-18', 'DEBIT MEMO CASH OTHER', -150.00, None),
    ('2013-04-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 651.00),
    ('2013-04-19', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -100.00, None),
    ('2013-04-19', 'CHQ 173 3700055438', -89.00, None),
    ('2013-04-19', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -632.74, None),
    ('2013-04-19', 'POINT OF SALE PURCHASE MCDONALD\'S #9062 RED DEER ABCA', -7.01, None),
    ('2013-04-19', 'POINT OF SALE PURCHASE MONEY MART #1205 RED DEER ABCA', -60.00, None),
    ('2013-04-19', 'POINT OF SALE PURCHASE WAL-MART #3075 RED DEER ABCA', -52.60, None),
    ('2013-04-19', 'POINT OF SALE PURCHASE SHOE CHALET RED DEER ABCA', -72.45, None),
    ('2013-04-19', 'DEPOSIT', None, 196.000),
    ('2013-04-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 358.00),
    ('2013-04-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 729.50),
    ('2013-04-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 2000.00),
    ('2013-04-19', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 232.50),
    ('2013-04-19', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-04-19', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -100.00, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -55.62, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE FAS GAS EASTHILL SVC # RED DEER ABCA', -134.81, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -287.66, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -129.00, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -106.01, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -99.01, None),
    ('2013-04-22', 'AUTO LEASE HEFFNER AUTO FC', -252.525, None),
    ('2013-04-22', 'AUTO LEASE HEFFNER AUTO FC', -190.050, None),
    ('2013-04-22', 'AUTO LEASE HEFFNER AUTO FC', -88.988, None),
    ('2013-04-22', 'CHQ 174 3700288468', -500.00, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -71.00, None),
    ('2013-04-22', 'POINT OF SALE PURCHASE MR -LUBE#58 RED DEER ABCA', -62.98, None),
    ('2013-04-23', 'OVERDRAWN HANDLING CHGS', -10.00, None),
    ('2013-04-23', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 205.00),
    ('2013-04-23', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 340.00),
    ('2013-04-24', 'AUTO INSURANCE JEVCO INSURANCE COMPANY', -726.29, None),
    ('2013-04-24', 'OVERDRAWN HANDLING CHGS', -5.00, None),
    ('2013-04-24', 'DEPOSIT GAETZ AND 67TH STREET 51409 002', None, 517.50),
    ('2013-04-24', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 731.00),
    ('2013-04-25', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 1750.00),
    ('2013-04-25', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -332.80, None),
    ('2013-04-25', 'POINT OF SALE PURCHASE NORTH HILL ARBYS Q2P RED DEER ABCA', -13.01, None),
    ('2013-04-25', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -254.54, None),
    ('2013-04-25', 'POINT OF SALE PURCHASE 606 - LD NORTH HILL RED DEER ABCD', -16.89, None),
    ('2013-04-25', 'POINT OF SALE PURCHASE SAVE ON FOODS #6682 RED DEER ABCA', -70.98, None),
    ('2013-04-25', 'PC BILL PAYMENT GAETZ AND 67TH STREET 51409 002', -874.5, None),
    ('2013-04-25', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 175.00),
    ('2013-04-25', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 115.50),
    ('2013-04-26', 'ABM WITHDRAWAL GAETZ & 67TH 3 RED DEER AB', -200.00, None),
    ('2013-04-26', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -140.00, None),
    ('2013-04-26', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -107.93, None),
    ('2013-04-26', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -45.00, None),
    ('2013-04-26', 'POINT OF SALE PURCHASE MCDONALD\'S #9062 RED DEER ABCA', -5.45, None),
    ('2013-04-26', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 529.58),
    ('2013-04-29', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 1742.50),
    ('2013-04-29', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1484.90),
    ('2013-04-29', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 735.00),
    ('2013-04-29', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 392.50),
    ('2013-04-29', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 82.50),
    ('2013-04-29', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 1661.64),
    ('2013-04-29', 'CHO* 24 7800653852', -147.525, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE CALGARY AIRPORT AUTHOR CALGARY ABCA', -51.42, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -125.42, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE CANADA SAFEWAY #808 EDMONTON ABCA', -59.02, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE COMMUNICATIONS GROUP ( RED DEER ABCA', -126.00, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE PHIL\'S RESTAURANTS RED RED DEER ABCA', -49.29, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE CHAPTERS 924 RED DEER ABCA', -64.50, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE GAETZ SOUTH SOBEYS QPS RED DEER ABCD', -109.95, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -149.00, None),
    ('2013-04-29', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -217.15, None),
]

def import_transactions(dry_run=True):
    """Import transactions to banking_transactions table."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    account_number = '903990106011'
    
    cur.execute("SELECT source_hash FROM banking_transactions WHERE source_hash IS NOT NULL")
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    imported = 0
    skipped = 0
    
    for trans_date, description, debit, credit in transactions:
        if debit is not None:
            amount = Decimal(str(debit))
            debit_amount = abs(amount)
            credit_amount = None
        else:
            amount = Decimal(str(credit))
            debit_amount = None
            credit_amount = amount
        
        source_hash = generate_hash(trans_date, description, amount)
        
        if source_hash in existing_hashes:
            skipped += 1
            continue
        
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
    print("Scotia Bank Late April 2013 Import")
    print("=" * 80)
    print(f"Account: 903990106011")
    print(f"Period: April 15-29, 2013")
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
