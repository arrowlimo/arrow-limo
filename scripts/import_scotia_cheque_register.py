"""
Import Scotia Bank cheque register data (checks 1-117)
- Update cheque_register table
- Match to banking_transactions via TX ID
- Create receipts for checks without them
- Assign GL codes based on payee patterns
- Handle NSF, void, and special cases
"""

import os
import psycopg2
from datetime import datetime
import re

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# GL Code mapping based on payee patterns
GL_CODES = {
    'payroll': '5210',  # Driver/Employee wages
    'vehicle_lease': '5150',  # Heffner Auto lease payments
    'vehicle_maintenance': '5120',  # Parrs Auto, Earls Auto, Kirks Tire
    'rent': '5410',  # Fibrenew rent
    'utilities': '5420',  # Fibrenew utilities, Telus
    'insurance': '5310',  # Tredd Mayfair Insurance
    'licensing': '5330',  # AGLC, licenses
    'source_deductions': '2310',  # Revenue Canada payroll taxes
    'advertising': '5510',  # Action Pages, bridal shows
    'donations': '5850',  # Word of Life donation
    'bank_transfer': '1010',  # Arrow Limousine transfers
    'unknown': '5850',  # Generic expense
}

# Cheque data from user (hand-written register with possible misspellings)
CHEQUE_DATA = [
    (1, '2012-07-09', 1870.14, 'CHQ 1 ANGEL ESCOBAR', 'ANGEL ESCOBAR', 69078),
    (2, '2012-07-18', 489.20, 'CHQ 2 MID ALTA (L8 INSPECTION', 'MID ALTA', 69118),
    (3, '2012-07-13', 2000.00, 'CHQ 3 PARRS AUTOMOTIVE', 'PARRS AUTOMOTIVE', 69093),
    (4, '2012-07-13', 840.95, 'CHQ 4 EARLS AUTO', 'EARLS AUTO', 69092),
    (5, '2012-09-06', 2236.92, 'CHQ 5 ACTION PAGES', 'ACTION PAGES', 69310),
    (6, '2012-07-17', 400.00, 'CHQ 6 DALE MENARD', 'DALE MENARD', 69109),
    (7, '2012-07-17', 100.00, 'CHQ 7 DALE MENARD', 'DALE MENARD', 69108),
    (8, '2012-07-19', 2000.00, 'CHQ 8 ARROW LIMOUSINE( TRANSFER FOR CAR PMNTS)', 'ARROW LIMOUSINE', 69122),
    (9, '2012-07-23', 1885.65, 'CHQ 9 JACK CARTER', 'JACK CARTER', 69145),
    (10, None, 0.00, 'CHQ 10 NOT ISSUES', 'NOT ISSUED', None),  # Not issued
    (11, '2012-07-23', 3000.00, 'CHQ 11 KIRKS TIRE', 'KIRKS TIRE', 69142),
    (12, '2012-08-01', 3071.04, 'CHQ 12 PAUL MANSELL', 'PAUL MANSELL', 69178),
    (13, '2012-08-10', 3086.58, 'CHQ 13 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 69209),
    (14, '2012-08-07', 599.06, 'CHQ 14 ZAC KELLER', 'ZAC KELLER', 69193),
    (15, '2012-08-01', 1511.17, 'CHQ 15 DALE MENARD', 'DALE MENARD', 69177),
    (16, '2012-08-08', 2088.59, 'CHQ 16 DOUG REDMOND', 'DOUG REDMOND', 69198),
    (17, '2012-08-13', 1908.11, 'CHQ 17 MICHAEL RICHARD', 'MICHAEL RICHARD', 69215),
    (18, '2012-08-09', 1207.50, 'CHQ 18 FIBRENEW', 'FIBRENEW', 69203),
    (19, '2012-08-10', 827.48, 'CHQ 19 ANGEL ESCOBAR', 'ANGEL ESCOBAR', 69207),
    (20, '2012-08-10', 155.00, 'CHQ 20 ANGEL ESCOBAR', 'ANGEL ESCOBAR', 69208),
    (21, '2012-08-10', 1000.00, 'CHQ 21 PARRS AUTOMOTIVE', 'PARRS AUTOMOTIVE', 69205),
    (22, '2012-09-25', 1475.25, 'CHQ 22 HEFFNER AUTO (L-9)', 'HEFFNER AUTO', 69370),  # Corrected: was WITH THIS RING - actually Heffner
    (23, '2012-09-25', 1475.25, 'CHQ 23 HEFFNER AUTO (L-9)', 'HEFFNER AUTO', 69370),
    (24, '2013-04-29', 1475.25, 'CHQ 24 HEFFNER AUTO (L-9)', 'HEFFNER AUTO', 78251),
    (25, None, 1475.25, 'CHQ 25 HEFFNER AUTO (L-9)', 'HEFFNER AUTO', None),
    (26, None, 1475.25, 'CHQ 26 HEFFNER AUTO (L-9)', 'HEFFNER AUTO', None),
    (27, None, 1475.25, 'CHQ 27  HEFFNER AUTO (L-9)', 'HEFFNER AUTO', None),
    (28, None, 1475.25, 'CHQ 28 HEFFNER AUTO (L-9)', 'HEFFNER AUTO', None),
    (29, '2012-09-27', 2525.25, 'CHQ 29 HEFFNER AUTO (L-10)', 'HEFFNER AUTO', 69380),
    (30, '2012-10-30', 2525.25, 'CHQ 30 HEFFNER AUTO (L-10) NSF', 'HEFFNER AUTO', 69498),
    (31, '2013-03-20', 2525.25, 'CHQ 31 HEFFNER AUTO (L-10)', 'HEFFNER AUTO', 78038),
    (32, '2012-12-10', 2525.25, 'CHQ 32 HEFFNER AUTO (L-10)', 'HEFFNER AUTO', 69671),
    (33, None, 2525.25, 'CHQ 33 HEFFNER AUTO (L-10)', 'HEFFNER AUTO', None),
    (34, '2013-07-22', 2525.25, 'CHQ 34 HEFFNER AUTO (L-10)', 'HEFFNER AUTO', 78671),
    (35, '2012-09-25', 1900.50, 'CHQ 35 HEFFNER AUTO (L-11)', 'HEFFNER AUTO', 69371),
    (36, '2012-10-30', 1900.50, 'CHQ 36 HEFFNER AUTO (L-11) NSF', 'HEFFNER AUTO', 69501),
    (37, '2013-01-21', 1900.50, 'CHQ 37 HEFFNER AUTO (L-11)', 'HEFFNER AUTO', 77769),
    (38, '2013-03-11', 1900.50, 'CHQ 38 HEFFNER AUTO (L-11)', 'HEFFNER AUTO', 77982),
    (39, '2012-12-24', 1900.50, 'CHQ 39 HEFFNER AUTO (L-11)', 'HEFFNER AUTO', 69734),
    (40, '2013-03-22', 1900.50, 'CHQ 40 HEFFNER AUTO (L-11)', 'HEFFNER AUTO', 78047),
    (41, None, 3993.79, 'CHQ 41 REVENUE CANADA (SOURCE DEDUCTIONS)', 'REVENUE CANADA', None),
    (42, '2012-08-17', 500.00, 'CHQ 42 DALE MENARD', 'DALE MENARD', 69231),
    (43, '2012-08-23', 1900.50, 'CHQ 43 HEFFNER AUTO (L-11)', 'HEFFNER AUTO', 69253),
    (44, '2012-08-24', 2000.00, 'CHQ 44 ARROW LIMOUSINE (TRANSFER FOR INSURANCE)', 'ARROW LIMOUSINE', 69271),
    (45, '2012-09-04', 1295.42, 'CHQ 45 DALE MENARD', 'DALE MENARD', 69300),
    (46, '2012-09-04', 1848.93, 'CHQ 46 PAUL MANSELL', 'PAUL MANSELL', 69301),
    (47, '2012-09-10', 600.00, 'CHQ 47 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 69317),
    (48, '2012-09-17', 2101.00, 'CHQ 48 DOUG REDMOND', 'DOUG REDMOND', 69338),
    (49, '2012-09-11', 1314.52, 'CHQ 49 ANGEL ESCOBAR', 'ANGEL ESCOBAR', 69321),
    (50, '2012-10-01', 1163.75, 'CHQ 50 FIBRENEW', 'FIBRENEW', 69396),
    (51, '2012-10-01', 170.43, 'CHQ 51 FIBRENEW (UTILITIES)', 'FIBRENEW', 69395),
    (52, '2012-09-18', 2998.78, 'CHQ 52 REVENUE CANADA (SOURCE DEDUCTIONS)', 'REVENUE CANADA', 69346),
    (53, '2012-09-21', 1925.00, 'CHQ 53 VIC PFIEFER (HEFFNER AUTO) L-15', 'VIC PFIEFER', 69358),
    (54, '2012-09-17', 3007.97, 'CHQ 54 TELUS', 'TELUS', 69340),
    (55, '2012-09-18', 166.19, 'CHQ 55 TELUS', 'TELUS', 69347),
    (56, '2012-09-24', 500.00, 'CHQ 56 MIKE WOODROW', 'MIKE WOODROW', 69367),
    (57, '2012-10-01', 287.11, 'CHQ 57 CHANTEL THOMAS', 'CHANTEL THOMAS', 69398),
    (58, '2012-09-27', 1044.52, 'CHQ 58 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 69378),
    (59, '2012-10-01', 200.00, 'CHQ 59 AGLC (LICENSE RENEWAL)', 'AGLC', 69397),
    (60, '2012-09-28', 908.15, 'CHQ 60 (UNKNOWN)', 'UNKNOWN', 69385),
    (61, '2012-10-01', 2200.00, 'CHQ 61 PAUL RICHARD (PAYROLL)', 'PAUL RICHARD', 69394),
    (62, '2012-10-02', 95.72, 'CHQ 62 JESSE GORDON', 'JESSE GORDON', 69408),
    (63, '2012-10-02', 505.01, 'CHQ 63 JESSY GORDON', 'JESSE GORDON', 69407),  # Misspelling: JESSY -> JESSE
    (64, '2012-10-03', 650.00, 'CHQ 64 PAUL MANSELL', 'PAUL MANSELL', 69411),
    (65, '2012-10-09', 1088.31, 'CHQ 65 DUSTEN TOWNSEND', 'DUSTAN TOWNSEND', 69426),  # Misspelling: DUSTEN -> DUSTAN
    (66, '2012-10-15', 506.35, 'CHQ 66 CHANTEL THOMAS', 'CHANTEL THOMAS', 69447),
    (67, '2012-10-05', 473.05, 'CHQ 67 DALE MENARD', 'DALE MENARD', 69418),
    (68, '2012-10-09', 1578.95, 'CHQ 68 PAUL MANSELL', 'PAUL MANSELL', 69428),
    (69, '2012-10-19', 700.00, 'CHQ 69 PAUL MANSELL', 'PAUL MANSELL', 69472),
    (70, '2012-10-12', 206.16, 'CHQ 70 LOGAN MOSINSKY', 'LOGAN MOSINSKY', 69440),
    (71, '2012-10-11', 1820.98, 'CHQ 71 DOUG REDMOND', 'DOUG REDMOND', 69434),
    (72, '2012-10-12', 1891.81, 'CHQ 72 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 69441),
    (73, '2012-10-11', 871.99, 'CHQ 73 ANGEL ESCOBAR', 'ANGEL ESCOBAR', 69435),
    (74, '2012-10-24', 2201.83, 'CHQ 74 MICHAEL RICHARD', 'MICHAEL RICHARD', 69488),
    (75, '2012-10-12', 2000.00, 'CHQ 75 PARRS AUTO', 'PARRS AUTOMOTIVE', 69442),
    (76, '2012-10-16', 1500.00, 'CHQ 76 PARRS AUTO', 'PARRS AUTOMOTIVE', 69457),
    (77, '2012-10-22', 1500.00, 'CHQ 77 MIKE WOODROW', 'MIKE WOODROW', 69481),
    (78, '2012-10-24', 1445.62, 'CHQ 78 FIBRENEW', 'FIBRENEW', 69487),
    (79, '2012-10-29', 419.92, 'CHQ 79 ANGEL ESCOBAR', 'ANGEL ESCOBAR', 69784),
    (80, '2012-10-26', 1531.58, 'CHQ 80 HEFFNER AUTO (L-4 DOWNPAYMENT)', 'HEFFNER AUTO', 69780),
    (81, '2012-11-07', 500.00, 'CHQ 81 PAUL MANSELL', 'PAUL MANSELL', 69529),
    (82, '2012-11-13', 880.00, 'CHQ 82 DUSTIN TOWNSEND', 'DUSTAN TOWNSEND', 69791),  # Misspelling: DUSTIN -> DUSTAN
    (83, '2012-11-13', 276.33, 'CHQ 83 DUSTIN TOWNSEND', 'DUSTAN TOWNSEND', 69792),  # Misspelling: DUSTIN -> DUSTAN
    (84, '2012-11-14', 600.00, 'CHQ 84 PAUL MANSELL', 'PAUL MANSELL', 69549),
    (85, '2012-11-08', 484.92, 'CHQ 85 KEVIN BOULLEY', 'KEVIN BOULLEY', 69535),
    (86, '2013-06-26', 1666.11, 'CHQ 86 MICHAEL RICHARD', 'MICHAEL RICHARD', 78525),
    (87, None, 1500.00, 'CHQ 87 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', None),
    (88, '2012-11-22', 1500.00, 'CHQ 88 DOUG REDMOND', 'DOUG REDMOND', 69573),
    (89, '2012-12-17', 324.86, 'CHQ 89 DALE MENARD', 'DALE MENARD', 69706),
    (90, '2012-11-13', 707.60, 'CHQ 90 JESSE GORDON', 'JESSE GORDON', 69790),
    (91, '2012-11-14', 88.35, 'CHQ 91 LOGAN MASINSKY', 'LOGAN MOSINSKY', 69548),  # Misspelling: MASINSKY -> MOSINSKY
    (92, None, 613.00, 'CHQ 92 TREDD MAYFAIR INSURANCE (VOID)', 'TREDD MAYFAIR', None),  # VOID
    (93, None, 200.00, 'CHQ 93 WORD OF LIFE (DONATION) - VOID', 'WORD OF LIFE', None),  # VOID - no banking TX found
    (94, None, 1885.65, 'CHQ 94 JACK CARTER (L-8)', 'JACK CARTER', None),
    (95, '2012-12-06', 1885.65, 'CHQ 95 JACK CARTER (L-8)', 'JACK CARTER', 69654),
    (96, '2012-12-06', 658.06, 'CHQ 96 PAUL MANSELL (PAID BY CIBC)', 'PAUL MANSELL', 69655),
    (97, '2012-12-06', 100.00, 'CHQ 97 WELCOME WAGON', 'WELCOME WAGON', 69646),
    (98, '2012-12-19', 200.00, 'CHQ 98 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 69727),
    (99, '2012-11-29', 613.00, 'CHQ 99 TREDD MAYFAIR', 'TREDD MAYFAIR', 69608),
    (100, '2013-03-21', 300.00, 'CHQ 100 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 78043),
    (101, '2012-12-03', 2000.00, 'CHQ 101 PARRS AUTOMOTIVE', 'PARRS AUTOMOTIVE', 69618),
    (102, '2012-12-06', 2200.00, 'CHQ 102 PAUL RICHARD (PAYROLL)', 'PAUL RICHARD', 69653),
    (103, '2012-12-04', 1950.00, 'CHQ 103 PAUL MANSELL', 'PAUL MANSELL', 69639),
    (104, '2012-12-03', 1000.00, 'CHQ 104 KEVIN BOULLEY', 'KEVIN BOULLEY', 69620),
    (105, '2012-12-04', 1567.52, 'CHQ 105 CHANTAL THOMAS', 'CHANTEL THOMAS', 69636),  # Misspelling: CHANTAL -> CHANTEL
    (106, '2012-12-06', 708.93, 'CHQ 106 JESSE GORDON', 'JESSE GORDON', 69647),
    (107, '2012-12-04', 139.81, 'CHQ 107 DUSTAN TOWNSEND PAYROLL PAID TO KEVIN KOSIK FOR A GUITAR', 'KEVIN KOSIK', 69637),  # Paid to lien holder
    (108, None, 564.92, 'CHQ 108 SHAWN CALLIN', 'SHAWN CALLIN', None),
    (109, '2012-12-12', 2297.73, 'CHQ 109 DOUG REDMOND', 'DOUG REDMOND', 69684),
    (110, '2012-12-11', 2120.72, 'CHQ 110 JEANNIE SHILLINGTON', 'JEANNIE SHILLINGTON', 69680),
    (111, '2012-12-10', 55.31, 'CHQ 111 KEVIN BOULLEY', 'KEVIN BOULLEY', 69670),
    (112, '2012-12-12', 782.57, 'CHQ 112 PAUL MANSELL', 'PAUL MANSELL', 69686),
    (113, '2012-12-10', 866.56, 'CHQ 113 MIKE RICHARD', 'MICHAEL RICHARD', 69673),  # Misspelling: MIKE -> MICHAEL
    (114, '2012-12-13', 210.00, 'CHQ 114 KEVIN BOULLEY', 'KEVIN BOULLEY', 69690),
    (115, '2012-12-20', 3281.12, 'CHQ 115 IFS', 'IFS', 69732),
    (116, '2013-01-14', 3281.13, 'CHQ 116 IFS', 'IFS', 77731),
    (117, None, 841.11, 'CHQ 117 MIKE RICHARD', 'MICHAEL RICHARD', None),  # Misspelling: MIKE -> MICHAEL
]

def assign_gl_code(payee, description):
    """Assign GL code based on payee and description patterns"""
    payee_upper = payee.upper()
    desc_upper = description.upper()
    
    # Payroll employees
    if any(name in payee_upper for name in ['ANGEL ESCOBAR', 'PAUL MANSELL', 'JEANNIE SHILLINGTON', 
                                              'DOUG REDMOND', 'DALE MENARD', 'MICHAEL RICHARD',
                                              'JACK CARTER', 'ZAC KELLER', 'JESSE GORDON',
                                              'DUSTAN TOWNSEND', 'CHANTEL THOMAS', 'LOGAN MOSINSKY',
                                              'MIKE WOODROW', 'KEVIN BOULLEY', 'SHAWN CALLIN']):
        if 'PAYROLL' in desc_upper or 'LIEN' not in desc_upper:
            return GL_CODES['payroll']
    
    # Vehicle lease
    if 'HEFFNER' in payee_upper or 'VIC PFIEFER' in payee_upper:
        return GL_CODES['vehicle_lease']
    
    # Vehicle maintenance
    if any(vendor in payee_upper for vendor in ['PARRS', 'EARLS AUTO', 'KIRKS TIRE', 'MID ALTA']):
        return GL_CODES['vehicle_maintenance']
    
    # Rent
    if 'FIBRENEW' in payee_upper and 'UTILIT' not in desc_upper:
        return GL_CODES['rent']
    
    # Utilities
    if 'FIBRENEW' in payee_upper and 'UTILIT' in desc_upper:
        return GL_CODES['utilities']
    if 'TELUS' in payee_upper:
        return GL_CODES['utilities']
    
    # Insurance
    if 'TREDD MAYFAIR' in payee_upper or 'INSURANCE' in desc_upper:
        return GL_CODES['insurance']
    
    # Licensing
    if 'AGLC' in payee_upper or 'LICENSE' in desc_upper:
        return GL_CODES['licensing']
    
    # Source deductions
    if 'REVENUE CANADA' in payee_upper or 'SOURCE DEDUCTIONS' in desc_upper:
        return GL_CODES['source_deductions']
    
    # Advertising
    if 'ACTION PAGES' in payee_upper or 'BRIDAL SHOW' in desc_upper or 'WELCOME WAGON' in payee_upper:
        return GL_CODES['advertising']
    
    # Donations
    if 'WORD OF LIFE' in payee_upper or 'DONATION' in desc_upper:
        return GL_CODES['donations']
    
    # Bank transfers
    if 'ARROW LIMOUSINE' in payee_upper and 'TRANSFER' in desc_upper:
        return GL_CODES['bank_transfer']
    
    # Special case: Check 107 - lien holder payment (still payroll expense)
    if 'KEVIN KOSIK' in payee_upper:
        return GL_CODES['payroll']  # Payroll expense paid to lien holder
    
    return GL_CODES['unknown']

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("SCOTIA BANK CHEQUE REGISTER IMPORT")
        print("=" * 80)
        
        # Statistics
        total_checks = len(CHEQUE_DATA)
        checks_with_tx_id = sum(1 for c in CHEQUE_DATA if c[5] is not None)
        checks_without_date = sum(1 for c in CHEQUE_DATA if c[1] is None)
        nsf_checks = sum(1 for c in CHEQUE_DATA if 'NSF' in c[3])
        void_checks = sum(1 for c in CHEQUE_DATA if 'VOID' in c[3])
        
        print(f"\nCheque Register Overview:")
        print(f"  Total checks: {total_checks}")
        print(f"  Checks with TX ID: {checks_with_tx_id}")
        print(f"  Checks without date: {checks_without_date}")
        print(f"  NSF checks: {nsf_checks}")
        print(f"  Void checks: {void_checks}")
        
        # Step 1: Check/create cheque_register table structure
        print("\n" + "=" * 80)
        print("STEP 1: Verify cheque_register table structure")
        print("=" * 80)
        
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'cheque_register'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        if columns:
            print(f"✓ cheque_register table exists with {len(columns)} columns:")
            for col, dtype in columns:
                print(f"  - {col}: {dtype}")
        else:
            print("✗ cheque_register table does not exist - creating...")
            cur.execute("""
                CREATE TABLE cheque_register (
                    id SERIAL PRIMARY KEY,
                    cheque_number INTEGER NOT NULL,
                    cheque_date DATE,
                    amount DECIMAL(12,2) NOT NULL,
                    payee VARCHAR(200),
                    description TEXT,
                    banking_transaction_id INTEGER,
                    gl_code VARCHAR(10),
                    is_nsf BOOLEAN DEFAULT FALSE,
                    is_void BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("✓ Created cheque_register table")
        
        # Step 2: Insert/update cheque register data
        print("\n" + "=" * 80)
        print("STEP 2: Import cheque register data")
        print("=" * 80)
        
        inserted = 0
        updated = 0
        
        for cheque_num, date_str, amount, description, payee, tx_id in CHEQUE_DATA:
            # Parse date
            cheque_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
            
            # Detect NSF and VOID
            is_nsf = 'NSF' in description
            is_void = 'VOID' in description or cheque_num == 10  # Check 10 not issued
            
            # Assign GL code
            gl_code = assign_gl_code(payee, description)
            
            # Special notes
            notes = []
            if is_nsf:
                notes.append('NSF (Not Sufficient Funds)')
            if is_void:
                notes.append('VOID - Check not issued or cancelled')
            if cheque_num == 96:
                notes.append('Paid by CIBC instead of Scotia')
            if cheque_num == 107:
                notes.append('Payroll expense for Dustan Townsend, paid to lien holder Kevin Kosik for guitar')
            
            notes_str = '; '.join(notes) if notes else None
            
            # Check if exists
            cur.execute("SELECT id FROM cheque_register WHERE cheque_number::text = %s", (str(cheque_num),))
            existing = cur.fetchone()
            
            if existing:
                # Update existing
                cur.execute("""
                    UPDATE cheque_register
                    SET cleared_date = COALESCE(%s, cleared_date),
                        amount = %s,
                        payee = %s,
                        memo = %s,
                        banking_transaction_id = COALESCE(%s, banking_transaction_id),
                        status = CASE 
                            WHEN %s THEN 'NSF'
                            WHEN %s THEN 'VOID'
                            ELSE status
                        END,
                        created_at = CURRENT_TIMESTAMP
                    WHERE cheque_number::text = %s
                """, (cheque_date, amount, payee, description, tx_id, is_nsf, is_void, str(cheque_num)))
                updated += 1
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO cheque_register 
                    (cheque_number, cleared_date, amount, payee, memo, banking_transaction_id, 
                     status, account_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, '903990106011')
                """, (str(cheque_num), cheque_date, amount, payee, description, tx_id,
                      'NSF' if is_nsf else ('VOID' if is_void else 'CLEARED')))
                inserted += 1
        
        conn.commit()
        print(f"\n✓ Inserted: {inserted} new cheques")
        print(f"✓ Updated: {updated} existing cheques")
        
        # Step 3: Match to banking and fill missing dates
        print("\n" + "=" * 80)
        print("STEP 3: Match to banking_transactions and fill missing dates")
        print("=" * 80)
        
        # Get cheques with TX ID but no date
        cur.execute("""
            SELECT cr.id, cr.cheque_number, cr.banking_transaction_id
            FROM cheque_register cr
            WHERE cr.banking_transaction_id IS NOT NULL
            AND cr.cheque_date IS NULL
        """)
        missing_dates = cur.fetchall()
        
        filled_dates = 0
        for reg_id, cheque_num, tx_id in missing_dates:
            # Get date from banking
            cur.execute("""
                SELECT transaction_date 
                FROM banking_transactions 
                WHERE transaction_id = %s
            """, (tx_id,))
            banking_row = cur.fetchone()
            
            if banking_row and banking_row[0]:
                cur.execute("""
                    UPDATE cheque_register
                    SET cheque_date = %s
                    WHERE id = %s
                """, (banking_row[0], reg_id))
                filled_dates += 1
                print(f"  Cheque #{cheque_num}: Filled date from banking TX {tx_id} -> {banking_row[0]}")
        
        conn.commit()
        print(f"\n✓ Filled {filled_dates} missing dates from banking records")
        
        # Step 4: Create receipts for checks without them
        print("\n" + "=" * 80)
        print("STEP 4: Create receipts for checks without receipt records")
        print("=" * 80)
        
        # Find checks with banking_transaction_id but no receipt
        cur.execute("""
            SELECT 
                cr.id,
                cr.cheque_number,
                cr.cheque_date,
                cr.amount,
                cr.payee,
                cr.memo,
                cr.banking_transaction_id,
                cr.status
            FROM cheque_register cr
            WHERE cr.banking_transaction_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM receipts r
                WHERE r.banking_transaction_id = cr.banking_transaction_id
            )
            AND cr.status != 'VOID'
            ORDER BY cr.cheque_number::integer
        """)
        checks_needing_receipts = cur.fetchall()
        
        receipts_created = 0
        for reg_id, cheque_num, cheque_date, amount, payee, memo, tx_id, status in checks_needing_receipts:
            # Calculate GST (5% included in amount)
            gst_amount = round(amount * 0.05 / 1.05, 2)
            net_amount = round(amount - gst_amount, 2)
            
            # Assign GL code from payee
            gl_code = assign_gl_code(payee, memo)
            
            # Category based on GL code
            category_map = {
                '5210': 'Payroll',
                '5150': 'Vehicle Lease',
                '5120': 'Vehicle Maintenance',
                '5410': 'Rent',
                '5420': 'Utilities',
                '5310': 'Insurance',
                '5330': 'Licensing',
                '2310': 'Payroll Taxes',
                '5510': 'Advertising',
                '5850': 'Other Expense',
                '1010': 'Bank Transfer',
            }
            category = category_map.get(gl_code, 'Other Expense')
            
            # Receipt description
            receipt_desc = f"Cheque #{cheque_num} - {memo}"
            if status == 'NSF':
                receipt_desc += " (NSF)"
            
            # Insert receipt
            cur.execute("""
                INSERT INTO receipts 
                (vendor, amount, receipt_date, 
                 category, memo, banking_transaction_id,
                 created_from_banking)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (banking_transaction_id) DO NOTHING
            """, (payee, amount, cheque_date, 
                  category, receipt_desc, tx_id))
            
            if cur.rowcount > 0:
                receipts_created += 1
                print(f"  ✓ Created receipt for Cheque #{cheque_num}: {payee} ${amount:,.2f} - {category}")
        
        conn.commit()
        print(f"\n✓ Created {receipts_created} receipts from cheque register")
        
        # Step 5: Summary report
        print("\n" + "=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        
        # Total cheques
        cur.execute("SELECT COUNT(*) FROM cheque_register")
        total = cur.fetchone()[0]
        
        # With dates
        cur.execute("SELECT COUNT(*) FROM cheque_register WHERE cheque_date IS NOT NULL")
        with_dates = cur.fetchone()[0]
        
        # Linked to banking
        cur.execute("SELECT COUNT(*) FROM cheque_register WHERE banking_transaction_id IS NOT NULL")
        linked = cur.fetchone()[0]
        
        # With receipts
        cur.execute("""
            SELECT COUNT(DISTINCT cr.cheque_number)
            FROM cheque_register cr
            JOIN receipts r ON r.banking_transaction_id = cr.banking_transaction_id
        """)
        with_receipts = cur.fetchone()[0]
        
        # NSF and Void
        cur.execute("SELECT COUNT(*) FROM cheque_register WHERE status = 'NSF'")
        nsf_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM cheque_register WHERE status = 'VOID'")
        void_count = cur.fetchone()[0]
        
        # Summary by payee
        cur.execute("""
            SELECT payee, COUNT(*), SUM(amount)
            FROM cheque_register
            WHERE status != 'VOID'
            GROUP BY payee
            ORDER BY SUM(amount) DESC
            LIMIT 10
        """)
        gl_distribution = cur.fetchall()
        
        print(f"\nCheque Register Status:")
        print(f"  Total cheques in register: {total}")
        print(f"  Cheques with dates: {with_dates} ({with_dates/total*100:.1f}%)")
        print(f"  Linked to banking: {linked} ({linked/total*100:.1f}%)")
        print(f"  With receipt records: {with_receipts} ({with_receipts/total*100:.1f}%)")
        print(f"  NSF cheques: {nsf_count}")
        print(f"  Void cheques: {void_count}")
        
        print(f"\nTop Payees by Amount:")
        for payee, count, total_amt in gl_distribution:
            print(f"  {payee}: {count} cheques, ${total_amt:,.2f}")
        
        print("\n" + "=" * 80)
        print("✓ IMPORT COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
