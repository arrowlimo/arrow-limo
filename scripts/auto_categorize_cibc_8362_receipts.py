"""
Auto-categorize receipts from CIBC 8362 2014-2017 based on vendor patterns
Uses business logic from past categorizations
"""
import psycopg2
import re

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 100)
print("AUTO-CATEGORIZE RECEIPTS - CIBC 8362 (2014-2017)")
print("=" * 100)

# Define categorization rules (vendor pattern → category, business_personal)
categorization_rules = [
    # Personal expenses
    (r'TOMMY GUNS|TOMMYS|BARBER', 'Personal Care', 'Personal'),
    (r'PHARMACY|SHOPPERS|REXALL|DRUG MART|\bIDA\b', 'Personal - Medical', 'Personal', '5880'),
    (r'CHIROPRACTOR|PHYSIO|MASSAGE|DENTAL|DOCTOR|MEDICAL', 'Personal - Medical', 'Personal'),
    (r'TIM HORTONS|TIMS|STARBUCKS|COFFEE', 'Personal - Food/Drink', 'Personal'),
    (r'MCDONALDS|MACDONALDS|BURGER KING|SUBWAY|A&W|PIZZA|RESTAURANT|WENDYS|PHOENIX BUFFET|7 ELEVEN|7-ELEVEN|EAST SIDE MARIO|KFC|TONY ROMA|DENNYS|RANCH HOUSE|MACS CONVENIENCE|PINK BOW|MONGOLIE GRILL|RED DEER BUFFET|SMITTYS|DAIRY QUEEN|DRAGON CITY|ARBY|\bMACS\b', 'Personal - Food/Drink', 'Personal', '5880'),
    (r'SAVE ON FOODS|SAFEWAY|SUPERSTORE|SOBEYS|WALMART|WAL MART|COSTCO|REAL CANADIAN WHOLESALE', 'Personal - Groceries', 'Personal'),
    (r'GLOBAL PET FOOD|PET FOOD', 'Personal - Pet Supplies', 'Personal'),
    (r'PAYMENT MASTERCARD CAPITAL ONE|PAYMENT CAPITAL ONE|ROYAL BANK VISA PAYMENT|RBC VISA PAYMENT|PAYMENT VISA ROYAL BANK', 'Credit Card Payment', 'Personal'),
    (r'WOK BOX|CHINESE|SUSHI', 'Personal - Food/Drink', 'Personal'),
    (r'ITUNES|APPLE\.COM', 'Personal - Entertainment', 'Personal'),
    (r'BANK WITHDRAWAL|CASH WITHDRAWAL', 'Cash Withdrawal', 'Personal'),
    
    # Fuel (Business)
    (r'FAS GAS|ESSO|SHELL|PETRO|HUSKY|CO-OP|CHEVRON|MOHAWK|PIONEER|JOES 76|RUN\'?N ON EMPTY|CENTEX|\bRUN\b', 'Fuel', 'Business', '5110'),
    
    # Vehicle expenses
    (r'HEFFNER AUTO|RIFCO|AUTO FINANCE|CAR PAYMENT|ROYNAT LEASE|ASI FINANCE|ASI FINANCIAL|MERIDIAN ONECAP', 'Vehicle Lease/Finance', 'Business'),
    (r'ALL SERVICE INSURANCE|ALL SERVICE INSURNACE|ALL SERVICE INS|INTACT INSURANCE|INTACT INS|FIRST INSURANCE|FIRST INSURNACE', 'Vehicle Insurance', 'Business'),
    (r'REGISTRY|ONE STOP LICENCE|VEHICLE REGISTRATION|RED DEER REGISTR', 'Vehicle Registration', 'Business'),
    (r'WOODRIDGE FORD|ERLES AUTO|KAL TIRE|CANADIAN TIRE|SUPER CLEAN|MR SUDS|CAR WASH|TIRE GARAGE|AUTOMOTIVE VILLAGE|PART SOURCE|PARTS SOURCE|AMBASSADOR MOTORS|AUTOMOTIVE UNIVERSE|KIRKS TIRE|CAM CLARK FORD|MIKASA PERFORMANCE', 'Vehicle Maintenance & Repairs', 'Business', '5120'),
    
    # Mortgage/Rent (Personal home mortgage)
    (r'MCAP|RMG MORTGAGES|MORTGAGE PROTECT|HOME MORTGAGE', 'Personal - Mortgage', 'Personal'),
    
    # Entertainment (Personal)
    (r'CINEPLEX|CINEPLES|MOVIE|THEATRE', 'Personal - Entertainment', 'Personal'),
    
    # Utilities
    (r'TELUS|BELL|ROGERS|SHAW|INTERNET|PHONE', 'Utilities - Phone/Internet', 'Business'),
    (r'CITY OF RED DEER', 'Utilities - Municipal', 'Business'),
    (r'ATCO|ENMAX|EPCOR|GAS BILL|ELECTRIC', 'Utilities - Gas/Electric', 'Business'),
    
    # Banking fees
    (r'NSF FEE|NSF CHARGE|OVERDRAFT FEE', 'Banking Fees - NSF', 'Business'),
    (r'ABM FEE|ATM FEE|BANK MACHINE', 'Banking Fees - ABM', 'Business'),
    (r'SERVICE CHARGE|BANK FEE|MONTHLY FEE|OD FEE|OD INTEREST|ETRANSFER FEE|ETRANFER FEE', 'Banking Fees', 'Business'),
    
    # Square fees (merchant services)
    (r'SQUARE FEE|SQUARE WITHDRAWAL', 'Merchant Services Fees', 'Business'),
    
    # eTransfers (typically business payments to contractors/vendors)
    (r'ETRANSFER|E-TRANSFER|ETRANFER', 'Contractor Payments', 'Business'),
    
    # Loans (payday/short-term for business)
    (r'MONEY MART|CASH MONEY|PAYDAY', 'Loan Proceeds', 'Business'),
    
    # Government
    (r'RECEIVER GENERAL|CRA|REVENUE CANADA|WCB|WORKERS COMP', 'Government Payments', 'Business'),
    
    # Office/Business
    (r'STAPLES|OFFICE DEPOT|BUSINESS DEPOT|COPIES NOW|BEST BUY|BED BATH|BEYOND', 'Office Supplies', 'Business', '5420'),
    (r'CURVEY BOTTLE', 'Business - Hospitality Supplies', 'Business', '5116'),
    (r'BLACK NIGHT INN', 'Trade Show Expenses', 'Business', '5840'),
    (r'CALGARY AIRPORT|AIRPORT AUTHORITY', 'Travel - Parking/Fees', 'Business'),
    
    # Liquor (Personal)
    (r'LIQUOR|BEER|WINE|ONE STOP LIQUOR|ALCOH', 'Personal - Liquor', 'Personal'),
    
    # Miscellaneous retail (Personal)
    (r'AMAZON|EBAY|ONLINE PURCHASE', 'Personal - Shopping', 'Personal'),
]

