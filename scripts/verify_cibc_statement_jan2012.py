#!/usr/bin/env python3
"""
Verify CIBC Account Statement - January 2012
Account: 74-61615, Branch: 00339
Statement Period: Jan 1 - Jan 31, 2012
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from datetime import date

def get_db_connection():
    """Standard ALMS database connection."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

# Extracted transactions from CIBC statement (Jan 2012)
STATEMENT_TRANSACTIONS = [
    # Page 1
    {'date': '2012-01-01', 'description': 'Balance forward', 'withdrawals': None, 'deposits': None, 'balance': 7177.34},
    {'date': '2012-01-01', 'description': 'PURCHASE00001188103', 'withdrawals': 63.50, 'deposits': None, 'balance': 7113.84},
    {'date': '2012-01-01', 'description': 'CENTEX PETROLEU', 'withdrawals': 4.80, 'deposits': None, 'balance': 7109.04},
    {'date': '2012-01-01', 'description': 'MR SUBS INC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-01', 'description': 'PURCHASE00001147103', 'withdrawals': 37.18, 'deposits': None, 'balance': 7071.86},
    {'date': '2012-01-01', 'description': 'REAL CDN WHOLE', 'withdrawals': 114.00, 'deposits': None, 'balance': 6957.86},
    {'date': '2012-01-01', 'description': 'RUNNTON EMPTY', 'withdrawals': 500.00, 'deposits': None, 'balance': 6457.86},
    {'date': '2012-01-01', 'description': 'ABM WITHDRAWAL 2OKQ', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-01', 'description': 'ABM FEE-7601 2', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-01', 'description': 'DEPOSIT', 'withdrawals': None, 'deposits': 756.26, 'balance': 7214.14},
    {'date': '2012-01-02', 'description': 'WITHDRAWAL', 'withdrawals': 140.00, 'deposits': None, 'balance': 7074.14},
    {'date': '2012-01-02', 'description': 'TRANSFER', 'withdrawals': 2200.00, 'deposits': None, 'balance': 4874.14},
    {'date': '2012-01-02', 'description': 'TRANSFER FEE 28049', 'withdrawals': 78.70, 'deposits': None, 'balance': 4795.44},
    {'date': '2012-01-02', 'description': 'BED BATH & BEYO', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 2
    {'date': '2012-01-03', 'description': 'PURCHASE00001190078', 'withdrawals': 93.82, 'deposits': None, 'balance': 4701.62},
    {'date': '2012-01-03', 'description': 'CENTEX PETROLEU', 'withdrawals': 15.45, 'deposits': None, 'balance': 4686.17},
    {'date': '2012-01-03', 'description': 'PURCHASE00001200097', 'withdrawals': 29.00, 'deposits': None, 'balance': 4657.17},
    {'date': '2012-01-03', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-03', 'description': 'E-TRANSFER9000001371711', 'withdrawals': None, 'deposits': 570.56, 'balance': 4686.61},  # Handwritten: "Intact"
    {'date': '2012-01-03', 'description': 'E-TRANSFER RECLAIM000001445880', 'withdrawals': None, 'deposits': 570.56, 'balance': 4657.17},  # Handwritten: "in Intact"
    {'date': '2012-01-03', 'description': 'E-TRANSFER9000001519438', 'withdrawals': 570.56, 'deposits': None, 'balance': 4086.61},
    {'date': '2012-01-03', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 528.00, 'balance': 4614.61},
    {'date': '2012-01-03', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': 715.00, 'balance': 5329.61},
    {'date': '2012-01-03', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 304.50, 'balance': 5634.11},
    {'date': '2012-01-03', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 482.50, 'balance': 6116.61},
    {'date': '2012-01-03', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': 699.62, 'balance': 6816.23},
    {'date': '2012-01-03', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 2275.26, 'balance': 9091.49},
    {'date': '2012-01-03', 'description': 'DEPOSIT', 'withdrawals': None, 'deposits': 2275.26, 'balance': 9091.49},
    {'date': '2012-01-03', 'description': 'PURCHASE00001142034', 'withdrawals': 308.70, 'deposits': None, 'balance': 8782.79},
    {'date': '2012-01-03', 'description': 'GIBLEE AUTO REPA', 'withdrawals': 2197.71, 'deposits': None, 'balance': 6585.08},
    {'date': '2012-01-03', 'description': 'MERCH464617775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-03', 'description': 'GBL MERCH FEES', 'withdrawals': 500.00, 'deposits': None, 'balance': 7085.08},
    {'date': '2012-01-03', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 435.00, 'balance': 7520.08},
    {'date': '2012-01-03', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': 1840.00, 'balance': 9360.08},
    
    # Page 3
    {'date': '2012-01-04', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 673.74, 'balance': 10033.82},
    {'date': '2012-01-04', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': 2375.75, 'balance': 12409.57},
    {'date': '2012-01-04', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 2142.50, 'balance': 14552.07},
    {'date': '2012-01-04', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 370.00, 'balance': 14922.07},
    {'date': '2012-01-04', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': 1233.37, 'balance': 16155.44},
    {'date': '2012-01-04', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 250.00, 'balance': 16405.44},
    {'date': '2012-01-04', 'description': 'REV-INSURANCE#14A003', 'withdrawals': 553.89, 'deposits': None, 'balance': 15851.55},
    {'date': '2012-01-04', 'description': 'EPLES AUTO REPA', 'withdrawals': 48.00, 'deposits': None, 'balance': 15803.55},
    {'date': '2012-01-04', 'description': 'PURCHASE00001175046', 'withdrawals': 225.01, 'deposits': None, 'balance': 15578.54},
    {'date': '2012-01-04', 'description': 'CENTEX PETROLEU', 'withdrawals': 3005.46, 'deposits': None, 'balance': 12573.08},
    {'date': '2012-01-05', 'description': 'CHEQUE 170803 207', 'withdrawals': 1771.12, 'deposits': None, 'balance': 10801.96},
    {'date': '2012-01-05', 'description': 'CHEQUE 170804 203', 'withdrawals': 256.14, 'deposits': None, 'balance': 11060.10},
    {'date': '2012-01-05', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': 608.99, 'balance': 11670.09},
    {'date': '2012-01-05', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 173.25, 'balance': 11843.34},
    {'date': '2012-01-05', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 500.00, 'balance': 12343.34},
    {'date': '2012-01-05', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-05', 'description': 'PURCHASE00001367184', 'withdrawals': 87.04, 'deposits': None, 'balance': 12256.30},
    {'date': '2012-01-05', 'description': 'WAL-MART #3275', 'withdrawals': 1620.24, 'deposits': None, 'balance': 10436.06},
    {'date': '2012-01-06', 'description': 'CHEQUE 171492$ 204', 'withdrawals': 351.89, 'deposits': None, 'balance': 10787.95},
    {'date': '2012-01-06', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 4
    {'date': '2012-01-06', 'description': 'CREDIT MEMO 4017775 MC', 'withdrawals': None, 'deposits': 205.00, 'balance': 10992.95},
    {'date': '2012-01-06', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-06', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 900.00, 'balance': 11892.95},
    {'date': '2012-01-06', 'description': 'WITHDRAWAL', 'withdrawals': 1000.00, 'deposits': None, 'balance': 10892.95},
    {'date': '2012-01-06', 'description': 'PURCHASE00001198045', 'withdrawals': 66.49, 'deposits': None, 'balance': 10826.46},
    {'date': '2012-01-06', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-06', 'description': 'PURCHASE00001188046', 'withdrawals': 71.20, 'deposits': None, 'balance': 10755.26},
    {'date': '2012-01-06', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-06', 'description': 'PURCHASE00001047053', 'withdrawals': 55.36, 'deposits': None, 'balance': 10699.90},
    {'date': '2012-01-06', 'description': 'GREGG DIST BED', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-06', 'description': 'PURCHASE00001148524', 'withdrawals': 905.08, 'deposits': None, 'balance': 9794.82},
    {'date': '2012-01-06', 'description': 'EBLES AUTO REPA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'GIBLEE AUTO REPA', 'withdrawals': 2525.25, 'deposits': None, 'balance': 7269.57},
    {'date': '2012-01-09', 'description': 'Dec11 PMT', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'RENT/LEASE', 'withdrawals': 1475.25, 'deposits': None, 'balance': 5794.32},
    {'date': '2012-01-09', 'description': 'Dec-11 PMT', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'PRE-AUTH DEBIT', 'withdrawals': 101.14, 'deposits': None, 'balance': 5693.18},
    {'date': '2012-01-09', 'description': '6948200000034', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'LPL BUSINESS PAD', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'PURCHASE00001201908', 'withdrawals': 36.00, 'deposits': None, 'balance': 5657.18},
    {'date': '2012-01-09', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'DEPOSIT', 'withdrawals': None, 'deposits': 1620.00, 'balance': 7277.18},
    {'date': '2012-01-09', 'description': 'PRE-AUTH DEBIT', 'withdrawals': 202.27, 'deposits': None, 'balance': 7074.91},
    {'date': '2012-01-09', 'description': '6005230090122', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'LPL BUSINESS PAD', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-09', 'description': 'PURCHASE00001201888', 'withdrawals': 3234.66, 'deposits': None, 'balance': 3840.25},
    {'date': '2012-01-09', 'description': 'CHEQUE 1020941 206', 'withdrawals': 1690.68, 'deposits': None, 'balance': 2149.57},
    {'date': '2012-01-10', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 2354.57},
    {'date': '2012-01-10', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-10', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-11', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 2559.57},
    {'date': '2012-01-11', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-11', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-11', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 2764.57},
    {'date': '2012-01-11', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-11', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-11', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 175.00, 'balance': 2939.57},
    {'date': '2012-01-11', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-11', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 5
    {'date': '2012-01-11', 'description': 'ABM WITHDRAWAL 2OKQ', 'withdrawals': 80.00, 'deposits': None, 'balance': 2879.57},
    {'date': '2012-01-11', 'description': '7-ELEVEN #9912', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 345.00, 'balance': 3224.57},
    {'date': '2012-01-12', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': 455.96, 'balance': 3680.53},
    {'date': '2012-01-12', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 261.00, 'balance': 3941.53},
    {'date': '2012-01-12', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'PURCHASE00001210227', 'withdrawals': 65.51, 'deposits': None, 'balance': 3876.02},
    {'date': '2012-01-12', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'PURCHASE00001208842', 'withdrawals': 348.00, 'deposits': None, 'balance': 3528.02},
    {'date': '2012-01-12', 'description': 'PASSPORT/RSUSSR', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'PURCHASE01714534474', 'withdrawals': 19.50, 'deposits': None, 'balance': 3508.52},
    {'date': '2012-01-12', 'description': '#OKYO KOREAN BI', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'CHEQUE #208', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-12', 'description': 'DEPOSIT', 'withdrawals': None, 'deposits': 440.00, 'balance': 3948.52},
    {'date': '2012-01-12', 'description': 'WITHDRAWAL', 'withdrawals': 1000.00, 'deposits': None, 'balance': 2948.52},
    {'date': '2012-01-12', 'description': 'PURCHASE42501001010', 'withdrawals': 134.40, 'deposits': None, 'balance': 2814.12},
    {'date': '2012-01-12', 'description': 'HERTZ', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-13', 'description': 'PURCHASE00001205268', 'withdrawals': 99.94, 'deposits': None, 'balance': 2714.18},
    {'date': '2012-01-13', 'description': 'PETRO-CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-13', 'description': 'PURCHASE00001482003', 'withdrawals': 8.55, 'deposits': None, 'balance': 2705.63},
    {'date': '2012-01-13', 'description': 'PURCHASE01701001009', 'withdrawals': 134.40, 'deposits': None, 'balance': 2571.23},
    {'date': '2012-01-16', 'description': 'HERTZ', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 925.00, 'balance': 3496.23},
    {'date': '2012-01-16', 'description': 'DEBIT MEMO', 'withdrawals': 3494.63, 'deposits': None, 'balance': 1.60},
    {'date': '2012-01-16', 'description': 'CRA Unregistered RM', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 150.00, 'balance': 151.60},
    {'date': '2012-01-16', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 356.60},
    {'date': '2012-01-16', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 6
    {'date': '2012-01-16', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 78.75, 'balance': 435.35},
    {'date': '2012-01-16', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'INSURANCE', 'withdrawals': 83.46, 'deposits': None, 'balance': 351.89},
    {'date': '2012-01-16', 'description': 'WOODRIDGE INSURANCE COMPANY', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'RENT/LEASE', 'withdrawals': 1885.65, 'deposits': None, 'balance': -1533.76},  # Handwritten: Intact
    {'date': '2012-01-16', 'description': 'L08136', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'JACK CARTER', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'RENT/LEASE', 'withdrawals': 2525.25, 'deposits': None, 'balance': -4059.01},  # Handwritten: Intact
    {'date': '2012-01-16', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'RENT/LEASE', 'withdrawals': 1475.25, 'deposits': None, 'balance': -5534.26},  # Handwritten: Intact, CMB
    {'date': '2012-01-16', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'RENT/LEASE', 'withdrawals': 1900.50, 'deposits': None, 'balance': -7434.76},  # Handwritten: Intact, CMB
    {'date': '2012-01-16', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'PAD PMT FEE 00339', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-16', 'description': 'CORRECTION 00339', 'withdrawals': None, 'deposits': 1885.65, 'balance': -4073.86},  # Handwritten: Intact, CMB
    {'date': '2012-01-16', 'description': 'CORRECTION 00339', 'withdrawals': None, 'deposits': 1900.50, 'balance': -2173.36},  # Handwritten: Intact, CMB
    {'date': '2012-01-16', 'description': 'CORRECTION 00339', 'withdrawals': None, 'deposits': 2525.25, 'balance': 351.89},  # Handwritten: Intact, CMB
    {'date': '2012-01-16', 'description': 'NSF CHARGE 00339', 'withdrawals': 170.00, 'deposits': None, 'balance': 181.89},
    {'date': '2012-01-17', 'description': 'PURCHASE00001215094', 'withdrawals': 91.00, 'deposits': None, 'balance': 90.89},
    {'date': '2012-01-17', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'PURCHASE00001239643', 'withdrawals': 23.50, 'deposits': None, 'balance': 67.39},
    {'date': '2012-01-17', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 641.87, 'balance': 709.26},
    {'date': '2012-01-17', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 378.00, 'balance': 1087.26},
    {'date': '2012-01-17', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 1292.26},
    {'date': '2012-01-17', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 1154.11, 'balance': 2446.37},
    {'date': '2012-01-17', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-17', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 1131.46, 'balance': 3577.83},
    {'date': '2012-01-18', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'PURCHASE00001211011', 'withdrawals': 45.56, 'deposits': None, 'balance': 3532.27},
    {'date': '2012-01-18', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 7
    {'date': '2012-01-18', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 175.00, 'balance': 3707.27},
    {'date': '2012-01-18', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'PURCHASE00001217071', 'withdrawals': 51.04, 'deposits': None, 'balance': 3656.23},
    {'date': '2012-01-18', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'PURCHASE2016*1433587', 'withdrawals': 800.00, 'deposits': None, 'balance': 2856.23},
    {'date': '2012-01-18', 'description': 'THE PHONE EXPER', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-18', 'description': 'PURCHASE2019*1424117', 'withdrawals': 287.68, 'deposits': None, 'balance': 2568.55},
    {'date': '2012-01-18', 'description': 'THE PHONE EXPER', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'ABM WITHDRAWAL 2OKQ', 'withdrawals': 100.00, 'deposits': None, 'balance': 2468.55},
    {'date': '2012-01-19', 'description': '7-ELEVEN #9912', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'PURCHASE23183*1341497', 'withdrawals': 50.43, 'deposits': None, 'balance': 2418.12},
    {'date': '2012-01-19', 'description': 'SAFEWAY #288', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'PURCHASE00001218007', 'withdrawals': 47.00, 'deposits': None, 'balance': 2371.12},
    {'date': '2012-01-19', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 156.00, 'balance': 2527.12},
    {'date': '2012-01-19', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 2732.12},
    {'date': '2012-01-19', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 432.25, 'balance': 3164.37},
    {'date': '2012-01-19', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-19', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-20', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 158.00, 'balance': 3322.37},
    {'date': '2012-01-20', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-20', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-20', 'description': 'INTERNET BILL PMT00002079644', 'withdrawals': 891.72, 'deposits': None, 'balance': 2430.65},
    {'date': '2012-01-20', 'description': 'ROGERS WIRELESS', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-20', 'description': 'PURCHASE00001219912', 'withdrawals': 75.00, 'deposits': None, 'balance': 2355.65},
    {'date': '2012-01-20', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-20', 'description': 'DEBIT MEMO', 'withdrawals': 21.62, 'deposits': None, 'balance': 2332.03},
    {'date': '2012-01-20', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-20', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 8
    {'date': '2012-01-23', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 1783.69, 'balance': 4115.72},
    {'date': '2012-01-23', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-23', 'description': 'ABM WITHDRAWAL 2OKQ', 'withdrawals': 100.00, 'deposits': None, 'balance': 4015.72},
    {'date': '2012-01-23', 'description': '7-ELEVEN #9912', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-23', 'description': 'PURCHASE00001233275', 'withdrawals': 75.60, 'deposits': None, 'balance': 3940.12},
    {'date': '2012-01-23', 'description': 'BUCK OR TWO #23', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-23', 'description': 'PURCHASE00001214023', 'withdrawals': 46.32, 'deposits': None, 'balance': 3893.80},
    {'date': '2012-01-23', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-23', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 175.00, 'balance': 4068.80},
    {'date': '2012-01-23', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-23', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-24', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 4273.80},
    {'date': '2012-01-24', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-24', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 165.00, 'balance': 4438.80},
    {'date': '2012-01-24', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-24', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-24', 'description': 'INSURANCE', 'withdrawals': 268.92, 'deposits': None, 'balance': 4169.88},
    {'date': '2012-01-24', 'description': 'JEVCO INSURANCE CAMPANY', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-24', 'description': 'INSURANCE', 'withdrawals': 1271.47, 'deposits': None, 'balance': 2898.41},
    {'date': '2012-01-24', 'description': 'IFS PREMIUM FIN', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-24', 'description': 'INSURANCE', 'withdrawals': 110.42, 'deposits': None, 'balance': 2787.99},
    {'date': '2012-01-25', 'description': 'IFS PREMIUM FIN', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-25', 'description': 'PURCHASE00001001124', 'withdrawals': 114.47, 'deposits': None, 'balance': 2673.52},
    {'date': '2012-01-25', 'description': 'SAVE ON FOODS #', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-25', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 325.00, 'balance': 2998.52},
    {'date': '2012-01-25', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-25', 'description': 'RENT/LEASE', 'withdrawals': 1900.50, 'deposits': None, 'balance': 1098.02},  # Handwritten: Intact
    {'date': '2012-01-25', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-25', 'description': 'RENT/LEASE', 'withdrawals': 2525.25, 'deposits': None, 'balance': -1427.23},  # Handwritten: Intact
    {'date': '2012-01-25', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-25', 'description': 'RENT/LEASE', 'withdrawals': 1475.25, 'deposits': None, 'balance': -2902.48},  # Handwritten: Intact
    {'date': '2012-01-25', 'description': 'HEFFNER AUTO FC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-25', 'description': 'CORRECTION 00339', 'withdrawals': None, 'deposits': 1475.25, 'balance': -1427.23},  # Handwritten: Intact, CMB
    {'date': '2012-01-25', 'description': 'CORRECTION 00339', 'withdrawals': None, 'deposits': 1900.50, 'balance': 473.27},  # Handwritten: Intact, CMB
    {'date': '2012-01-25', 'description': 'NSF CHARGE 00339', 'withdrawals': 85.00, 'deposits': None, 'balance': 388.27},
    
    # Page 9
    {'date': '2012-01-30', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 990.00, 'balance': 1378.27},
    {'date': '2012-01-30', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 205.00, 'balance': 1583.27},
    {'date': '2012-01-30', 'description': '4017775 DP', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'GBL DP4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 56.00, 'balance': 1639.27},
    {'date': '2012-01-30', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'GBL DP4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 196.50, 'balance': 1835.77},
    {'date': '2012-01-30', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 234.00, 'balance': 2069.77},
    {'date': '2012-01-30', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 162.75, 'balance': 2232.52},
    {'date': '2012-01-30', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 241.25, 'balance': 2473.77},
    {'date': '2012-01-30', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-30', 'description': 'MISC PAYMENT', 'withdrawals': 4.95, 'deposits': None, 'balance': 2468.82},
    {'date': '2012-01-30', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 726.00, 'balance': 3194.82},
    {'date': '2012-01-31', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 724.00, 'balance': 3918.82},
    {'date': '2012-01-31', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 412.50, 'balance': 4331.32},
    {'date': '2012-01-31', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 157.50, 'balance': 4488.82},
    {'date': '2012-01-31', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'PURCHASE00001015901', 'withdrawals': 1170.75, 'deposits': None, 'balance': 3318.07},
    {'date': '2012-01-31', 'description': 'FULL SPECTRUM K', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'PURCHASE00001182003', 'withdrawals': 1443.24, 'deposits': None, 'balance': 1874.83},
    {'date': '2012-01-31', 'description': 'EBLES AUTO REPA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'TRANSFER', 'withdrawals': 1800.00, 'deposits': None, 'balance': 74.83},
    {'date': '2012-01-31', 'description': 'TO 0033920-28362', 'withdrawals': None, 'deposits': None, 'balance': None},
    
    # Page 10 (Final page)
    {'date': '2012-01-31', 'description': 'DEBIT MEMO', 'withdrawals': 82.50, 'deposits': None, 'balance': -7.67},
    {'date': '2012-01-31', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-01-31', 'description': 'E-TRANSFER NWK FEE', 'withdrawals': 1.50, 'deposits': None, 'balance': -9.17},
    {'date': '2012-01-31', 'description': 'ACCOUNT FEE', 'withdrawals': 35.00, 'deposits': None, 'balance': -44.17},  # Handwritten: $1.50 CMB
    {'date': '2012-01-31', 'description': 'OVERDRAFT SIC', 'withdrawals': 5.00, 'deposits': None, 'balance': -49.17},
]

STATEMENT_SUMMARY = {
    'account_number': '74-61615',
    'branch': '00339',
    'statement_period': ('2012-01-01', '2012-01-31'),
    'opening_balance': Decimal('7177.34'),
    'closing_balance': Decimal('-49.17'),  # From first page summary
    'total_withdrawals': Decimal('4203.83'),
    'total_deposits': Decimal('46977.32'),
}

def check_banking_transactions_table(conn):
    """Check if banking_transactions table exists and what columns it has."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check table existence
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'banking_transactions'
        );
    """)
    table_exists = cur.fetchone()['exists']
    
    if not table_exists:
        print("[FAIL] Table 'banking_transactions' does NOT exist")
        cur.close()
        return None
    
    print("[OK] Table 'banking_transactions' exists")
    
    # Get column names
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'banking_transactions'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    print(f"\n📋 Columns in banking_transactions ({len(columns)} total):")
    for col in columns:
        print(f"   - {col['column_name']} ({col['data_type']})")
    
    cur.close()
    return [col['column_name'] for col in columns]

def query_jan2012_transactions(conn, columns):
    """Query banking_transactions for January 2012."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Build query based on available columns
    account_filter = ""
    if 'account_number' in columns:
        account_filter = "AND account_number = '74-61615'"
    elif 'account_name' in columns:
        account_filter = "AND account_name LIKE '%CIBC%'"
    
    query = f"""
        SELECT *
        FROM banking_transactions
        WHERE transaction_date >= '2012-01-01'
          AND transaction_date <= '2012-01-31'
          {account_filter}
        ORDER BY transaction_date, transaction_id;
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    return rows

def match_statement_to_db(statement_txns, db_txns):
    """Match statement transactions to database records."""
    
    print(f"\n{'='*80}")
    print(f"CIBC STATEMENT VERIFICATION - JANUARY 2012")
    print(f"Account: 74-61615 | Branch: 00339")
    print(f"{'='*80}\n")
    
    print(f"📄 Statement transactions: {len(statement_txns)}")
    print(f"💾 Database transactions: {len(db_txns)}")
    
    if len(db_txns) == 0:
        print("\n[FAIL] NO DATABASE RECORDS FOUND for January 2012!")
        print("\n📋 Statement Summary:")
        print(f"   Period: {STATEMENT_SUMMARY['statement_period'][0]} to {STATEMENT_SUMMARY['statement_period'][1]}")
        print(f"   Opening Balance: ${STATEMENT_SUMMARY['opening_balance']:,.2f}")
        print(f"   Closing Balance: ${STATEMENT_SUMMARY['closing_balance']:,.2f}")
        print(f"   Total Withdrawals: ${STATEMENT_SUMMARY['total_withdrawals']:,.2f}")
        print(f"   Total Deposits: ${STATEMENT_SUMMARY['total_deposits']:,.2f}")
        print(f"   Transaction Count: {len([t for t in statement_txns if t['withdrawals'] or t['deposits']])}")
        
        print("\n🔍 Sample Statement Transactions (first 10):")
        count = 0
        for txn in statement_txns:
            if txn['withdrawals'] or txn['deposits']:
                amount = txn['withdrawals'] if txn['withdrawals'] else txn['deposits']
                txn_type = 'W' if txn['withdrawals'] else 'D'
                print(f"   {txn['date']} | {txn_type} ${amount:>10.2f} | {txn['description']}")
                count += 1
                if count >= 10:
                    break
        
        return {'matched': 0, 'missing': len(statement_txns), 'coverage': 0.0}
    
    # If we have DB records, do detailed matching
    matched = 0
    missing = []
    
    for stmt_txn in statement_txns:
        if stmt_txn['withdrawals'] is None and stmt_txn['deposits'] is None:
            continue  # Skip balance forward and incomplete rows
        
        stmt_date = stmt_txn['date']
        stmt_desc = stmt_txn['description']
        stmt_amount = stmt_txn['withdrawals'] if stmt_txn['withdrawals'] else stmt_txn['deposits']
        
        # Try to find match in DB
        found = False
        for db_txn in db_txns:
            db_date = str(db_txn.get('transaction_date', ''))
            if db_date != stmt_date:
                continue
            
            # Check amount match (debit or credit)
            db_debit = db_txn.get('debit_amount', 0) or 0
            db_credit = db_txn.get('credit_amount', 0) or 0
            
            if stmt_txn['withdrawals'] and abs(float(db_debit) - float(stmt_amount)) < 0.01:
                found = True
                matched += 1
                break
            elif stmt_txn['deposits'] and abs(float(db_credit) - float(stmt_amount)) < 0.01:
                found = True
                matched += 1
                break
        
        if not found:
            missing.append(stmt_txn)
    
    total_stmt_txns = len([t for t in statement_txns if t['withdrawals'] or t['deposits']])
    coverage = (matched / total_stmt_txns * 100) if total_stmt_txns > 0 else 0
    
    print(f"\n[OK] Matched: {matched}/{total_stmt_txns} ({coverage:.1f}%)")
    print(f"[FAIL] Missing: {len(missing)}")
    
    if missing and len(missing) <= 20:
        print("\n🔍 Missing Transactions:")
        for txn in missing:
            amount = txn['withdrawals'] if txn['withdrawals'] else txn['deposits']
            txn_type = 'W' if txn['withdrawals'] else 'D'
            print(f"   {txn['date']} | {txn_type} ${amount:>10.2f} | {txn['description']}")
    
    return {'matched': matched, 'missing': len(missing), 'coverage': coverage}

def main():
    print("🔍 Verifying CIBC Statement - January 2012\n")
    
    conn = get_db_connection()
    
    # Step 1: Check table structure
    columns = check_banking_transactions_table(conn)
    
    if columns is None:
        print("\n[WARN] Cannot proceed - banking_transactions table not found")
        print("💡 Need to check other possible table names:")
        print("   - cibc_transactions")
        print("   - bank_statements")
        print("   - transactions")
        conn.close()
        return
    
    # Step 2: Query January 2012 transactions
    print("\n🔎 Querying database for January 2012 CIBC transactions...")
    db_txns = query_jan2012_transactions(conn, columns)
    
    # Step 3: Match statement to database
    result = match_statement_to_db(STATEMENT_TRANSACTIONS, db_txns)
    
    # Step 4: Final verdict
    print(f"\n{'='*80}")
    if result['coverage'] >= 95:
        print("[OK] EXCELLENT - Statement data is in ALMS database")
    elif result['coverage'] >= 75:
        print("[WARN] GOOD - Most statement data in ALMS, some gaps")
    elif result['coverage'] >= 50:
        print("[WARN] PARTIAL - Significant gaps in database coverage")
    elif result['coverage'] > 0:
        print("[FAIL] POOR - Minimal database coverage")
    else:
        print("[FAIL] NOT FOUND - Statement data NOT in ALMS database")
    print(f"{'='*80}\n")
    
    conn.close()

if __name__ == '__main__':
    main()
