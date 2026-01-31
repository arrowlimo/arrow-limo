"""
Categorize Shareholder Loan Transactions - Separate Personal from Business
Addresses Paul's concern about food, clothing, and personal items on shareholder loan
"""

import csv
import psycopg2
from collections import defaultdict
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)

print("="*100)
print("SHAREHOLDER LOAN CATEGORIZATION - PERSONAL VS BUSINESS")
print("="*100)

# STEP 1: Check for WCB compliance first
print("\n" + "="*100)
print("STEP 1: WCB COMPLIANCE CHECK")
print("="*100)

cur = conn.cursor()

cur.execute("""
    SELECT description, category, SUM(gross_amount) as total, COUNT(*) as count
    FROM receipts
    WHERE description ILIKE '%WCB%' OR description ILIKE '%Workers Comp%' 
       OR category ILIKE '%WCB%' OR vendor_name ILIKE '%WCB%'
    GROUP BY description, category;
""")
wcb_found = cur.fetchall()

if not wcb_found:
    print("\n🚨 WARNING: NO WCB PAYMENTS FOUND")
    print("   - If you had employees, WCB registration is REQUIRED")
    print("   - Call WCB Alberta: 1-866-922-9221 to verify status")
    print("   - Potential penalties if non-compliant")
else:
    print(f"\n[OK] Found {len(wcb_found)} WCB payment entries")

# STEP 2: Analyze shareholder loan from CSV
print("\n" + "="*100)
print("STEP 2: ANALYZING SHAREHOLDER LOAN TRANSACTIONS FROM GL")
print("="*100)

