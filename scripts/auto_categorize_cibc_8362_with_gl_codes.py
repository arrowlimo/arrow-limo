"""
Auto-categorize receipts from CIBC 8362 2014-2017 using GL codes from chart of accounts
"""
import psycopg2
import re

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 100)
print("AUTO-CATEGORIZE RECEIPTS WITH GL CODES - CIBC 8362 (2014-2017)")
print("=" * 100)

# Define categorization rules: (vendor pattern, category, business_personal, gl_code)
categorization_rules = [
    # FUEL - GL 5110
    (r'FAS GAS|ESSO|SHELL|PETRO|HUSKY|CO-OP|CHEVRON|MOHAWK|PIONEER|JOES 76|RUN\'?N ON EMPTY|CENTEX|\bRUN\b', 
     'Fuel Expense', 'Business', '5110'),
    
    # VEHICLE MAINTENANCE & REPAIRS - GL 5120
    (r'WOODRIDGE FORD|ERLES AUTO|KAL TIRE|CANADIAN TIRE|SUPER CLEAN|MR SUDS|CAR WASH|TIRE GARAGE|AUTOMOTIVE VILLAGE|PART SOURCE|PARTS SOURCE|AMBASSADOR MOTORS|AUTOMOTIVE UNIVERSE|KIRKS TIRE|CAM CLARK FORD|MIKASA PERFORMANCE', 
     'Vehicle Maintenance & Repairs', 'Business', '5120'),
    
    # VEHICLE INSURANCE - GL 5130
    (r'ALL SERVICE INSURANCE|ALL SERVICE INSURNACE|ALL SERVICE INS|INTACT INSURANCE|INTACT INS|FIRST INSURANCE|FIRST INSURNACE', 
     'Vehicle Insurance', 'Business', '5130'),
    
    # VEHICLE REGISTRATION - GL 5140
    (r'REGISTRY|ONE STOP LICENCE|VEHICLE REGISTRATION|RED DEER REGISTR', 
     'Vehicle Licenses & Permits', 'Business', '5140'),
    
    # VEHICLE LEASE PAYMENTS - GL 5150
    (r'HEFFNER AUTO|RIFCO|AUTO FINANCE|CAR PAYMENT|ROYNAT LEASE|ASI FINANCE|ASI FINANCIAL|MERIDIAN ONECAP', 
     'Vehicle Lease Payments', 'Business', '5150'),
    
    # BANK FEES - GL 5710
    (r'NSF FEE|NSF CHARGE|OVERDRAFT FEE|ABM FEE|ATM FEE|BANK MACHINE|SERVICE CHARGE|BANK FEE|MONTHLY FEE|OD FEE|OD INTEREST|ETRANSFER FEE|ETRANFER FEE', 
     'Bank Fees & Service Charges', 'Business', '5710'),
    
    # MERCHANT SERVICES FEES - GL 5720
    (r'SQUARE FEE|SQUARE WITHDRAWAL|PAYMENTECH', 
     'Credit Card Processing Fees', 'Business', '5720'),
    
    # PARKING & TOLLS - GL 5740
    (r'CALGARY AIRPORT|AIRPORT AUTHORITY|CALGARY PARKING', 
     'Parking and Tolls', 'Business', '5740'),
    
    # OFFICE SUPPLIES - GL 5420
    (r'STAPLES|OFFICE DEPOT|BUSINESS DEPOT|COPIES NOW|BEST BUY|BED BATH|BEYOND', 
     'Office Supplies', 'Business', '5420'),
    
    # TELEPHONE & INTERNET - GL 5430
    (r'TELUS|BELL|ROGERS|SHAW|INTERNET|PHONE', 
     'Telephone & Internet', 'Business', '5430'),
    
    # UTILITIES - GL 5440
    (r'CITY OF RED DEER|ATCO|ENMAX|EPCOR|GAS BILL|ELECTRIC', 
     'Utilities', 'Business', '5440'),
    
    # CLIENT AMENITIES - GL 5116
    (r'CURVEY BOTTLE|CURVY BOTTLE', 
     'Client Amenities - Food, Coffee, Supplies', 'Business', '5116'),
    
    # TRADE SHOW EXPENSES - GL 5840
    (r'BLACK NIGHT INN', 
     'Business Development Expenses', 'Business', '5840'),
    
    # CONTRACTOR PAYMENTS (eTransfers) - GL 5870 (Miscellaneous until we know more)
    (r'ETRANSFER|E-TRANSFER|ETRANFER', 
     'Miscellaneous Business Expense', 'Business', '5870'),
    
    # LOAN PROCEEDS (not an expense, but need to categorize)
    (r'MONEY MART|CASH MONEY|PAYDAY', 
     'Loan Proceeds', 'Business', None),
    
    # GOVERNMENT PAYMENTS - GL 5870
    (r'RECEIVER GENERAL|CRA|REVENUE CANADA|WCB|WORKERS COMP|AGLC', 
     'Miscellaneous Business Expense', 'Business', '5870'),
    
    # PERSONAL - MORTGAGE - GL 5880
    (r'MCAP|RMG MORTGAGES|MORTGAGE PROTECT|HOME MORTGAGE', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - ENTERTAINMENT - GL 5880
    (r'CINEPLEX|CINEPLES|MOVIE|THEATRE|ITUNES|APPLE\.COM', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - LIQUOR - GL 5880
    (r'LIQUOR|BEER|WINE|ONE STOP LIQUOR|ALCOH', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - FOOD/DRINK - GL 5880
    (r'TIM HORTONS|TIMS|STARBUCKS|COFFEE|MCDONALDS|MACDONALDS|BURGER KING|SUBWAY|A&W|PIZZA|RESTAURANT|WENDYS|PHOENIX BUFFET|7 ELEVEN|7-ELEVEN|EAST SIDE MARIO|KFC|TONY ROMA|DENNYS|RANCH HOUSE|MACS CONVENIENCE|PINK BOW|MONGOLIE GRILL|RED DEER BUFFET|SMITTYS|DAIRY QUEEN|DRAGON CITY|ARBY|\bMACS\b|WOK BOX|CHINESE|SUSHI', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - GROCERIES - GL 5880
    (r'SAVE ON FOODS|SAFEWAY|SUPERSTORE|SOBEYS|WALMART|WAL MART|COSTCO|REAL CANADIAN WHOLESALE', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - MEDICAL - GL 5880
    (r'PHARMACY|SHOPPERS|REXALL|DRUG MART|\bIDA\b|CHIROPRACTOR|PHYSIO|MASSAGE|DENTAL|DOCTOR|MEDICAL', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - PET SUPPLIES - GL 5880
    (r'GLOBAL PET FOOD|PET FOOD', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - PERSONAL CARE - GL 5880
    (r'TOMMY GUNS|TOMMYS|BARBER', 
     'Owner Personal (Non-Deductible)', 'Personal', '5880'),
    
    # PERSONAL - CASH WITHDRAWAL (not an expense)
    (r'BANK WITHDRAWAL|CASH WITHDRAWAL', 
     'Cash Withdrawal', 'Personal', None),
    
    # PERSONAL - CREDIT CARD PAYMENTS (not an expense)
    (r'PAYMENT MASTERCARD CAPITAL ONE|PAYMENT CAPITAL ONE|ROYAL BANK VISA PAYMENT|RBC VISA PAYMENT|PAYMENT VISA ROYAL BANK', 
     'Credit Card Payment', 'Personal', None),
]

# Get uncategorized receipts
cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        r.gross_amount,
        r.receipt_date
    FROM receipts r
    WHERE r.banking_transaction_id IN (
        SELECT transaction_id
        FROM banking_transactions
        WHERE bank_id = 1
        AND source_file = '2014-2017 CIBC 8362.xlsx'
    )
    AND (r.category IS NULL OR r.category = 'Uncategorized')
    ORDER BY r.receipt_date
""")

receipts = cur.fetchall()

print(f"\n📊 Found {len(receipts):,} uncategorized receipts\n")

if len(receipts) == 0:
    print("✅ All receipts already categorized")
    cur.close()
    conn.close()
    exit(0)

# Categorize receipts
categorized = 0
uncategorized_count = 0
category_counts = {}

print("🔍 Categorizing with GL codes...")

for receipt_id, vendor_name, amount, date in receipts:
    matched = False
    
    if not vendor_name:
        uncategorized_count += 1
        continue
    
    vendor_upper = vendor_name.upper()
    
    for pattern, category, biz_personal, gl_code in categorization_rules:
        if re.search(pattern, vendor_upper):
            # Update receipt with GL code
            cur.execute("""
                UPDATE receipts
                SET category = %s,
                    business_personal = %s,
                    gl_account_code = %s,
                    auto_categorized = true
                WHERE receipt_id = %s
            """, (category, biz_personal, gl_code, receipt_id))
            
            categorized += 1
            matched = True
            
            # Track counts
            key = f"{gl_code or 'NULL':<10} {category} ({biz_personal})"
            category_counts[key] = category_counts.get(key, 0) + 1
            
            break
    
    if not matched:
        uncategorized_count += 1

# Commit
conn.commit()
print(f"\n✅ COMMITTED {categorized:,} categorizations with GL codes")

# Show breakdown
print("\n" + "=" * 100)
print("CATEGORIZATION BREAKDOWN (with GL codes)")
print("=" * 100)
print(f"{'GL Code':<12} {'Category':<55} {'Count':>10}")
print("=" * 100)

for key, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{key:<67} {count:>10,}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total receipts processed: {len(receipts):,}")
print(f"✅ Auto-categorized: {categorized:,}")
print(f"⏭️  Still uncategorized: {uncategorized_count:,}")
print(f"📊 Success rate: {(categorized/len(receipts)*100):.1f}%")

# Show sample uncategorized
if uncategorized_count > 0:
    print("\n" + "=" * 100)
    print("SAMPLE UNCATEGORIZED VENDORS (first 20)")
    print("=" * 100)
    
    cur.execute("""
        SELECT DISTINCT vendor_name, COUNT(*) as cnt
        FROM receipts r
        WHERE r.banking_transaction_id IN (
            SELECT transaction_id
            FROM banking_transactions
            WHERE bank_id = 1
            AND source_file = '2014-2017 CIBC 8362.xlsx'
        )
        AND (r.category IS NULL OR r.category = 'Uncategorized')
        AND r.vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY cnt DESC
        LIMIT 20
    """)
    
    print(f"\n{'Vendor':<60} {'Count':<10}")
    print("-" * 100)
    for vendor, cnt in cur.fetchall():
        print(f"{vendor[:60]:<60} {cnt:<10}")

cur.close()
conn.close()

print("\n✅ Auto-categorization with GL codes complete")
print("\nNOTE: Bank transfers will be handled separately with source/destination accounts")
