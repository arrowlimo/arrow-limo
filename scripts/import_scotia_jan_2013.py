"""
Import Scotia Bank January 2013 transactions from manual screenshot extraction.
This script processes the transaction data extracted from PDF screenshots.

Usage:
    python import_scotia_jan_2013.py              # Dry-run (preview only)
    python import_scotia_jan_2013.py --write      # Apply to database
"""

import psycopg2
import hashlib
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def generate_hash(date, description, withdrawal, deposit):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"{date}|{description}|{withdrawal:.2f}|{deposit:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def extract_vendor_from_description(description):
    """Extract vendor name from transaction description."""
    desc = description.upper().strip()
    
    # Remove common prefixes
    prefixes = [
        'POINT OF SALE PURCHASE', 'POS PURCHASE', 'PURCHASE',
        'DEBIT MEMO', 'CREDIT MEMO', 'DEPOSIT', 'CHQ', 'CHEQUE',
        'ABM WITHDRAWAL', 'RENT/LEASES', 'PC BILL PAYMENT',
        'OVERDRAWN HANDLING CHGS', 'SERVICE CHARGE', 'OVERDRAFT INTEREST CHG'
    ]
    
    for prefix in prefixes:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip()
            break
    
    # Clean up
    desc = desc.replace('RED DEER AB', '').replace('RED DEER ABCA', '').replace('RED DEER ABCD', '')
    desc = desc.strip()
    
    # If still long, take first meaningful part
    if len(desc) > 50:
        parts = desc.split()
        desc = ' '.join(parts[:5])
    
    return desc if desc else 'UNKNOWN'

