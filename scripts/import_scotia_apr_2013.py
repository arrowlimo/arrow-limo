"""
Import Scotia Bank April 2013 transactions from manual entry.
Based on statement screenshots showing transactions from Mar 27 - Apr 15, 2013.
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
    if any(x in desc_upper for x in ['DEP CR', 'DEBITCD DEP CR', 'MCARD DEP CR', 'VISA DEP CR', 'DEP DR']):
        return 'MERCHANT_SETTLEMENT_CREDIT'
    
    # NSF related
    if 'NSF' in desc_upper:
        if 'RETURNED' in desc_upper or 'CHEQUE' in desc_upper:
            return 'REVENUE_REVERSAL'
        elif 'CHARGE' in desc_upper or 'FEE' in desc_upper:
            return 'BANK_FEE'
    
    # Bank fees
    if any(x in desc_upper for x in ['SERVICE CHARGE', 'OVERDRAFT', 'OVERDRAWN', 'INTERAC ABM FEE']):
        return 'BANK_FEE'
    
    # Lease payments
    if 'AUTO LEASE' in desc_upper or 'HEFFNER' in desc_upper or 'RENT/LEASES' in desc_upper:
        return 'EXPENSE_LEASE'
    
    # Insurance
    if 'INSURANCE' in desc_upper or 'JEVCO' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    # Fuel
    if any(x in desc_upper for x in ['FAS GAS', 'CENTEX', 'PETRO', 'SHELL', 'ESSO']):
        return 'EXPENSE_FUEL'
    
    # Point of sale purchases
    if 'POINT OF SALE' in desc_upper or 'POS PURCHASE' in desc_upper:
        if any(x in desc_upper for x in ['SUSHI', 'RESTAURANT', 'FOOD', 'BUFFET', 'DAIRY QUEEN', 'BOSTON PIZZA', 'BISTRO', 'GEORGE\'S PIZZA']):
            return 'EXPENSE_MEALS'
        elif any(x in desc_upper for x in ['604 - LB', 'GAETZ', 'MONEY MART', 'CANADIAN TIRE', 'STAPLES', 'TIME', 'AUTOMOTIVE']):
            return 'EXPENSE_SUPPLIES'
        elif any(x in desc_upper for x in ['SAFEWAY', 'CANADA SAFEWAY']):
            return 'EXPENSE_SUPPLIES'
        elif any(x in desc_upper for x in ['ERLES AUTO', 'MCLEVIN INDUSTRIES']):
            return 'EXPENSE_MAINTENANCE'
        elif any(x in desc_upper for x in ['CITY CENTER VACUUM', 'COMMUNICATIONS GROUP', 'THE RANCH HOUSE']):
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
    if 'CHASE PAYMENTECH' in desc_upper or 'PAYMENTECH CA' in desc_upper:
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
    if 'MCLEVIN INDUSTRIES' in desc_upper:
        return 'McLevin Industries'
    if 'AUTOMOTIVE UNIVERSE' in desc_upper:
        return 'Automotive Universe'
    
    # Insurance
    if 'JEVCO' in desc_upper:
        return 'Jevco Insurance'
    
    # Retail
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
    if 'THE RANCH HOUSE' in desc_upper:
        return 'The Ranch House'
    if 'COMMUNICATIONS GROUP' in desc_upper:
        return 'Communications Group'
    
    # Restaurants
    if 'DAIRY QUEEN' in desc_upper:
        return 'Dairy Queen'
    if 'BOSTON PIZZA' in desc_upper:
        return 'Boston Pizza'
    if 'SUSHI' in desc_upper:
        return 'Sushi Restaurant'
    if 'BISTRO SIBERIA' in desc_upper:
        return 'Bistro Siberia'
    if 'GEORGE\'S PIZZA' in desc_upper or 'GEORGES PIZZA' in desc_upper:
        return 'George\'s Pizza'
    
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

# Transaction data from April 2013 statements
transactions = [
    # Mar 27
    ('2013-03-27', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 655.00),
    ('2013-03-27', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -193.00, None),
    ('2013-03-27', 'SHARED ABM WITHDRAWAL VIA INTERAC', -201.50, None),
    ('2013-03-27', 'CHQ 156 3700138956', -2000.00, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE CANADA SAFEWAY #808 EDMONTON ABCA', -100.01, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE BOSTON PIZZA #159 EDMONTON ABCA', -70.34, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE CITY CENTER VACUUM RED DEER ABCA', -273.00, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE MCLEVIN INDUSTRIES INC RED DEER ABCA', -420.00, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE DAIRY QUEEN #26944 RED DEER ABCA', -84.8, None),
    ('2013-03-27', 'OVERDRAWN HANDLING CHGS', -10.00, None),
    ('2013-03-27', 'INTERAC ABM FEE', -1.50, None),
    ('2013-03-27', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 300.00),
    ('2013-03-27', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1056.25),
    ('2013-03-27', 'POINT OF SALE PURCHASE SUSHI SUSHI INTERAC RED DEER ABCA', -22.05, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -263.24, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE 606 - LD NORTH HILL RED DEER ABCD', -75.45, None),
    ('2013-03-27', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -124.81, None),
    ('2013-03-28', 'SERVICE CHARGE', -119.45, None),
    ('2013-03-28', 'OVERDRAFT INTEREST CHG', -34.81, None),
    ('2013-03-28', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 205.00),
    ('2013-03-28', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 232.50),
    ('2013-03-28', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 175.00),
    ('2013-03-28', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 1754.03),
    ('2013-03-28', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-03-28', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 871.97),
    ('2013-03-28', 'MISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', -796.12, None),
    ('2013-03-28', 'RENT/LEASES A0001<DEFTPYMT> ACE TRUCK RENTALS LTD.', -269.540, None),
    ('2013-03-28', 'AUTO LEASE HEFFNER AUTO FC', -88.987, None),
    ('2013-03-28', 'AUTO LEASE HEFFNER AUTO FC', -471.98, None),
    ('2013-03-28', 'CHQ 158 3700540657', -2200.00, None),
    ('2013-03-28', 'CHQ 157 5000358858', -900.00, None),
    ('2013-03-28', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 800.00),
    ('2013-04-01', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -198.71, None),
    ('2013-04-01', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -56.01, None),
    ('2013-04-01', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -148.95, None),
    ('2013-04-01', 'POINT OF SALE PURCHASE TIME 2 TIME RED DEER ABCA', -119.3, None),
    ('2013-04-01', 'POINT OF SALE PURCHASE STAPLES#285 RED DELR ABCA', -205.65, None),
    ('2013-04-01', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -66.01, None),
    ('2013-04-01', 'DEPOSIT 0873847000019 00001 VISA DEP DR CHASE PAYMENTECH', None, 483.03),
    ('2013-04-01', 'DEPOSIT 0973847000019 00001 MCARD DEP DR CHASE PAYMENTECH', None, 174.52),
    ('2013-04-01', 'OVERDRAWN HANDLING CHGS', -15.00, None),
    ('2013-04-01', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 82.50),
    ('2013-04-01', 'MISC PAYMENT 0873847000019 PAYMENTECH CA VISA DEP DR', -570.16, None),
    ('2013-04-01', 'MISC PAYMENT 0973847000019 PAYMENTECH CA MCARD FEE DR', -141.13, None),
    ('2013-04-01', 'CHQ 159 3700514685', -1817.69, None),
    ('2013-04-01', 'CHQ 160 3700514686', -1000.00, None),
    ('2013-04-02', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 221.38),
    ('2013-04-02', 'OVERDRAWN HANDLING CHGS', -20.00, None),
    ('2013-04-02', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 3859.73),
    ('2013-04-03', 'RETURNED NSF CHEQUE', None, 1817.69),
    ('2013-04-03', 'CHQ 161 3700158599', -564.65, None),
    ('2013-04-03', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 139.68),
    ('2013-04-04', 'OVERDRAWN HANDLING CHGS', -5.00, None),
    ('2013-04-04', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 768.75),
    ('2013-04-04', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-04-05', 'POINT OF SALE PURCHASE MONEY MART #1205 RED DEER ABCA', -500.00, None),
    ('2013-04-05', 'SERVICE CHARGE', -42.50, None),
    ('2013-04-05', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 156.00),
    ('2013-04-05', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 544.50),
    ('2013-04-05', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 300.00),
    ('2013-04-05', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 677.50),
    ('2013-04-05', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 582.50),
    ('2013-04-05', 'SHARED ABM WITHDRAWAL INTERAC', -122.00, None),
    ('2013-04-05', 'ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB', -900.00, None),
    ('2013-04-05', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -100.00, None),
    ('2013-04-05', 'CHQ 162 3900053379', -200.00, None),
    ('2013-04-05', 'CHQ 163 3900053380', -400.00, None),
    ('2013-04-08', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-04-08', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', -71.73, None),
    ('2013-04-08', 'POINT OF SALE PURCHASE CANADIAN TIRE #329 RED DEER ABCA', -520.76, None),
    ('2013-04-08', 'POINT OF SALE PURCHASE CANADIAN TIRE #645 RED DEER ABCA', -64.26, None),
    ('2013-04-08', 'INTERAC ABM FEE', -1.50, None),
    ('2013-04-08', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', None, 1132.50),
    ('2013-04-08', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 82.50),
    ('2013-04-08', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-04-09', 'POINT OF SALE PURCHASE FAS GAS EASTHILL SVC # RED DEER ABCA', -65.01, None),
    ('2013-04-09', 'POINT OF SALE PURCHASE AUTOMOTIVE UNIVERSE RED DEER ABCA', -50.00, None),
    ('2013-04-09', 'POINT OF SALE PURCHASE AUTOMOTIVE UNIVERSE RED DEER ABCA', -136.50, None),
    ('2013-04-09', 'POINT OF SALE PURCHASE GEORGE\'S PIZZA AND STE RED DEER ABCA', -44.98, None),
    ('2013-04-09', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 175.00),
    ('2013-04-09', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 850.00),
    ('2013-04-10', 'CHQ 164 3700546276', -1000.00, None),
    ('2013-04-10', 'POINT OF SALE PURCHASE COMMUNICATIONS GROUP ( RED DEER ABCA', -63.00, None),
    ('2013-04-10', 'POINT OF SALE PURCHASE THE RANCH HOUSE RED DEER ABCA', -39.49, None),
    ('2013-04-10', 'POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA', -1188.45, None),
    ('2013-04-10', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 175.00),
    ('2013-04-10', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 410.00),
    ('2013-04-11', 'DEBIT MEMO GAETZ AND 67TH STREET 51409 002 WD OTHER', -1000.00, None),
    ('2013-04-11', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 874.00),
    ('2013-04-11', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 500.00),
    ('2013-04-12', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', -200.00, None),
    ('2013-04-12', 'CHQ 166 3700095294', -1166.09, None),
    ('2013-04-12', 'CHQ 165 3700143266', -1146.03, None),
    ('2013-04-12', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', -176.92, None),
    ('2013-04-12', 'POINT OF SALE PURCHASE BISTRO SIBERIA RED DEER ABCA', -40.64, None),
    ('2013-04-12', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', -169.00, None),
    ('2013-04-12', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', -110.37, None),
    ('2013-04-12', 'OVERDRAWN HANDLING CHGS', -15.00, None),
    ('2013-04-12', 'DEPOSIT', None, 1870.00),
    ('2013-04-12', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', None, 770.26),
    ('2013-04-15', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', None, 6322.00),
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
    print("Scotia Bank April 2013 Import")
    print("=" * 80)
    print(f"Account: 903990106011")
    print(f"Period: March 27 - April 15, 2013")
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