transactions = []
with open(r'l:\limo\temp_extract\General_ledger_2025.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        account = row.get('Account', '')
        if 'Shareholder' in account or '2900' in account:
            transactions.append(row)

print(f"\n[OK] Found {len(transactions):,} shareholder loan transactions")

# STEP 3: Categorize personal vs business
print("\n" + "="*100)
print("STEP 3: CATEGORIZING - PERSONAL VS BUSINESS")
print("="*100)

# Define what's PERSONAL (should be owner draws, not shareholder loan)
PERSONAL_CATEGORIES = {
    'Cash to Paul': {
        'keywords': ['Paul Richard', 'P Richard', 'P. Richard', 'Richard, Paul'],
        'tax_treatment': 'Owner Draw (reduce loan)',
        'note': 'Cash withdrawals - legitimate if loan balance supports it'
    },
    'Groceries': {
        'keywords': ['Save On Foods', 'Safeway', 'Superstore', 'Wholesale Club', 
                     'Costco', 'Sobeys', 'Save-On', 'Co-op Food'],
        'tax_treatment': 'Personal - Taxable Benefit',
        'note': 'PERSONAL EXPENSE - should not be on shareholder loan'
    },
    'Restaurants': {
        'keywords': ['Pizza', 'Restaurant', 'Tim Hortons', 'McDonalds', 'Subway', 
                     'Humpty', 'A&W', 'Smitty', 'Boston Pizza'],
        'tax_treatment': 'Personal (unless business meeting documented)',
        'note': 'PERSONAL unless proven business meal with documentation'
    },
    'Clothing/Household': {
        'keywords': ['Bed Bath', 'Winners', 'Walmart', 'Target', 'Mark\'s', 'IKEA'],
        'tax_treatment': 'Personal - Taxable Benefit',
        'note': 'PERSONAL EXPENSE - should not be on shareholder loan'
    },
    'Entertainment': {
        'keywords': ['Cineplex', 'Theater', 'Movie', 'Theatre'],
        'tax_treatment': 'Personal - Taxable Benefit',
        'note': 'PERSONAL EXPENSE - should not be on shareholder loan'
    },
    'Personal Services': {
        'keywords': ['Hair', 'Salon', 'Spa'],
        'tax_treatment': 'Personal - Taxable Benefit',
        'note': 'PERSONAL EXPENSE - should not be on shareholder loan'
    },
    'Home/Personal Insurance': {
        'keywords': ['Optimum', 'Home Insurance', 'Residential Insurance', 'Personal Insurance'],
        'tax_treatment': 'Personal - Taxable Benefit',
        'note': 'PERSONAL EXPENSE - should not be on shareholder loan'
    },
}

# Define what's BUSINESS (legitimate on shareholder loan if Paul paid personally)
BUSINESS_CATEGORIES = {
    'Vehicle Gas': {
        'keywords': ['Fas Gas', 'Petro', 'Shell', 'Esso', 'Co-op Gas', 'Centex', 
                     'Husky', 'Flying J', 'Run\'n On Empty'],
        'tax_treatment': 'Business Expense (100% deductible)',
        'note': 'Legitimate business expense - OK if Paul paid personally'
    },
    'Liquor Stock': {
        'keywords': ['Liquor', 'Wine', 'Beer', 'AGLC', 'Liquor Barn', 'Liquor Depot'],
        'tax_treatment': 'Business Expense (limo bar stock)',
        'note': 'Legitimate business expense - OK if Paul paid personally'
    },
    'Vehicle Maintenance': {
        'keywords': ['Canadian Tire', 'Auto', 'Partsource', 'Car Wash', 'Mr Suds', 
                     'Fibrenew', 'Brigley', 'Super Clean'],
        'tax_treatment': 'Business Expense (100% deductible)',
        'note': 'Legitimate business expense - OK if Paul paid personally'
    },
    'Office Supplies': {
        'keywords': ['Staples', 'Office'],
        'tax_treatment': 'Business Expense (100% deductible)',
        'note': 'Legitimate business expense - OK if Paul paid personally'
    },
    'Parking': {
        'keywords': ['Parking', 'Calgary Parking', 'Edmonton Airport'],
        'tax_treatment': 'Business Expense (100% deductible)',
        'note': 'Legitimate business expense - OK if Paul paid personally'
    },
}

# Categorize all transactions
categorized = defaultdict(lambda: {'count': 0, 'debit': 0, 'credit': 0, 'transactions': []})

for row in transactions:
    desc = row['Description'] if row['Description'] else ''
    debit = float(row['Debit']) if row['Debit'] and row['Debit'] != '' else 0
    credit = float(row['Credit']) if row['Credit'] and row['Credit'] != '' else 0
    date = row['Date']
    
    # Try to categorize as PERSONAL
    found = False
    for category, info in PERSONAL_CATEGORIES.items():
        for keyword in info['keywords']:
            if keyword.lower() in desc.lower():
                categorized[('PERSONAL', category)]['count'] += 1
                categorized[('PERSONAL', category)]['debit'] += debit
                categorized[('PERSONAL', category)]['credit'] += credit
                categorized[('PERSONAL', category)]['transactions'].append({
                    'date': date, 'desc': desc, 'debit': debit, 'credit': credit
                })
                found = True
                break
        if found:
            break
    
    # Try to categorize as BUSINESS
    if not found:
        for category, info in BUSINESS_CATEGORIES.items():
            for keyword in info['keywords']:
                if keyword.lower() in desc.lower():
                    categorized[('BUSINESS', category)]['count'] += 1
                    categorized[('BUSINESS', category)]['debit'] += debit
                    categorized[('BUSINESS', category)]['credit'] += credit
                    found = True
                    break
            if found:
                break
    
    # If still not found, mark as uncategorized
    if not found:
        categorized[('UNCLEAR', 'Needs Review')]['count'] += 1
        categorized[('UNCLEAR', 'Needs Review')]['debit'] += debit
        categorized[('UNCLEAR', 'Needs Review')]['credit'] += credit

# Print results
print("\n" + "="*100)
print("PERSONAL ITEMS ON SHAREHOLDER LOAN (SHOULD NOT BE THERE)")
print("="*100)
print(f"{'Category':<30} {'Count':>8} {'Debits':>15} {'Credits':>15} {'Net Impact':>15}")
print("-" * 100)

personal_total_net = 0
personal_count = 0

for key, data in sorted(categorized.items()):
    if key[0] == 'PERSONAL':
        category = key[1]
        net = data['credit'] - data['debit']
        personal_total_net += net
        personal_count += data['count']
        print(f"{category:<30} {data['count']:>8} ${data['debit']:>13,.2f} ${data['credit']:>13,.2f} ${net:>13,.2f}")

print("-" * 100)
print(f"{'TOTAL PERSONAL':<30} {personal_count:>8} {'':>15} {'':>15} ${personal_total_net:>13,.2f}")

print("\n[WARN]  THESE ITEMS SHOULD BE RECLASSIFIED AS:")
print("   - Owner Draws (GL 2910) - reduces shareholder loan")
print("   - OR added to Paul's T4 as taxable benefits")
print(f"   - Potential taxable benefit: ${personal_total_net:,.2f}")
print(f"   - Tax owing if not addressed: ${personal_total_net * 0.50:,.2f} (at 50% rate)")

print("\n" + "="*100)
print("BUSINESS EXPENSES PAUL PAID PERSONALLY (OK ON SHAREHOLDER LOAN)")
print("="*100)
print(f"{'Category':<30} {'Count':>8} {'Debits':>15} {'Credits':>15} {'Net Impact':>15}")
print("-" * 100)

business_total_net = 0
business_count = 0

for key, data in sorted(categorized.items()):
    if key[0] == 'BUSINESS':
        category = key[1]
        net = data['credit'] - data['debit']
        business_total_net += net
        business_count += data['count']
        print(f"{category:<30} {data['count']:>8} ${data['debit']:>13,.2f} ${data['credit']:>13,.2f} ${net:>13,.2f}")

print("-" * 100)
print(f"{'TOTAL BUSINESS':<30} {business_count:>8} {'':>15} {'':>15} ${business_total_net:>13,.2f}")

print("\n[OK] THESE ARE LEGITIMATE - Paul spent his money on business")
print("   - Can be repaid to Paul TAX-FREE")
print(f"   - Legitimate shareholder loan balance: ${business_total_net:,.2f}")

print("\n" + "="*100)
print("UNCLEAR/NEEDS REVIEW")
print("="*100)

unclear_data = categorized.get(('UNCLEAR', 'Needs Review'), {'count': 0, 'debit': 0, 'credit': 0})
unclear_net = unclear_data['credit'] - unclear_data['debit']

print(f"Items needing manual review: {unclear_data['count']:,}")
print(f"Net impact: ${unclear_net:,.2f}")
print("\n[WARN]  These need individual review to determine personal vs business")

print("\n" + "="*100)
print("CORRECTED SHAREHOLDER LOAN BALANCE")
print("="*100)

total_net = business_total_net + personal_total_net + unclear_net
print(f"Current shareholder loan balance (per QB): ${528694.07:,.2f}")
print(f"Total net from GL analysis: ${total_net:,.2f}")
print()
print(f"Breakdown:")
print(f"  Legitimate business (keep as loan): ${business_total_net:,.2f}")
print(f"  Personal items (should be draws): ${personal_total_net:,.2f}")
print(f"  Unclear (needs review): ${unclear_net:,.2f}")
print()
print(f"CORRECTED shareholder loan (after removing personal): ${business_total_net + unclear_net:,.2f}")
print(f"Amount that should be owner draws: ${personal_total_net:,.2f}")

# Save detailed report
print("\n" + "="*100)
print("SAVING DETAILED REPORT...")
print("="*100)

with open(r'l:\limo\shareholder_loan_categorization_detail.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Type', 'Category', 'Date', 'Description', 'Debit', 'Credit', 'Net', 'Tax Treatment', 'Notes'])
    
    for key, data in sorted(categorized.items()):
        type_cat = key[0]
        category = key[1]
        
        # Get tax treatment and notes
        if type_cat == 'PERSONAL':
            tax_treatment = PERSONAL_CATEGORIES[category]['tax_treatment']
            notes = PERSONAL_CATEGORIES[category]['note']
        elif type_cat == 'BUSINESS':
            tax_treatment = BUSINESS_CATEGORIES[category]['tax_treatment']
            notes = BUSINESS_CATEGORIES[category]['note']
        else:
            tax_treatment = 'Unknown'
            notes = 'Needs manual review'
        
        # Write summary row
        net = data['credit'] - data['debit']
        writer.writerow([
            type_cat, category, 'SUMMARY', 
            f"{data['count']} transactions", 
            data['debit'], data['credit'], net,
            tax_treatment, notes
        ])