# Transaction data extracted from screenshots
# Format: (date, description, withdrawal, deposit, balance)
# Date is when transaction posted (the date line BELOW the transaction)
transactions = [
    # Screenshot 1 - transactions with date 0503 (May 3rd, but this is actually Jan 3rd based on context)
    # Wait, looking at column header "M D", this is Month Day
    # 0503 = Month 05, Day 03? No, that would be May
    # Let me re-read: User said "the date is the last line of the transaction so everything above is the lower date"
    # Looking at balance column: 0430 at top, then 0501, then 0502, 0503
    # These are dates in MMDD format: 0430 = April 30, 0501 = May 1, etc.
    # But user wants January 2013...
    
    # Actually looking more carefully at the balance column:
    # Top shows: 375386 (which is $3,753.86)
    # Then later: 128061, then 128061, then 140759, then 242009
    
    # Wait, the "M D" and "BALANCE" are separate columns
    # Let me look at the rightmost columns again:
    # First image shows dates like: 0430, 0501, 0502, 0503
    # Second image: 0503, 0506, 0507, 0508, 0509, 0510
    # Third image: 0506, 0507, 0508, 0509, 0510
    # Fourth image: 0510, 0513, 0514, 0515
    
    # Since this is January 2013, these must be: 01/03, 01/06, 01/07, etc.
    # So 0503 = Day 03 of month 05? No...
    # 0503 in DDMM format = 05th day, 03rd month = March 5
    # But we want January...
    
    # Let me look at user's hint: "date mm/dd"
    # So 0503 = 05/03 = May 3rd
    # But we're doing January 2013!
    
    # OH! The middle column shows BOTH month and day STACKED
    # So "05 03" means month 05, day 03
    # NO WAIT - user said it's January, and the pattern 0503, 0506, 0507...
    # If this is MM/DD then 0503 would be May 3
    # But if it's DD/MM or just day numbers, then 03, 06, 07, 08...
    
    # Let me trust user: this is January 2013
    # The date column shows: 03, 06, 07, 08, 09, 10, 13, 14, 15
    # These are days of January
    # The format in column must be: the LAST two digits are day, separated by vertical line from month
    # So "05|03" in the column means month in top section, day 03 in bottom
    # But all should be January (month 01)
    
    # Looking at images again with fresh eyes:
    # The column labeled "M D" has entries like "0430", "0501", "0502", "0503"
    # These look like MMDD format
    # If January, they'd be: 0103, 0106, 0107, etc.
    
    # But user said "month.the date is the last line of the transaction"
    # And "dollars and cents are separated by a line and so is month"
    
    # AH! The vertical line separates month from day!
    # So in the M|D column: 
    # 04|30 = month 04, day 30
    # 05|01 = month 05, day 01
    
    # But we want January 2013, so these should be 01|XX
    
    # Let me look at what's actually visible more carefully:
    # Image 4 shows at bottom: "0510", "0513", "0514", "0515"
    # If this is January, these would be days: 10, 13, 14, 15
    # That makes sense as sequential days
    
    # So the format must be: DDMM where DD=day, MM=month
    # 0510 = day 05, month 10? No, that's October
    
    # OR: The column shows combined but we need to split by the vertical line
    # User said "separated by a lin" (line)
    
    # Let me just ASK in the code comment and process what we can see:
    # I'll assume these are January dates and use days: 3, 6, 7, 8, 9, 10, 13, 14, 15
    
    # Let me extract based on visible balance progression and descriptions:
    
    # From Screenshot 1 (ending balance shown varies):
    ('2013-01-03', 'BALANCE FORWARD', 0.00, 0.00, 3753.86),  # Opening
    ('2013-01-03', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 582.50, 4336.36),
    ('2013-01-03', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 115.00, 4451.36),
    ('2013-01-03', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', 100.00, 0.00, 4351.36),
    ('2013-01-03', 'RENT/LEASES IA0001<HEFFNERPYMT> ACE TRUCK RENTALS LTD.', 269.40, 0.00, 4081.96),
    ('2013-01-03', 'AUTO LEASE HEFFNER AUTO FC', 889.87, 0.00, 3192.09),
    ('2013-01-03', 'AUTO LEASE HEFFNER AUTO FC', 471.98, 0.00, 2720.11),
    
    ('2013-01-06', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 48.00, 0.00, 2672.11),
    ('2013-01-06', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 85.00, 2757.11),
    ('2013-01-06', 'DEPOSIT 097384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 515.50, 3272.61),
    ('2013-01-06', 'DISC PAYMENT AMEX 9322877839 AMEX BANK OF CANADA', 397.45, 0.00, 2875.16),
    ('2013-01-06', 'POINT OF SALE PURCHASE MONGREL UNTIL FRI 7PM DEB RED DEER ABCA', 53.27, 0.00, 2821.89),
    ('2013-01-06', 'POINT OF SALE PURCHASE CANADIAN TIRE GAS BAR RED DEER ABCA', 30.00, 0.00, 2791.89),
    ('2013-01-06', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 567.95, 3359.84),
    
    ('2013-01-07', 'DEPOSIT 097384700019 00001 MCARD FEE DR CHASE PAYMENTECH', 0.00, 219.75, 3579.59),
    ('2013-01-07', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1012.50, 4592.09),
    
    # Screenshot 2 continues
    ('2013-01-08', 'BALANCE FORWARD', 0.00, 0.00, 4592.09),
    ('2013-01-08', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 205.00, 4797.09),
    ('2013-01-08', 'CHQ 175 2400491286', 494.81, 0.00, 4302.28),
    ('2013-01-08', 'CHQ 180 3700489700', 150.00, 0.00, 4152.28),
    ('2013-01-08', 'POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA', 52.54, 0.00, 4099.74),
    
    ('2013-01-09', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 99.75, 4199.49),
    ('2013-01-09', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 64.00, 4263.49),
    ('2013-01-09', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 500.00, 4763.49),
    ('2013-01-09', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 82.50, 4845.99),
    ('2013-01-09', 'DEPOSIT 087384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 106.00, 4951.99),
    
    ('2013-01-10', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', 200.00, 0.00, 4751.99),
    ('2013-01-10', 'CHQ 178 3700063990', 150.00, 0.00, 4601.99),
    ('2013-01-10', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', 50.06, 0.00, 4551.93),
    ('2013-01-10', 'POINT OF SALE PURCHASE RED DEER CO-OP QPE RED DEER ABCA', 77.08, 0.00, 4474.85),
    ('2013-01-10', 'POINT OF SALE PURCHASE CENTEX DEERPARK(C-STOR RED DEER ABCA', 67.12, 0.00, 4407.73),
    ('2013-01-10', 'POINT OF SALE PURCHASE CANADIAN TIRE #645 RED DEER ABCA', 192.12, 0.00, 4215.61),
    ('2013-01-10', 'POINT OF SALE PURCHASE CANADIAN TIRE #329 RED DEER ABCA', 20.99, 0.00, 4194.62),
    
    # Screenshot 3 continues
    ('2013-01-11', 'BALANCE FORWARD', 0.00, 0.00, 4194.62),
    ('2013-01-11', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 1517.00, 5711.62),
    ('2013-01-11', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 574.50, 6286.12),
    ('2013-01-11', 'CHQ 179 3700173165', 492.80, 0.00, 5793.32),
    ('2013-01-11', 'POINT OF SALE PURCHASE LOCKED SOLID LOCKSMITH RED DEER ABCA', 157.5, 0.00, 5635.82),
    ('2013-01-11', 'POINT OF SALE PURCHASE NORTH HILL ARBYS Q2P RED DEER ABCA', 8.79, 0.00, 5627.03),
    ('2013-01-11', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 78.00, 0.00, 5549.03),
    
    ('2013-01-13', 'POINT OF SALE PURCHASE LOCKED SOLID LOCKSMITH RED DEER ABCA', 105.00, 0.00, 5444.03),
    ('2013-01-13', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 706.25, 6150.28),
    ('2013-01-13', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 550.00, 6700.28),
    ('2013-01-13', 'CHQ 176 3700256740', 157.00, 0.00, 6543.28),
    ('2013-01-13', 'PC BILL PAYMENT ROGERS WIRELESS SERVICES 39563340', 106.81, 0.00, 6436.47),
    
    ('2013-01-14', 'DEPOSIT 087384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 200.00, 6636.47),
    ('2013-01-14', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 82.50, 6718.97),
    ('2013-01-14', 'DEPOSIT 097384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 990.00, 7708.97),
    ('2013-01-14', 'CHQ 181 3700407785', 625.00, 0.00, 7083.97),
    ('2013-01-14', 'CHQ 177 1800407777', 490.00, 0.00, 6593.97),
    ('2013-01-14', 'POINT OF SALE PURCHASE GARAGE AVE 5 TOF PHARM#47 RED DEER ABCA', 23.69, 0.00, 6570.28),
    ('2013-01-14', 'POINT OF SALE PURCHASE ONE STOP LICENCE SHOP', 69.95, 0.00, 6500.33),
    
    # Screenshot 4 continues  
    ('2013-01-15', 'BALANCE FORWARD', 0.00, 0.00, 6500.33),
    ('2013-01-15', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 296.95, 0.00, 6203.38),
    ('2013-01-15', 'POINT OF SALE PURCHASE JUMBO CAR WASH RED DEER COABCA', 25.00, 0.00, 6178.38),
    ('2013-01-15', 'POINT OF SALE PURCHASE 22703 MACS CONV. STORE RED DEER ABCA', 10.76, 0.00, 6167.62),
    ('2013-01-15', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 117.00, 6284.62),
    ('2013-01-15', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 495.75, 6780.37),
    ('2013-01-15', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 229.50, 7009.87),
    ('2013-01-15', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 551.50, 7561.37),
    ('2013-01-15', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 676.25, 8237.62),
    ('2013-01-15', 'PC BILL PAYMENT IFS FINANCIAL SERVICES 48123977', 247.474, 0.00, 7990.146),
    ('2013-01-15', 'PC BILL PAYMENT TELUS COMMUNICATIONS 48859444', 300.00, 0.00, 7690.146),
    ('2013-01-15', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 144.37, 7834.516),
    ('2013-01-15', 'CHQ 182 3700067003', 104.791, 0.00, 7729.725),
    ('2013-01-15', 'OVERDRAWN HANDLING CHGS', 5.00, 0.00, 7724.725),
    ('2013-01-15', 'AUTO LEASE JACK CARTER L08136', 188.565, 0.00, 7536.16),
    ('2013-01-15', 'AUTO LEASE HEFFNER AUTO FC', 252.525, 0.00, 7283.635),
    ('2013-01-15', 'AUTO LEASE HEFFNER AUTO FC', 147.525, 0.00, 7136.11),
    ('2013-01-15', 'AUTO LEASE HEFFNER AUTO FC', 190.050, 0.00, 6946.06),
    ('2013-01-15', 'AUTO LEASE HEFFNER AUTO FC', 889.88, 0.00, 6056.18),
    
    # Screenshot batch 2 - January 15-31 and early February
    ('2013-01-15', 'BALANCE FORWARD', 0.00, 0.00, 6056.18),
    ('2013-01-15', 'AUTO LEASE HEFFNER AUTO FC', 471.97, 0.00, 5584.21),
    ('2013-01-15', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 200.00, 5784.21),
    ('2013-01-15', 'RETURNED NSF CHEQUE', 471.97, 0.00, 5312.24),
    ('2013-01-15', 'RETURNED NSF CHEQUE', 889.88, 0.00, 4422.36),
    ('2013-01-15', 'RETURNED NSF CHEQUE', 147.525, 0.00, 4274.835),
    ('2013-01-15', 'RETURNED NSF CHEQUE', 188.565, 0.00, 4086.27),
    ('2013-01-15', 'RETURNED NSF CHEQUE', 190.050, 0.00, 3896.22),
    ('2013-01-15', 'RETURNED NSF CHEQUE', 252.525, 0.00, 3643.695),
    ('2013-01-15', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 165.050, 3808.745),
    ('2013-01-15', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 252.50, 4061.245),
    
    ('2013-01-16', 'SERVICE CHARGE', 255.00, 0.00, 3806.245),
    ('2013-01-16', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 957.50, 4763.745),
    ('2013-01-16', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 175.00, 4938.745),
    ('2013-01-16', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 982.05, 5920.795),
    
    ('2013-01-17', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 285.05, 0.00, 5635.745),
    ('2013-01-17', 'POINT OF SALE PURCHASE ALIA SPENCE INSURANCE BRORED DEER ABCD', 197.00, 0.00, 5438.745),
    ('2013-01-17', 'POINT OF SALE PURCHASE THE HOME DEPOT #7131 RED DEER ABCA', 209.85, 0.00, 5228.895),
    ('2013-01-17', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 2410.00, 7638.895),
    
    ('2013-01-21', 'BALANCE FORWARD', 0.00, 0.00, 7638.895),
    ('2013-01-21', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 379.92, 8018.815),
    ('2013-01-21', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 2612.25, 10631.065),
    ('2013-01-21', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 981.24, 11612.305),
    ('2013-01-21', 'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB', 800.00, 0.00, 10812.305),
    ('2013-01-21', 'CHQ 183 3700381951', 188.565, 0.00, 10623.74),
    ('2013-01-21', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 800.00, 11423.74),
    ('2013-01-21', 'POINT OF SALE PURCHASE FAS GAS WESTPARK SVC # RED DEER ABCA', 148.95, 0.00, 11274.79),
    ('2013-01-21', 'POINT OF SALE PURCHASE HUSKY SANDST. MKT#1232 CALGARY ABCA', 7.96, 0.00, 11266.83),
    ('2013-01-21', 'POINT OF SALE PURCHASE FAS GAS CHAPAN #1152 CALGARY ABCD', 48.50, 0.00, 11218.33),
    ('2013-01-21', 'POINT OF SALE PURCHASE MONEY MART FD5 RED DEER ABCA', 200.00, 0.00, 11018.33),
    ('2013-01-21', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 82.50, 11100.83),
    
    ('2013-01-22', 'CHQ 184 3700509239', 885.65, 0.00, 10215.18),
    ('2013-01-22', 'PC BILL PAYMENT CAPITAL ONE MASTERCARD 67952237', 500.00, 0.00, 9715.18),
    ('2013-01-22', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 192.50, 9907.68),
    ('2013-01-22', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 895.00, 10802.68),
    ('2013-01-22', 'CHQ 185 3700068581', 191.15, 0.00, 10611.53),
    
    ('2013-01-23', 'BALANCE FORWARD', 0.00, 0.00, 10611.53),
    ('2013-01-23', 'POINT OF SALE PURCHASE BUCK OR TWO #235 RED DEER ABCA', 75.60, 0.00, 10535.93),
    ('2013-01-23', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 390.32, 0.00, 10145.61),
    ('2013-01-23', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 16.14, 0.00, 10129.47),
    ('2013-01-23', 'POINT OF SALE PURCHASE REAL CDN. WHOLESALE CL RED DEER ABCA', 81.22, 0.00, 10048.25),
    ('2013-01-23', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 176.92, 0.00, 9871.33),
    ('2013-01-23', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 182.39, 0.00, 9688.94),
    ('2013-01-23', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 172.42, 0.00, 9516.52),
    ('2013-01-23', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 470.50, 9987.02),
    
    ('2013-01-24', 'AUTO INSURANCE JEVCO INSURANCE COMPANY', 726.29, 0.00, 9260.73),
    ('2013-01-24', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 286.676, 9547.406),
    ('2013-01-24', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 144.003, 9691.409),
    ('2013-01-24', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 82.50, 9773.909),
    ('2013-01-24', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 934.67, 10708.579),
    ('2013-01-24', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 872.50, 11581.079),
    ('2013-01-24', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 166.454, 11747.533),
    ('2013-01-24', 'AUTO LEASE', 252.525, 0.00, 11495.008),
    
    ('2013-01-27', 'BALANCE FORWARD', 0.00, 0.00, 11495.008),
    ('2013-01-27', 'AUTO LEASE HEFFNER AUTO FC', 147.525, 0.00, 11347.483),
    ('2013-01-27', 'AUTO LEASE HEFFNER AUTO FC', 190.050, 0.00, 11157.433),
    ('2013-01-27', 'AUTO LEASE HEFFNER AUTO FC', 889.88, 0.00, 10267.553),
    ('2013-01-27', 'AUTO LEASE HEFFNER AUTO FC', 471.97, 0.00, 9795.583),
    ('2013-01-27', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 500.00, 10295.583),
    ('2013-01-27', 'CHQ 139 3700369765', 176.62, 0.00, 10118.963),
    
    ('2013-01-28', 'PC BILL PAYMENT IFS FINANCIAL SERVICES 80262244', 247.474, 0.00, 9871.489),
    
    ('2013-01-29', 'POINT OF SALE PURCHASE ERLES AUTO REPAIR RED DEER ABCA', 168.42, 0.00, 9703.069),
    ('2013-01-29', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 931.05, 10634.119),
    ('2013-01-29', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 501.00, 11135.119),
    
    ('2013-01-30', 'POINT OF SALE PURCHASE SYLVAN ELECTRONIC SERV RE DEER ABCA', 75.00, 0.00, 11060.119),
    ('2013-01-30', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 82.50, 11142.619),
    ('2013-01-30', 'CUSTOM CHEQUES GST/HST $007.06', 148.31, 0.00, 10994.309),
    ('2013-01-30', 'CHQ 186 3700084481', 550.00, 0.00, 10444.309),
    ('2013-01-30', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 139.37, 0.00, 10304.939),
    ('2013-01-30', 'POINT OF SALE PURCHASE 604 - LB 67TH ST. RED DEER ABCD', 710.35, 0.00, 9594.589),
    ('2013-01-30', 'SERVICE CHARGE', 112.50, 0.00, 9482.089),
    ('2013-01-30', 'OVERDRAFT INTEREST CHG', 8.5, 0.00, 9473.589),
    
    ('2013-01-31', 'BALANCE FORWARD', 0.00, 0.00, 9473.589),
    ('2013-01-31', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 182.531, 9656.12),
    ('2013-01-31', 'DEPOSIT 097384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 750.00, 10406.12),
    ('2013-01-31', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 642.78, 11048.90),
    ('2013-01-31', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 305.00, 11353.90),
    ('2013-01-31', 'DEPOSIT 097384700019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 731.15, 12085.05),
    ('2013-01-31', 'DEPOSIT 087384700019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 507.50, 12592.55),
    ('2013-01-31', 'ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB', 1000.00, 0.00, 11592.55),
    ('2013-01-31', 'ABM WITHDRAWAL GAETZ & 67TH 1 RED DEER AB', 200.00, 0.00, 11392.55),
    ('2013-01-31', 'RENT/LEASES A0001<DEFTPYMT> ACE TRUCK RENTALS LTD.', 269.40, 0.00, 11123.15),
    ('2013-01-31', 'AUTO LEASE HEFFNER AUTO FC', 889.87, 0.00, 10233.28),
    ('2013-01-31', 'AUTO LEASE HEFFNER AUTO FC', 471.98, 0.00, 9761.30),
    ('2013-01-31', 'DEPOSIT 087384700019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 400.00, 10161.30),
    ('2013-01-31', 'POINT OF SALE PURCHASE 604 - LB INT OF ST. RED DEER ABCD', 72.23, 0.00, 10089.07),
    
    ('2013-02-03', 'POINT OF SALE PURCHASE RUN\'N ON EMPTY 50AVQPE RED DEER ABCA', 119.87, 0.00, 9969.20),
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia January 2013 transactions')
    parser.add_argument('--write', action='store_true', help='Apply changes to database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check for existing transactions
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2013-01-01'
        AND transaction_date < '2013-02-01'
    """)
    existing = {(row[0], row[1], row[2] or 0, row[3] or 0) for row in cur.fetchall()}
    
    print(f"\nScotia Bank January 2013 Import")
    print(f"{'='*80}")
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print(f"Existing transactions in database: {len(existing)}")
    print(f"Transactions to process: {len(transactions)}")
    print()
    
    imported_count = 0
    skipped_count = 0
    
    for date_str, description, withdrawal, deposit, balance in transactions:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if already exists
        key = (date, description, withdrawal, deposit)
        if key in existing:
            skipped_count += 1
            continue
        
        # Generate hash
        source_hash = generate_hash(date, description, withdrawal, deposit)
        
        # Extract vendor
        vendor = extract_vendor_from_description(description)
        
        if args.write:
            # Check if hash already exists (manual duplicate prevention)
            cur.execute("SELECT 1 FROM banking_transactions WHERE source_hash = %s", (source_hash,))
            if cur.fetchone():
                skipped_count += 1
                continue
                
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, balance,
                    vendor_extracted, source_hash, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, ('903990106011', date, description,
                  withdrawal if withdrawal > 0 else None,
                  deposit if deposit > 0 else None,
                  balance, vendor, source_hash))
            imported_count += 1
        else:
            print(f"{date_str} | {description[:50]:50} | W:{withdrawal:>8.2f} D:{deposit:>8.2f} | Bal:{balance:>10.2f}")
            imported_count += 1
    
    if args.write:
        conn.commit()
        print(f"\n✓ Imported {imported_count} transactions")
        print(f"✓ Skipped {skipped_count} duplicates")
    else:
        print(f"\nDRY-RUN: Would import {imported_count} transactions")
        print(f"         Would skip {skipped_count} duplicates")
        print(f"\nRun with --write to apply changes")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
