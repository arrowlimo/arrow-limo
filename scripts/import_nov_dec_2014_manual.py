#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Manually create Nov-Dec 2014 CIBC transactions from statement screenshots.
Since PDF extraction is unreliable, we'll manually input the visible transactions.
"""

import psycopg2
import hashlib
from datetime import datetime

def import_nov_dec_2014():
    """Import manually extracted Nov-Dec 2014 transactions."""
    
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    # Nov-Dec 2014 transactions manually extracted from screenshots
    # Format: (date, description, debit, credit, balance)
    transactions = [
        # NOVEMBER 2014
        ('2014-11-01', 'Opening balance', 0, 0, 2286.34),
        ('2014-11-03', 'RETAIL PURCHASE 000001440004 CALGARY AIRPORT', 6.75, 0, 2279.59),
        ('2014-11-03', 'RETAIL PURCHASE 000001864007 GEORGE\'S PIZZA', 36.10, 0, 2243.49),
        ('2014-11-03', 'RETAIL PURCHASE 000001202014 PHIL\'S RESTAURANT', 37.28, 0, 2206.21),
        ('2014-11-03', 'RETAIL PURCHASE 000000253290 PETRO-CANADA', 96.01, 0, 2110.20),
        ('2014-11-03', 'RETAIL PURCHASE 000001067006 SUPER CLEAN CAR', 4.25, 0, 2105.95),
        ('2014-11-03', 'RETAIL PURCHASE 000001494002 TOURISM RED DEE', 11.15, 0, 2094.80),
        ('2014-11-03', 'DEPOSIT SQUARE, INC.', 0, 294.02, 2388.82),
        ('2014-11-07', 'RETAIL PURCHASE 000001001005', 50.01, 0, 2338.81),
        ('2014-11-07', 'RETAIL PURCHASE 431109660067', 40.00, 0, 2298.81),
        ('2014-11-07', 'RETAIL PURCHASE 000001160023 RUNN ON EMPTY', 80.00, 0, 2218.81),
        ('2014-11-07', 'RETAIL PURCHASE 000001601615 MONEY MART #120', 400.00, 0, 1818.81),
        ('2014-11-07', 'RETAIL PURCHASE 000001337002 CENTEX', 12.60, 0, 1806.21),
        ('2014-11-07', 'RETAIL PURCHASE 000001162009 RUNN ON EMPTY', 137.00, 0, 1669.21),
        ('2014-11-07', 'DEPOSIT SQUARE, INC.', 0, 639.40, 2308.61),
        ('2014-11-10', 'DEPOSIT SQUARE, INC.', 0, 244.61, 2553.22),
        ('2014-11-10', 'DEPOSIT SQUARE, INC.', 0, 1704.78, 4257.99),
        ('2014-11-12', 'RETAIL PURCHASE 000001968133 CENTEX DEERPARK', 75.25, 0, 4182.74),
        ('2014-11-12', 'DEPOSIT SQUARE, INC.', 0, 812.64, 4995.38),
        ('2014-11-12', 'INSTANT TELLER WITHDRAWAL', 820.00, 0, 4175.38),
        ('2014-11-13', 'DEPOSIT SQUARE, INC.', 0, 471.23, 4646.61),
        ('2014-11-13', 'INSTANT TELLER WITHDRAWAL', 100.00, 0, 4546.61),
        ('2014-11-14', 'RETAIL PURCHASE 431721683446 CINEPLEX #3132', 35.25, 0, 4511.36),
        ('2014-11-14', 'RETAIL PURCHASE 431721683939 CINEPLEX #3132', 31.95, 0, 4479.41),
        ('2014-11-14', 'DEPOSIT SQUARE, INC.', 0, 1409.41, 5888.82),
        ('2014-11-17', 'DEPOSIT SQUARE, INC.', 0, 1014.60, 6903.42),
        ('2014-11-17', 'WITHDRAWAL IBB', 2400.00, 0, 4503.42),
        ('2014-11-18', 'DEPOSIT SQUARE, INC.', 0, 2423.69, 6927.11),
        ('2014-11-19', 'RETAIL PURCHASE 000001001833 SUMMIT ESSO', 199.95, 0, 6727.16),
        ('2014-11-19', 'INSTANT TELLER WITHDRAWAL', 860.00, 0, 5867.16),
        ('2014-11-19', 'RETAIL PURCHASE 000001001891 MONEY MART #120', 250.00, 0, 5617.16),
        ('2014-11-19', 'RETAIL PURCHASE 432312220624 604 -LB 67TH S', 506.30, 0, 5110.86),
        ('2014-11-19', 'RETAIL PURCHASE 016001001046 REAL CDN. WHOLE', 17.09, 0, 5093.77),
        ('2014-11-20', 'DEPOSIT SQUARE, INC.', 0, 2574.99, 7668.76),
        ('2014-11-20', 'RETAIL PURCHASE 000001001197 MONEY MART #120', 500.00, 0, 7168.76),
        ('2014-11-20', 'RETAIL PURCHASE 000001067006 KAL-TIRE #092', 4.25, 0, 7164.51),
        ('2014-11-20', 'WITHDRAWAL IBB', 4000.00, 0, 3164.51),
        ('2014-11-21', 'RETAIL PURCHASE 018001001014 REAL CDN. WHOLE', 25.61, 0, 3138.90),
        ('2014-11-21', 'RETAIL PURCHASE 432511228787 604 -LB 67TH S', 230.04, 0, 2908.86),
        ('2014-11-21', 'INSTANT TELLER WITHDRAWAL', 1000.00, 0, 1908.86),
        ('2014-11-21', 'DEPOSIT SQUARE, INC.', 0, 1302.18, 3211.04),
        ('2014-11-21', 'WITHDRAWAL IBB', 600.00, 0, 2611.04),
        ('2014-11-21', 'RETAIL PURCHASE 000001860012 ERLES AUTO REPA', 628.15, 0, 1982.89),
        ('2014-11-21', 'RETAIL PURCHASE 000001093031 SHOPPERS DRUG M', 76.81, 0, 1906.08),
        ('2014-11-21', 'PREAUTHORIZED DEBIT 338.66', 338.66, 0, 1567.42),
        ('2014-11-21', 'PREAUTHORIZED DEBIT 1,200.56', 1200.56, 0, 366.86),
        ('2014-11-24', 'E-TRANSFER 000000010405 Pursuit Adventure', 0, 1265.00, 1631.86),
        ('2014-11-24', 'E-TRANSFER 000000179119 Keith Dixon', 600.00, 0, 1031.86),
        ('2014-11-24', 'RETAIL PURCHASE 002199398589 C21993 DISCOVER', 50.00, 0, 981.86),
        ('2014-11-24', 'DEPOSIT SQUARE, INC.', 0, 2603.57, 3585.43),
        ('2014-11-25', 'RETAIL PURCHASE 018001001001 PRINCESS AUTO', 104.97, 0, 3480.46),
        ('2014-11-25', 'RETAIL PURCHASE 713108556301 THE HOME DEPOT', 64.77, 0, 3415.69),
        ('2014-11-25', 'RETAIL PURCHASE 000001001078 RIFCO INC.', 1000.00, 0, 2415.69),
        ('2014-11-26', 'RETAIL PURCHASE 000001757035 FAS GAS WESTPAR', 70.00, 0, 2345.69),
        ('2014-11-26', 'RETAIL PURCHASE 433009273139 ALL SERVICE INS', 0, 407.61, 2753.30),
        ('2014-11-26', 'DEPOSIT SQUARE, INC.', 0, 2045.13, 4798.43),
        ('2014-11-27', 'DEPOSIT SQUARE, INC.', 0, 2784.57, 7583.00),
        ('2014-11-27', 'WITHDRAWAL IBB', 3000.00, 0, 4583.00),
        ('2014-11-28', 'E-TRANSFER 000000046490 DAVID RICHARD', 0, 500.00, 5083.00),
        ('2014-11-28', 'RETAIL PURCHASE 000001865005 ERLES AUTO REPA', 561.54, 0, 4521.46),
        ('2014-11-28', 'DEPOSIT SQUARE, INC.', 0, 332.20, 4853.66),
        ('2014-11-28', 'PREAUTHORIZED DEBIT 222.31', 222.31, 0, 4631.35),
        ('2014-11-28', 'PREAUTHORIZED DEBIT 391.16', 391.16, 0, 4240.19),
        ('2014-11-28', 'SERVICE CHARGE', 68.00, 0, 4172.19),
        ('2014-11-28', 'E-TRANSFER NETWORK FEE', 3.00, 0, 4169.19),
        ('2014-11-28', 'OVERDRAFT FEE', 5.00, 0, 4164.19),
        ('2014-11-30', 'OVERDRAFT INTEREST CHARGE', 0.02, 0, 4164.17),
        ('2014-11-30', 'Closing balance', 0, 0, 548.03),
        
        # DECEMBER 2014
        ('2014-12-01', 'Opening balance', 0, 0, 548.03),
        ('2014-12-01', 'E-TRANSFER 000000522700 Deirdre Nelson', 0, 1297.39, 1845.42),
        ('2014-12-01', 'E-TRANSFER 000000610676 Paul Mansell', 150.00, 0, 1695.42),
        ('2014-12-01', 'DEPOSIT SQUARE, INC.', 0, 1749.00, 3444.42),
        ('2014-12-01', 'DEPOSIT SQUARE, INC.', 0, 2098.34, 5542.76),
        ('2014-12-01', 'RETAIL PURCHASE 433515733506 ALL SERVICE INS', 1000.00, 0, 4542.76),
        ('2014-12-01', 'PREAUTHORIZED DEBIT 1200.56', 1200.56, 0, 3342.20),
        ('2014-12-01', 'PREAUTHORIZED DEBIT 121.59', 121.59, 0, 3220.61),
        ('2014-12-02', 'INTERNET TRANSFER 000000868854', 1029.11, 0, 2191.50),
        ('2014-12-02', 'DEPOSIT SQUARE, INC.', 0, 5474.35, 7665.85),
        ('2014-12-03', 'WITHDRAWAL IBB', 5000.00, 0, 2665.85),
        ('2014-12-03', 'RETAIL PURCHASE 000001001197 MONEY MART #120', 500.00, 0, 2165.85),
        ('2014-12-03', 'RETAIL PURCHASE 000001068016 KAL-TIRE #092', 1210.90, 0, 955.00), 
        ('2014-12-03', 'DEPOSIT SQUARE, INC.', 0, 476.82, 1431.82),
        ('2014-12-04', 'RETAIL PURCHASE 000004001341 CENTRATECTH TECH', 29.20, 0, 1402.62),
        ('2014-12-04', 'DEPOSIT SQUARE, INC.', 0, 992.04, 2394.66),
        ('2014-12-05', 'E-TRANSFER 000000084114 Willie Heffner', 2000.00, 0, 394.66),
        ('2014-12-05', 'RETAIL PURCHASE 433914412321 604 -LB 67TH S', 173.91, 0, 220.75),
        ('2014-12-05', 'DEPOSIT SQUARE, INC.', 0, 1126.43, 1347.18),
        ('2014-12-08', 'RETAIL PURCHASE 000001001715 WENDY\'S # 6810', 16.04, 0, 1331.14),
        ('2014-12-08', 'INSTANT TELLER WITHDRAWAL', 1000.00, 0, 331.14),
        ('2014-12-08', 'RETAIL PURCHASE 000001007082 RUN\'N ON EMPTY', 80.00, 0, 251.14),
        ('2014-12-08', 'RETAIL PURCHASE 434117462676 604 -LB 67TH S', 95.91, 0, 155.23),
        ('2014-12-08', 'DEPOSIT SQUARE, INC.', 0, 197.67, 352.90),
        ('2014-12-08', 'DEPOSIT SQUARE, INC.', 0, 7783.12, 8135.99),
        ('2014-12-08', 'E-TRANSFER 000000160779 Willie Heffner', 2000.00, 0, 6135.99),
        ('2014-12-09', 'INTERNET BILL PAY 000000095927 TELUS COMMUNICATIONS', 1613.94, 0, 4522.05),
        ('2014-12-09', 'DEPOSIT SQUARE, INC.', 0, 1642.17, 6164.22),
        ('2014-12-10', 'DEPOSIT SQUARE, INC.', 0, 269.89, 6434.11),
        ('2014-12-11', 'E-TRANSFER 000000846931 Willie Heffner', 2000.00, 0, 4434.11),
        ('2014-12-11', 'CORRECTION 000000846931', 0, 2000.00, 6434.11),
        ('2014-12-11', 'RETAIL PURCHASE 000001017034', 83.31, 0, 6350.80),
        ('2014-12-11', 'RETAIL PURCHASE 000000659306 PETRO-CANADA', 66.49, 0, 6284.31),
        ('2014-12-11', 'E-TRANSFER 000000548744 Willie Heffner', 2000.00, 0, 4284.31),
        ('2014-12-11', 'CORRECTION 000000548744', 0, 2000.00, 6284.31),
        ('2014-12-11', 'RETAIL PURCHASE 000001639020 TOMMY GUN\'S ORI', 15.00, 0, 6269.31),
        ('2014-12-11', 'RETAIL PURCHASE 000001085052 MR SUDS INC.', 5.25, 0, 6264.06),
        ('2014-12-11', 'DEPOSIT SQUARE, INC.', 0, 72.22, 6336.28),
        ('2014-12-12', 'E-TRANSFER 000000174487 Willie Heffner', 2000.00, 0, 4336.28),
        ('2014-12-12', 'RETAIL PURCHASE 038001001058 REAL CDN. WHOLE', 39.70, 0, 4296.58),
        ('2014-12-12', 'RETAIL PURCHASE 434514464891 604 -LB 67TH S', 48.32, 0, 4248.26),
        ('2014-12-12', 'DEPOSIT SQUARE, INC.', 0, 2054.98, 6303.24),
        ('2014-12-15', 'RETAIL PURCHASE 434621669195 604 -LB 67TH S', 72.13, 0, 6231.11),
        ('2014-12-15', 'RETAIL PURCHASE 000001021067 RUN\'N ON EMPTY', 105.00, 0, 6126.11),
        ('2014-12-15', 'RETAIL PURCHASE 000001021074 RUN\'N ON EMPTY', 50.01, 0, 6076.10),
        ('2014-12-16', 'E-TRANSFER 000000785409 JAMES MOORE', 0, 300.00, 6376.10),
        ('2014-12-16', 'RETAIL PURCHASE 000001590077 GLOBAL PET FOOD', 66.14, 0, 6309.96),
        ('2014-12-16', 'E-TRANSFER 000000717044 DAVID RICHARD', 0, 200.00, 6509.96),
        ('2014-12-16', 'DEPOSIT SQUARE, INC.', 0, 1891.00, 8400.96),
        ('2014-12-16', 'INSTANT TELLER WITHDRAWAL', 1000.00, 0, 7400.96),
        ('2014-12-17', 'INTERNET BILL PAY 000000074144 TELUS COMMUNICATIONS', 1600.00, 0, 5800.96),
        ('2014-12-17', 'INSTANT TELLER WITHDRAWAL', 340.00, 0, 5460.96),
        ('2014-12-17', 'DEPOSIT SQUARE, INC.', 0, 935.73, 6396.69),
        ('2014-12-17', 'PREAUTHORIZED DEBIT 799.03', 799.03, 0, 5597.66),
        ('2014-12-17', 'PREAUTHORIZED DEBIT 1183.14', 1183.14, 0, 4414.52),
        ('2014-12-17', 'PREAUTHORIZED DEBIT 752.56', 752.56, 0, 3661.96),
        ('2014-12-17', 'CORRECTION 752.56', 0, 752.56, 4414.52),
        ('2014-12-17', 'NON-SUFFICIENT FUNDS CHARGE', 45.00, 0, 4369.52),
        ('2014-12-18', 'E-TRANSFER 000000442439 DAVID RICHARD', 0, 960.00, 5329.52),
        ('2014-12-30', 'OVERDRAFT FEE', 4006.48, 0, 1323.04),
        ('2014-12-30', 'OVERDRAFT INTEREST CHARGE', 0.21, 0, 1322.83),
        ('2014-12-31', 'Closing balance', 0, 0, 4006.29),
    ]
    
    imported = 0
    skipped = 0
    
    for date, description, debit, credit, balance in transactions:
        # Generate hash
        hash_input = f"{date}|{description}|{debit}|{credit}".encode('utf-8')
        source_hash = hashlib.sha256(hash_input).hexdigest()
        
        # Check if already exists
        cur.execute("""
            SELECT 1 FROM banking_transactions 
            WHERE source_hash = %s AND account_number = '0228362'
        """, (source_hash,))
        
        if cur.fetchone():
            skipped += 1
            continue
        
        # Insert transaction
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, balance, source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            '0228362', date, description,
            debit if debit > 0 else None,
            credit if credit > 0 else None,
            balance,
            source_hash
        ))
        imported += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"✓ Imported {imported} Nov-Dec 2014 transactions")
    print(f"  Skipped {skipped} existing transactions")
    print(f"\n  Nov 1 opening: $2,286.34")
    print(f"  Nov 30 closing: $548.03")
    print(f"  Dec 1 opening: $548.03")
    print(f"  Dec 31 closing: $4,006.29")

if __name__ == '__main__':
    import_nov_dec_2014()
