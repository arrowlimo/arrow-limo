"""
Import Scotia Bank September-November 2013 transactions from pasted statement data.

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
        match = re.search(r'(?:POS Purchase|POS PURCHASE)\s+(.+?)(?:\s+RED D|\s+EDMON|\s+CALGA|\s+SYLVA|$)', description, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
            # Remove trailing location codes
            vendor = re.sub(r'\s+(RED D|EDMON|CALGA|SYLVA)$', '', vendor, flags=re.IGNORECASE)
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
        if 'EMAIL MONEY' in desc_upper:
            return 'REVENUE_DEPOSIT'
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
    if 'INSURANCE' in desc_upper:
        return 'EXPENSE_INSURANCE'
    
    # Bill payments
    if 'BILL PAYMENT' in desc_upper or 'BR BILL PAYMENT' in desc_upper:
        return 'EXPENSE_BILL_PAYMENT'
    
    # Fuel purchases
    if any(x in desc_upper for x in ['CENTEX', 'PETRO-CANADA', 'SHELL', 'ESSO', 'HUSKY', "RUN'N ON EMPTY", 'FAS GAS', 'SAFEWAY GAS', 'HUGHES PETROLEUM']):
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
    
    # ABM Withdrawals
    if 'ABM WITHDRAWAL' in desc_upper:
        return 'CASH_WITHDRAWAL'
    
    # Deposits
    if 'DEPOSIT' in description and 'MERCHANT' not in desc_upper:
        return 'REVENUE_DEPOSIT'
    
    return 'UNCATEGORIZED'

# Transaction data from pasted statement (Sep-Nov 2013)
TRANSACTIONS = [
    # November 2013
    ('2013-11-29', 'Overdraft Charge', 3.45, 0),
    ('2013-11-29', 'Service Charge', 112.50, 0),
    ('2013-11-29', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-11-29', 'Cheque 271', 646.96, 0),
    ('2013-11-29', 'Cheque 272', 3805.23, 0),
    ('2013-11-29', 'Cheque 265', 2004.21, 0),
    ('2013-11-29', 'POS Purchase PETRO-CANADA RED D', 68.03, 0),
    ('2013-11-29', 'Rent/Lease HEFFNER AUTO FC', 1775.25, 0),
    ('2013-11-28', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 156.53),
    ('2013-11-28', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 394.56),
    ('2013-11-28', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 0.51),
    ('2013-11-27', 'Rent/Lease HEFFNER AUTO FC', 914.88, 0),
    ('2013-11-27', 'Rent/Lease HEFFNER AUTO FC', 237.52, 0),
    ('2013-11-27', 'Rent/Lease HEFFNER AUTO FC', 1925.50, 0),
    ('2013-11-27', 'Rent/Lease HEFFNER AUTO FC', 2550.25, 0),
    ('2013-11-27', 'Bill Payment PC-CAPITAL ONE MASTERCARD 80135883', 500.00, 0),
    ('2013-11-27', 'Bill Payment PC-TELUS MOBILITY/MOBILITE 80135882', 231.34, 0),
    ('2013-11-27', 'POS Purchase CHOICE AUTO ELECTRIC REPARED D', 562.57, 0),
    ('2013-11-27', 'ABM Withdrawal', 300.00, 0),
    ('2013-11-27', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 920.01),
    ('2013-11-27', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 205.00),
    ('2013-11-26', 'Bill Payment PC-TELUS COMMUNICATIONS 78470854', 556.68, 0),
    ('2013-11-26', 'Bill Payment PC-TELUS COMMUNICATIONS 78470853', 6097.05, 0),
    ('2013-11-26', 'POS Purchase CASH STORE 771 RED DEE RED D', 701.41, 0),
    ('2013-11-26', 'POS Purchase SHELL FLYING J #79600 RED D', 363.75, 0),
    ('2013-11-26', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 156.00, 0),
    ('2013-11-26', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 61.00, 0),
    ('2013-11-26', 'Miscellaneous Payment AMEX BANK OF CANADA', 600.00, 0),
    ('2013-11-26', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1126.24),
    ('2013-11-26', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 948.50),
    ('2013-11-25', 'POS Purchase CENTEX DEERPARK(C-STOR RED D', 54.50, 0),
    ('2013-11-25', 'Miscellaneous Payment AMEX BANK OF CANADA', 211.52, 0),
    ('2013-11-25', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 411.51),
    ('2013-11-25', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 221.36),
    ('2013-11-25', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 4145.64),
    ('2013-11-22', 'POS Purchase SUMMIT ESSO RED D', 72.00, 0),
    ('2013-11-22', 'Cheque 267', 325.62, 0),
    ('2013-11-22', 'POS Purchase 604 - LB 67TH ST. RED D', 1919.66, 0),
    ('2013-11-22', 'POS Purchase WAL-MART #1007 KITCH', 150.01, 0),
    ('2013-11-22', 'ABM Withdrawal', 37.62, 0),
    ('2013-11-22', 'Miscellaneous Payment AMEX BANK OF CANADA', 700.00, 0),
    ('2013-11-22', 'Miscellaneous Payment AMEX BANK OF CANADA', 372.37, 0),
    ('2013-11-22', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 620.23),
    ('2013-11-22', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 953.80),
    ('2013-11-22', 'Credit Memo PC-EMAIL MONEY TRF', 0, 1020.12),
    ('2013-11-21', 'POS Purchase 604 - LB 67TH ST. RED D', 299.13, 0),
    ('2013-11-21', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 750.62),
    ('2013-11-20', 'Overdrawn Handling Chg.', 5.00, 0),
    ('2013-11-20', 'Insurance EQUITY PREMIUM FINANCE INC.', 1157.94, 0),
    ('2013-11-20', 'POS Purchase STAPLES#285 RED D', 82.03, 0),
    ('2013-11-20', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 178.82),
    ('2013-11-20', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 175.51),
    ('2013-11-20', 'Deposit', 0, 650.00),
    ('2013-11-19', 'Cheque 269', 1706.25, 0),
    ('2013-11-19', 'Cheque 270', 451.77, 0),
    ('2013-11-19', 'Cheque 264', 1028.61, 0),
    ('2013-11-19', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 99.23),
    ('2013-11-18', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 267.50),
    ('2013-11-18', 'Service Charge', 85.00, 0),
    ('2013-11-18', 'Miscellaneous Payment AMEX BANK OF CANADA', 930.13, 0),
    ('2013-11-18', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 124.03),
    ('2013-11-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 75.00),
    ('2013-11-18', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 486.50),
    ('2013-11-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 752.01),
    ('2013-11-18', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 482.34),
    ('2013-11-15', 'Service Charge', 42.50, 0),
    ('2013-11-15', 'Returned Cheque - NSF', 2525.25, 0),
    ('2013-11-15', 'Returned Cheque - NSF', 1900.50, 0),
    ('2013-11-15', 'Returned Cheque - NSF', 889.88, 0),
    ('2013-11-15', 'Miscellaneous Payment PAYMENTECH CA VISA DEP DR', 1027.16, 0),
    ('2013-11-15', 'Rent/Lease HEFFNER AUTO FC', 889.88, 0),
    ('2013-11-15', 'Rent/Lease HEFFNER AUTO FC', 1900.50, 0),
    ('2013-11-15', 'Rent/Lease HEFFNER AUTO FC', 738.41, 0),
    ('2013-11-15', 'Rent/Lease HEFFNER AUTO FC', 2525.25, 0),
    ('2013-11-15', 'Debit Memo OTHER', 0, 750.00),
    ('2013-11-15', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 64.01, 0),
    ('2013-11-15', 'POS Purchase 604 - LB 67TH ST. RED D', 378.50, 0),
    ('2013-11-15', 'POS Purchase MONGOLIE GRILL-RED DEE RED D', 74.58, 0),
    ('2013-11-15', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 425.00),
    ('2013-11-15', 'Deposit', 0, 2650.75),
    ('2013-11-14', 'Debit Memo OTHER', 0, 1600.00),
    ('2013-11-14', 'POS Purchase SUMMIT ESSO RED D', 83.01, 0),
    ('2013-11-14', 'Deposit', 0, 410.00),
    ('2013-11-13', 'Credit Memo PC-EMAIL MONEY TRF', 0, 500.00),
    ('2013-11-13', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 106.13),
    ('2013-11-13', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 150.00),
    ('2013-11-12', 'Service Charge', 42.50, 0),
    ('2013-11-12', 'Returned Cheque - NSF 263', 2393.40, 0),
    ('2013-11-12', 'Cheque 263', 2393.40, 0),
    ('2013-11-12', 'Cheque 259', 244.55, 0),
    ('2013-11-12', 'Bill Payment PC-TELUS COMMUNICATIONS 47838739', 1767.13, 0),
    ('2013-11-12', 'POS Purchase 604 - LB 67TH ST. RED D', 118.04, 0),
    ('2013-11-12', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 125.67, 0),
    ('2013-11-12', 'POS Purchase TOMMY GUN\'S ORIGINAL B RED D', 39.40, 0),
    ('2013-11-12', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 630.00),
    ('2013-11-12', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1436.56),
    ('2013-11-12', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 941.62),
    ('2013-11-08', 'Overdrawn Handling Chg.', 5.00, 0),
    ('2013-11-08', 'Insurance Cooperators CSI', 128.33, 0),
    ('2013-11-08', 'Service Charge', 42.50, 0),
    ('2013-11-08', 'Service Charge', 1.50, 0),
    ('2013-11-08', 'POS Purchase CENTEX DEERPARK(C-STOR RED D', 44.00, 0),
    ('2013-11-08', 'ABM Withdrawal', 201.85, 0),
    ('2013-11-08', 'Miscellaneous Payment AMEX BANK OF CANADA', 192.87, 0),
    ('2013-11-08', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 136.00),
    ('2013-11-07', 'Returned Cheque - NSF 260', 1683.63, 0),
    ('2013-11-07', 'Cheque 260', 1683.63, 0),
    ('2013-11-07', 'Cheque 262', 899.55, 0),
    ('2013-11-07', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 127.83, 0),
    ('2013-11-07', 'POS Purchase SYLVAN ELECTRONIC SERV REDE', 50.00, 0),
    ('2013-11-06', 'Cheque 261', 531.62, 0),
    ('2013-11-06', 'POS Purchase SOUTHVIEW ESSO 8800913 CALGA', 57.00, 0),
    ('2013-11-06', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 636.76),
    ('2013-11-06', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 826.88),
    ('2013-11-05', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 75.00),
    ('2013-11-04', 'Service Charge', 42.50, 0),
    ('2013-11-04', 'Returned Cheque - NSF', 1035.53, 0),
    ('2013-11-04', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 181.53),
    ('2013-11-04', 'Miscellaneous Payment PAYMENTECH CA MCARD FEE DR', 261.79, 0),
    ('2013-11-04', 'Miscellaneous Payment PAYMENTECH CA VISA FEE DR', 1035.53, 0),
    ('2013-11-04', 'Merchant Deposit Debit 566756800000 00001 DEBITCD F', 0.25, 0),
    ('2013-11-04', 'POS Purchase 604 - LB 67TH ST. RED D', 72.00, 0),
    ('2013-11-04', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 356.72),
    ('2013-11-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 140.00),
    ('2013-11-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 184.53),
    ('2013-11-01', 'Overdrawn Handling Chg.', 5.00, 0),
    ('2013-11-01', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 202.63),
    ('2013-11-01', 'Cheque 252', 1109.26, 0),
    ('2013-11-01', 'Rent/Lease HEFFNER AUTO FC', 889.87, 0),
    ('2013-11-01', 'Rent/Lease ACE TRUCK RENTALS LTD.', 2695.40, 0),
    ('2013-11-01', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 68.00, 0),
    
    # October 2013
    ('2013-10-31', 'Overdraft Charge', 11.97, 0),
    ('2013-10-31', 'Service Charge', 112.50, 0),
    ('2013-10-31', 'POS Purchase SHOPPERS DRUG MART #24 RED D', 216.81, 0),
    ('2013-10-31', 'Cheque 257', 1200.00, 0),
    ('2013-10-31', 'Cheque 258', 300.00, 0),
    ('2013-10-31', 'Cheque 255', 857.50, 0),
    ('2013-10-31', 'Bill Payment PC-CAPITAL ONE MASTERCARD 21107493', 500.00, 0),
    ('2013-10-31', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 3401.25),
    ('2013-10-31', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 968.35),
    ('2013-10-30', 'POS Purchase CARRIAGE AUTO UPHOLSTE RED D', 189.00, 0),
    ('2013-10-30', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 631.63),
    ('2013-10-29', 'Bill Payment PC-WORKERS COMP BOARD ALBERTA 14518155', 780.00, 0),
    ('2013-10-29', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1075.00),
    ('2013-10-29', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 425.00),
    ('2013-10-28', 'Cheque 256', 1000.00, 0),
    ('2013-10-28', 'Cheque 254', 2876.37, 0),
    ('2013-10-28', 'Merchant Deposit Debit 566756800000 00001 VISA', 0.97, 0),
    ('2013-10-28', 'POS Purchase WAL MART #1007 KITCH', 146.09, 0),
    ('2013-10-28', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 160.00, 0),
    ('2013-10-28', 'POS Purchase 606 - LD NORTH HILL RED D', 51.05, 0),
    ('2013-10-28', 'Miscellaneous Payment AMEX BANK OF CANADA', 223.43, 0),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 475.62),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 264.50),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 2181.16),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 478.54),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 655.96),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 489.50),
    ('2013-10-28', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 389.25),
    ('2013-10-28', 'Deposit', 0, 350.00),
    ('2013-10-25', 'Cheque 248', 2287.26, 0),
    ('2013-10-25', 'Rent/Lease HEFFNER AUTO FC', 914.88, 0),
    ('2013-10-25', 'Rent/Lease HEFFNER AUTO FC', 1925.50, 0),
    ('2013-10-25', 'POS Purchase CHOICE AUTO ELECTRIC REPARED D', 958.90, 0),
    ('2013-10-25', 'POS Purchase WAL-MART #3075 RED D', 158.18, 0),
    ('2013-10-25', 'POS Purchase PRINCESS AUTO RED D', 236.61, 0),
    ('2013-10-25', 'POS Purchase TIM HORTONS #2705# QTH RED D', 9.24, 0),
    ('2013-10-25', 'Miscellaneous Payment AMEX BANK OF CANADA', 223.43, 0),
    ('2013-10-25', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 2327.52),
    ('2013-10-24', 'POS Purchase CANADIAN TIRE #645 RED D', 1582.15, 0),
    ('2013-10-24', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 750.00),
    ('2013-10-24', 'Deposit', 0, 2379.00),
    ('2013-10-23', 'Cheque 253', 1000.00, 0),
    ('2013-10-23', 'Bill Payment PC-ROGERS WIRELESS SERVICES 99897050', 1000.00, 0),
    ('2013-10-23', 'Merchant Deposit Debit 566756800000 00001 MCARD', 500.00, 0),
    ('2013-10-23', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 49.00, 0),
    ('2013-10-23', 'POS Purchase PRAIRIE OFFICE PLUS RED D', 50.75, 0),
    ('2013-10-23', 'POS Purchase MONGOLIE GRILL-RED DEE RED D', 81.51, 0),
    ('2013-10-23', 'POS Purchase STAPLES#285 RED D', 478.04, 0),
    ('2013-10-23', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 2730.81),
    ('2013-10-22', 'POS Purchase 604 - LB 67TH ST. RED D', 210.46, 0),
    ('2013-10-21', 'Insurance EQUITY PREMIUM FINANCE INC.', 1157.94, 0),
    ('2013-10-21', 'POS Purchase RED DEER CO-OP LTD QPE RED D', 30.00, 0),
    ('2013-10-21', 'POS Purchase KINSMEN CLUB OF RED DE RED D', 510.00, 0),
    ('2013-10-21', 'POS Purchase WAL-MART #3194 RED D', 100.44, 0),
    ('2013-10-21', 'Miscellaneous Payment AMEX BANK OF CANADA', 248.39, 0),
    ('2013-10-21', 'Miscellaneous Payment AMEX BANK OF CANADA', 168.87, 0),
    ('2013-10-21', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1171.52),
    ('2013-10-21', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1583.86),
    ('2013-10-21', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 1203.28),
    ('2013-10-21', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 507.95),
    ('2013-10-21', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 150.00),
    ('2013-10-18', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 144.97, 0),
    ('2013-10-18', 'POS Purchase 606 -LD NORTH HILL RED D', 58.79, 0),
    ('2013-10-18', 'POS Purchase 604 -LB 67TH ST. RED D', 471.70, 0),
    ('2013-10-18', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 878.25),
    ('2013-10-17', 'POS Purchase 604 -LB 67TH ST. RED D', 28.45, 0),
    ('2013-10-17', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 175.00),
    ('2013-10-17', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 3436.20),
    ('2013-10-17', 'Credit Memo OTHER', 0, 889.88),
    ('2013-10-17', 'Credit Memo OTHER', 0, 1900.50),
    ('2013-10-17', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 238.39),
    ('2013-10-11', 'Debit Memo OTHER', 100.00, 0),
    ('2013-10-11', 'POS Purchase PART SOURCE #791 RED D', 36.09, 0),
    ('2013-10-11', 'Deposit', 0, 205.00),
    ('2013-10-10', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 125.58, 0),
    ('2013-10-10', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1389.88),
    ('2013-10-10', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 175.00),
    ('2013-10-09', 'Bill Payment PC-TELUS COMMUNICATIONS 71785772', 1691.30, 0),
    ('2013-10-09', 'POS Purchase WAL-MART #3194 RED D', 120.50, 0),
    ('2013-10-09', 'POS Purchase CANADIAN TIRE #645 RED D', 157.49, 0),
    ('2013-10-09', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 45.94, 0),
    ('2013-10-09', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 655.19),
    ('2013-10-08', 'Cheque 247', 2280.60, 0),
    ('2013-10-08', 'Insurance Cooperators CSI', 128.33, 0),
    ('2013-10-07', 'Cheque 250', 349.01, 0),
    ('2013-10-07', 'Cheque 246', 232.90, 0),
    ('2013-10-07', 'Cheque 245', 1575.00, 0),
    ('2013-10-07', 'Service Charge', 1.00, 0),
    ('2013-10-07', 'Debit Memo PC-EMAIL MONEY TRF', 2200.00, 0),
    ('2013-10-07', 'POS Purchase 604 - LB 67TH ST. RED D', 36.52, 0),
    ('2013-10-07', 'POS Purchase PHIL\'S RESTAURANTS RED RED D', 57.79, 0),
    ('2013-10-07', 'POS Purchase FAS GAS LAKEVIEW SVC# SYLVA', 15.40, 0),
    ('2013-10-07', 'POS Purchase 604 - LB 67TH ST. RED D', 105.45, 0),
    ('2013-10-07', 'POS Purchase 604 - LB 67TH ST. RED D', 349.17, 0),
    ('2013-10-07', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 82.69),
    ('2013-10-07', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 2319.60),
    ('2013-10-07', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 1281.31),
    ('2013-10-07', 'Merchant Deposit Credit 566756800000 00001 DEBITCD D', 0, 440.82),
    ('2013-10-07', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 2994.05),
    ('2013-10-04', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 88.02, 0),
    ('2013-10-04', 'POS Purchase RED DEER REGISTRIES RED D', 591.00, 0),
    ('2013-10-04', 'ABM Withdrawal', 500.00, 0),
    ('2013-10-04', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 500.00),
    ('2013-10-04', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 205.00),
    ('2013-10-04', 'Credit Memo OTHER', 0, 2695.40),
    ('2013-10-03', 'Debit Memo OTHER', 100.00, 0),
    ('2013-10-03', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 74.00, 0),
    ('2013-10-03', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 2912.75),
    ('2013-10-03', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 541.12),
    ('2013-10-03', 'Deposit', 0, 350.00),
    ('2013-10-02', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-10-02', 'Miscellaneous Payment PAYMENTECH CA MCARD FEE DR', 130.80, 0),
    ('2013-10-02', 'Miscellaneous Payment PAYMENTECH CA VISA DEP DR', 709.74, 0),
    ('2013-10-02', 'Merchant Deposit Credit 566756800000 00001 VISA', 0, 995.31),
    ('2013-10-02', 'Merchant Deposit Credit 566756800000 00001 MCARD', 0, 572.50),
    ('2013-10-01', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-10-01', 'Rent/Lease HEFFNER AUTO FC', 889.87, 0),
    ('2013-10-01', 'Rent/Lease ACE TRUCK RENTALS LTD.', 2695.40, 0),
    
    # September 2013
    ('2013-09-30', 'Overdraft Charge', 10.30, 0),
    ('2013-09-30', 'Service Charge', 112.50, 0),
    ('2013-09-30', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-09-30', 'Cheque 244', 248.42, 0),
    ('2013-09-30', 'ABM Withdrawal', 400.00, 0),
    ('2013-09-30', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 175.00),
    ('2013-09-30', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 582.74),
    ('2013-09-27', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-09-27', 'POS Purchase GEORGE\'S PIZZA AND STE RED D', 45.36, 0),
    ('2013-09-27', 'Cheque 243', 1050.00, 0),
    ('2013-09-27', 'Cheque 239', 200.00, 0),
    ('2013-09-27', 'POS Purchase 604 - LB 67TH ST. RED D', 148.54, 0),
    ('2013-09-27', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 662.38),
    ('2013-09-26', 'POS Purchase TOAD N TURTLE PUBHOUSE RED D', 41.63, 0),
    ('2013-09-26', 'POS Purchase UPTOWN LIQUOR STORE RED D', 43.05, 0),
    ('2013-09-26', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 124.04),
    ('2013-09-26', 'Cheque 240', 2139.20, 0),
    ('2013-09-26', 'Cheque 241', 75.00, 0),
    ('2013-09-26', 'Cheque 242', 2000.00, 0),
    ('2013-09-26', 'ABM Withdrawal', 400.00, 0),
    ('2013-09-26', 'Merchant Deposit Debit 087384700019 00001 VISA', 205.00, 0),
    ('2013-09-26', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 201.02, 0),
    ('2013-09-26', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 225.01, 0),
    ('2013-09-26', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 88.00, 0),
    ('2013-09-26', 'Deposit', 0, 1512.00),
    ('2013-09-25', 'POS Purchase BUCK OR TWO #235 RED D', 75.60, 0),
    ('2013-09-25', 'POS Purchase ERLES AUTO REPAIR RED D', 105.00, 0),
    ('2013-09-25', 'Miscellaneous Payment AMEX BANK OF CANADA', 522.43, 0),
    ('2013-09-25', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 3407.70),
    ('2013-09-25', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 945.00),
    ('2013-09-25', 'Deposit', 0, 1634.62),
    ('2013-09-24', 'Overdrawn Handling Chg.', 15.00, 0),
    ('2013-09-24', 'POS Purchase HUSKY COLISEUM #5070 EDMON', 50.00, 0),
    ('2013-09-24', 'POS Purchase O2\'S TAP HOUSE & GRILL EDMON', 37.73, 0),
    ('2013-09-24', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 206.75),
    ('2013-09-24', 'Insurance IFS PREMIUM FIN', 2311.74, 0),
    ('2013-09-24', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 237.00, 0),
    ('2013-09-24', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 82.69),
    ('2013-09-23', 'Rent/Lease HEFFNER AUTO FC', 127.94, 0),
    ('2013-09-23', 'Rent/Lease HEFFNER AUTO FC', 1900.50, 0),
    ('2013-09-23', 'Rent/Lease HEFFNER AUTO FC', 2525.25, 0),
    ('2013-09-23', 'Miscellaneous Payment AMEX BANK OF CANADA', 656.20, 0),
    ('2013-09-23', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 1683.91),
    ('2013-09-23', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 769.24),
    ('2013-09-23', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 250.00),
    ('2013-09-23', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 1083.67),
    ('2013-09-23', 'Deposit', 0, 577.50),
    ('2013-09-20', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-09-20', 'POS Purchase GEORGE\'S PIZZA AND STE RED D', 30.90, 0),
    ('2013-09-20', 'Insurance EQUITY PREMIUM FINANCE INC.', 1157.94, 0),
    ('2013-09-20', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 226.25, 0),
    ('2013-09-20', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 166.01, 0),
    ('2013-09-20', 'POS Purchase CHOICE AUTO ELECTRIC REPARED D', 376.53, 0),
    ('2013-09-20', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 105.01, 0),
    ('2013-09-20', 'ABM Withdrawal', 500.00, 0),
    ('2013-09-20', 'ABM Withdrawal', 1000.00, 0),
    ('2013-09-20', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 2987.91),
    ('2013-09-19', 'POS Purchase A&W #1540 EDMON', 9.71, 0),
    ('2013-09-19', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 44.10),
    ('2013-09-19', 'POS Purchase RUN\'N ON EMPTY 50AVQPE RED D', 51.43, 0),
    ('2013-09-19', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 380.00),
    ('2013-09-18', 'Credit Memo OTHER', 0, 2525.25),
    ('2013-09-18', 'Credit Memo OTHER', 0, 1900.50),
    ('2013-09-18', 'Credit Memo OTHER', 0, 127.94),
    ('2013-09-17', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 118.12),
    ('2013-09-16', 'Overdrawn Handling Chg.', 25.00, 0),
    ('2013-09-16', 'Rent/Lease HEFFNER AUTO FC', 127.94, 0),
    ('2013-09-16', 'Rent/Lease HEFFNER AUTO FC', 889.88, 0),
    ('2013-09-16', 'Rent/Lease HEFFNER AUTO FC', 1900.50, 0),
    ('2013-09-16', 'Rent/Lease HEFFNER AUTO FC', 1475.25, 0),
    ('2013-09-16', 'Rent/Lease HEFFNER AUTO FC', 2525.25, 0),
    ('2013-09-16', 'Bill Payment BR BILL PAYMENT', 3841.73, 0),
    ('2013-09-16', 'Bill Payment PC-CAPITAL ONE MASTERCARD 20919126', 75.00, 0),
    ('2013-09-16', 'Bill Payment PC-CAPITAL ONE MASTERCARD 20910678', 500.00, 0),
    ('2013-09-16', 'POS Purchase SAFEWAY GAS BAR #0808 EDMON', 60.00, 0),
    ('2013-09-16', 'POS Purchase 604 - LB 67TH ST. RED D', 475.48, 0),
    ('2013-09-16', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 165.38),
    ('2013-09-16', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 250.00),
    ('2013-09-16', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 2807.31),
    ('2013-09-16', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 332.81),
    ('2013-09-16', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 771.18),
    ('2013-09-16', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 1000.00),
    ('2013-09-16', 'Deposit', 0, 1768.94),
    ('2013-09-13', 'Cheque 238', 163.90, 0),
    ('2013-09-13', 'Bill Payment PC-TELUS COMMUNICATIONS 15694784', 3319.08, 0),
    ('2013-09-13', 'POS Purchase HUGHES PETROLEUM LTD EDMON', 39.32, 0),
    ('2013-09-13', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 205.00),
    ('2013-09-13', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 248.07),
    ('2013-09-12', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 315.00),
    ('2013-09-12', 'Cheque 189', 500.00, 0),
    ('2013-09-12', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1796.15),
    ('2013-09-12', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 232.87),
    ('2013-09-12', 'Deposit', 0, 2138.86),
    ('2013-09-11', 'Overdrawn Handling Chg.', 5.00, 0),
    ('2013-09-11', 'Cheque 232', 782.99, 0),
    ('2013-09-11', 'Cheque 237', 1800.84, 0),
    ('2013-09-11', 'Cheque 236', 2915.80, 0),
    ('2013-09-11', 'POS Purchase ERLES AUTO REPAIR RED D', 110.78, 0),
    ('2013-09-11', 'POS Purchase WINDSHIELD SURGEONS RED D', 215.25, 0),
    ('2013-09-11', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 565.00),
    ('2013-09-11', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 215.00),
    ('2013-09-11', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 200.00),
    ('2013-09-10', 'POS Purchase ERLES AUTO REPAIR RED D', 111.83, 0),
    ('2013-09-10', 'POS Purchase ERLES AUTO REPAIR RED D', 219.84, 0),
    ('2013-09-10', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1561.00),
    ('2013-09-10', 'Deposit', 0, 1223.71),
    ('2013-09-10', 'Credit Memo OTHER', 0, 5.00),
    ('2013-09-09', 'Cheque 230', 1400.61, 0),
    ('2013-09-09', 'Cheque 234', 381.30, 0),
    ('2013-09-09', 'Cheque 235', 1210.76, 0),
    ('2013-09-09', 'Insurance Cooperators CSI', 123.79, 0),
    ('2013-09-09', 'Miscellaneous Payment AMEX BANK OF CANADA', 144.75, 0),
    ('2013-09-09', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 470.18),
    ('2013-09-09', 'Merchant Deposit Credit 087384700019 00001 DEBITCD D', 0, 234.99),
    ('2013-09-09', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 502.59),
    ('2013-09-09', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 951.25),
    ('2013-09-09', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 128.71),
    ('2013-09-09', 'Deposit', 0, 2193.69),
    ('2013-09-06', 'Service Charge', 42.50, 0),
    ('2013-09-06', 'Returned Cheque - NSF 227', 1570.00, 0),
    ('2013-09-06', 'Cheque 231', 432.53, 0),
    ('2013-09-06', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 325.00),
    ('2013-09-06', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 177.53),
    ('2013-09-05', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 82.69),
    ('2013-09-04', 'Overdrawn Handling Chg.', 10.00, 0),
    ('2013-09-04', 'Cheque 227', 1570.00, 0),
    ('2013-09-04', 'Cheque 229', 2000.00, 0),
    ('2013-09-04', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 2571.70),
    ('2013-09-03', 'Overdrawn Handling Chg.', 5.00, 0),
    ('2013-09-03', 'Cheque 228', 1575.00, 0),
    ('2013-09-03', 'Rent/Lease HEFFNER AUTO FC', 471.98, 0),
    ('2013-09-03', 'Rent/Lease HEFFNER AUTO FC', 889.87, 0),
    ('2013-09-03', 'Rent/Lease ACE TRUCK RENTALS LTD.', 2695.40, 0),
    ('2013-09-03', 'Merchant Deposit Debit 087384700019 00001 VISA', 585.89, 0),
    ('2013-09-03', 'Merchant Deposit Debit 097384700019 00001 MCARD', 227.21, 0),
    ('2013-09-03', 'POS Purchase TIM HORTONS #0107# QTH RED D', 1.00, 0),
    ('2013-09-03', 'ABM Withdrawal', 640.00, 0),
    ('2013-09-03', 'Miscellaneous Payment AMEX BANK OF CANADA', 1015.78, 0),
    ('2013-09-03', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 205.00),
    ('2013-09-03', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 124.03),
    ('2013-09-03', 'Merchant Deposit Credit 087384700019 00001 VISA', 0, 1551.94),
    ('2013-09-03', 'Merchant Deposit Credit 097384700019 00001 MCARD', 0, 165.00),
    ('2013-09-03', 'Deposit', 0, 1343.63),
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia Sep-Nov 2013 transactions')
    parser.add_argument('--write', action='store_true', help='Actually write to database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check for existing transactions to prevent duplicates
    cur.execute("""
        SELECT source_hash FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2013-09-01'
        AND transaction_date <= '2013-11-30'
    """)
    existing_hashes = {row[0] for row in cur.fetchall() if row[0]}
    
    print(f"Found {len(existing_hashes)} existing transactions in database for Sep-Nov 2013")
    
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
                'STATEMENT_PASTE_SEP_NOV_2013',
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