# Get uncategorized receipts from CIBC 8362 2014-2017
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
uncategorized = 0
category_counts = {}

print("🔍 Categorizing...")

for receipt_id, vendor_name, amount, date in receipts:
    matched = False
    
    if not vendor_name:
        uncategorized += 1
        continue
    
    vendor_upper = vendor_name.upper()
    
    for pattern, category, biz_personal in categorization_rules:
        if re.search(pattern, vendor_upper):
            # Update receipt
            cur.execute("""
                UPDATE receipts
                SET category = %s,
                    business_personal = %s,
                    auto_categorized = true
                WHERE receipt_id = %s
            """, (category, biz_personal, receipt_id))
            
            categorized += 1
            matched = True
            
            # Track counts
            key = f"{category} ({biz_personal})"
            category_counts[key] = category_counts.get(key, 0) + 1
            
            break
    
    if not matched:
        uncategorized += 1

# Commit
conn.commit()
print(f"\n✅ COMMITTED {categorized:,} categorizations")

# Show breakdown
print("\n" + "=" * 100)
print("CATEGORIZATION BREAKDOWN")
print("=" * 100)

for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{category:<50} {count:>6,} receipts")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total receipts processed: {len(receipts):,}")
print(f"✅ Auto-categorized: {categorized:,}")
print(f"⏭️  Still uncategorized: {uncategorized:,}")
print(f"📊 Success rate: {(categorized/len(receipts)*100):.1f}%")

# Show sample uncategorized (for manual review)
if uncategorized > 0:
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

print("\n✅ Auto-categorization complete")
print("\nNOTE: Bank transfers will be handled separately with source/destination accounts")