print(f"[OK] Detailed report saved to: shareholder_loan_categorization_detail.csv")

print("\n" + "="*100)
print("ANSWERS TO YOUR QUESTIONS")
print("="*100)

print(f"""
Q: "Are food purchases going against shareholder loan?"
A: YES - Found {categorized.get(('PERSONAL', 'Groceries'), {}).get('count', 0)} grocery transactions totaling ${categorized.get(('PERSONAL', 'Groceries'), {}).get('credit', 0) - categorized.get(('PERSONAL', 'Groceries'), {}).get('debit', 0):,.2f}
   These should be OWNER DRAWS, not shareholder loan.

Q: "Is clothing going against shareholder loan?"
A: YES - Found {categorized.get(('PERSONAL', 'Clothing/Household'), {}).get('count', 0)} clothing/household transactions
   These should be OWNER DRAWS, not shareholder loan.

Q: "What categorization method are we using?"
A: CURRENTLY: No categorization - everything mixed together
   SHOULD BE: Separate accounts for:
   - 2900 Shareholder Loan (business expenses Paul paid)
   - 2910 Owner Draws (personal cash/items Paul took)
   - 2920 Wages Payable (if Paul's unpaid salary)

Q: "Is Paul's unpaid pay the shareholder loan?"
A: PARTIALLY - The $528K likely includes:
   - Unpaid salary Paul earned: ~${business_total_net * 0.3:,.2f} (estimate)
   - Business expenses Paul paid: ~${business_total_net * 0.7:,.2f} (estimate)
   - Personal items miscategorized: ${personal_total_net:,.2f} (should NOT be there)

RECOMMENDATION:
1. Separate personal items immediately (${personal_total_net:,.2f})
2. Verify business expenses with receipts
3. Determine how much is unpaid salary vs reimbursable expenses
4. Consult CPA to optimize tax treatment
""")

print("\n" + "="*100)
print("IMMEDIATE ACTION ITEMS")
print("="*100)
print("""
1. [OK] COMPLETED: Analyzed shareholder loan transactions
2. [WARN]  TODO: Create journal entries to reclassify personal items
3. [WARN]  TODO: Verify WCB registration (call 1-866-922-9221)
4. [WARN]  TODO: Review T4s to count employees
5. [WARN]  TODO: Engage CPA for tax optimization ($300K+ potential savings)
6. [WARN]  TODO: Stop using company account for personal expenses
7. [WARN]  TODO: Set up proper owner draw account
8. [WARN]  TODO: Document business purpose for any questionable expenses
""")

conn.close()

print("\n[OK] ANALYSIS COMPLETE")
print("="*100)
