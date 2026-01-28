"""
Create Standardized Chart of Accounts (2002-2025)
Maps all category variations to proper GL accounts
"""

import psycopg2
from datetime import datetime

# Connect to database
conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres', 
    password='***REMOVED***',
    host='localhost'
)

# Standardized Chart of Accounts
CHART_OF_ACCOUNTS = {
    # Assets (1000-1999)
    '1000': {
        'name': 'Cash and Cash Equivalents',
        'type': 'Asset',
        'subcategories': {
            '1010': 'Checking Account',
            '1020': 'Savings Account', 
            '1030': 'Petty Cash',
            '1040': 'Money Market',
        }
    },
    '1100': {
        'name': 'Accounts Receivable',
        'type': 'Asset',
        'subcategories': {
            '1110': 'Trade Receivables',
            '1120': 'Other Receivables',
        }
    },
    '1500': {
        'name': 'Fixed Assets',
        'type': 'Asset',
        'subcategories': {
            '1510': 'Vehicles',
            '1520': 'Equipment',
            '1530': 'Accumulated Depreciation',
        }
    },
    
    # Liabilities (2000-2999)
    '2000': {
        'name': 'Accounts Payable',
        'type': 'Liability',
        'subcategories': {
            '2010': 'Trade Payables',
            '2020': 'Other Payables',
        }
    },
    '2100': {
        'name': 'Loans Payable',
        'type': 'Liability',
        'subcategories': {
            '2110': 'Short-term Loans',
            '2120': 'Long-term Loans',
            '2130': 'Line of Credit',
        }
    },
    
    # Equity (3000-3999)
    '3000': {
        'name': 'Owner\'s Equity',
        'type': 'Equity',
        'subcategories': {
            '3010': 'Capital',
            '3020': 'Drawings',
            '3030': 'Retained Earnings',
        }
    },
    
    # Revenue (4000-4999)
    '4000': {
        'name': 'Service Revenue',
        'type': 'Revenue',
        'subcategories': {
            '4010': 'Charter Services',
            '4020': 'Airport Transfers',
            '4030': 'Special Events',
            '4040': 'Other Services',
        }
    },
    '4100': {
        'name': 'Deposits and Transfers',
        'type': 'Revenue',
        'subcategories': {
            '4110': 'Customer Deposits',
            '4120': 'Electronic Transfers',
            '4130': 'Branch Deposits',
        }
    },
    
    # Cost of Goods Sold (5000-5099)
    '5000': {
        'name': 'Direct Operating Costs',
        'type': 'COGS',
        'subcategories': {
            '5010': 'Driver Wages',
            '5020': 'Commissions',
        }
    },
    
    # Operating Expenses (5100-5999)
    '5100': {
        'name': 'Fuel and Vehicle Operating Costs',
        'type': 'Expense',
        'subcategories': {
            '5110': 'Vehicle Fuel',
            '5120': 'Equipment Fuel',
            '5130': 'Fuel Cards',
        }
    },
    '5200': {
        'name': 'Maintenance and Repairs',
        'type': 'Expense',
        'subcategories': {
            '5210': 'Vehicle Maintenance',
            '5220': 'Equipment Maintenance',
            '5230': 'Facility Maintenance',
        }
    },
    '5300': {
        'name': 'Insurance',
        'type': 'Expense',
        'subcategories': {
            '5310': 'Vehicle Insurance',
            '5320': 'Liability Insurance',
            '5330': 'Property Insurance',
        }
    },
    '5400': {
        'name': 'Bank Charges and Interest',
        'type': 'Expense',
        'subcategories': {
            '5410': 'Bank Service Charges',
            '5420': 'NSF Fees',
            '5430': 'Overdraft Fees',
            '5440': 'Interest Expense',
            '5450': 'Credit Card Fees',
        }
    },
    '5500': {
        'name': 'Office and Administrative',
        'type': 'Expense',
        'subcategories': {
            '5510': 'Office Supplies',
            '5520': 'Postage and Shipping',
            '5530': 'Printing and Copying',
            '5540': 'Subscriptions',
        }
    },
    '5600': {
        'name': 'Communication',
        'type': 'Expense',
        'subcategories': {
            '5610': 'Telephone',
            '5620': 'Internet',
            '5630': 'Mobile Phones',
        }
    },
    '5700': {
        'name': 'Travel and Entertainment',
        'type': 'Expense',
        'subcategories': {
            '5710': 'Meals',
            '5720': 'Accommodations',
            '5730': 'Client Entertainment',
            '5740': 'Parking and Tolls',
        }
    },
    '5800': {
        'name': 'Professional Fees',
        'type': 'Expense',
        'subcategories': {
            '5810': 'Accounting',
            '5820': 'Legal',
            '5830': 'Consulting',
        }
    },
    '5900': {
        'name': 'Other Operating Expenses',
        'type': 'Expense',
        'subcategories': {
            '5910': 'Licenses and Permits',
            '5920': 'Dues and Subscriptions',
            '5930': 'Miscellaneous',
        }
    },
}

# Map old category variations to new GL accounts
CATEGORY_MAPPINGS = {
    # Banking and Deposits (should map to Asset accounts, not expense)
    'BANKING - DEPOSIT': '1010',
    'BANKING - CHECKING': '1010',
    'BANKING - LOANS': '2110',
    'BANKING - Checking': '1010',
    'BANKING': '1010',
    
    # Transfers (Internal - shouldn't be expense)
    'TRANSFERS - DEPOSIT': '1010',
    'TRANSFERS - CHECKING': '1010',
    'TRANSFERS - LOANS': '2110',
    
    # Loans
    'LOANS - CHECKING': '2110',
    'LOANS - LOANS': '2110',
    
    # Deposits (Revenue or Liability)
    'DEPOSITS - DEPOSIT': '4110',
    'DEPOSITS - CHECKING': '4110',
    'CUSTOMER PAYMENT': '4110',
    
    # Fuel (Expense)
    'FUEL_EXPENSE': '5110',
    'FUEL - DEPOSIT': '5110',
    'FUEL - CHECKING': '5110',
    'FUEL - LOANS': '5110',
    
    # Bank Charges
    'Bank Charges & Interest': '5410',
    'BANK FEES - NSF': '5420',
    'Branch Transaction SERVICE CHARGE': '5410',
    'Branch Transaction NON-SUFFICIENT': '5420',
    'Branch Transaction OVERDRAFT FEE': '5430',
    'Branch Transaction OVERDRAFT INTER': '5440',
    
    # Payments
    'Internet Bill Payment': '2010',
    'PAYMENT': '2010',
    
    # ATM
    'atm withdrawal': '1030',
    'CASH WITHDRAWAL': '1030',
    
    # Revenue items
    'Branch Transaction Revenue': '4130',
    'Internet Banking Revenue': '4120',
    'Branch Transaction EFT D': '4120',
    'Electronic Funds Transfer': '4120',
    
    # Other
    'OTHER_EXPENSE': '5930',
    'Business expense': '5900',  # Generic - needs subcategorization
    'MAINTENANCE_EXPENSE': '5210',
    'Cheque': '1010',
    'Reimbursement': '5930',
    'Branch Transaction Debit Memo': '5410',
    
    # Existing numbered accounts (keep as-is)
    '5400': '5400',
    '5700': '5700',
    '5600': '5600',
    '5200': '5200',
}

# Vendor-based categorization suggestions
VENDOR_PATTERNS = {
    'FAS GAS': '5110',
    'RUN\'N ON EMPTY': '5110',
    'PETRO-CANADA': '5110',
    'SHELL': '5110',
    'CO-OP': '5110',
    'CHEVRON': '5110',
    'ESSO': '5110',
    
    'PLENTY OF LIQUOR': '5730',  # Client entertainment
    
    'TELUS': '5630',
    'ROGERS': '5630',
    'BELL': '5630',
    'SHAW': '5620',
    
    'MONEY MART': '5450',  # Payment processing fees
    
    'ROYAL BANK': '5410',
    'RBC': '5410',
    'CIBC': '5410',
    'TD BANK': '5410',
}

def create_chart_of_accounts_table():
    """Create table for standardized chart of accounts"""
    cur = conn.cursor()
    
    cur.execute("""
        DROP TABLE IF EXISTS chart_of_accounts CASCADE
    """)
    
    cur.execute("""
        CREATE TABLE chart_of_accounts (
            account_code VARCHAR(10) PRIMARY KEY,
            parent_account VARCHAR(10),
            account_name VARCHAR(200) NOT NULL,
            account_type VARCHAR(50) NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert main accounts and subcategories
    for main_code, details in CHART_OF_ACCOUNTS.items():
        cur.execute("""
            INSERT INTO chart_of_accounts 
            (account_code, parent_account, account_name, account_type, description)
            VALUES (%s, NULL, %s, %s, %s)
        """, (main_code, details['name'], details['type'], f"Main account: {details['name']}"))
        
        for sub_code, sub_name in details.get('subcategories', {}).items():
            cur.execute("""
                INSERT INTO chart_of_accounts
                (account_code, parent_account, account_name, account_type, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (sub_code, main_code, sub_name, details['type'], f"Sub-account of {details['name']}"))
    
    conn.commit()
    print(f"✓ Created chart_of_accounts table with {cur.rowcount} accounts")

def create_category_mapping_table():
    """Create mapping table for old categories to new GL accounts"""
    cur = conn.cursor()
    
    cur.execute("""
        DROP TABLE IF EXISTS category_mappings CASCADE
    """)
    
    cur.execute("""
        CREATE TABLE category_mappings (
            mapping_id SERIAL PRIMARY KEY,
            old_category VARCHAR(200) NOT NULL UNIQUE,
            new_account_code VARCHAR(10) REFERENCES chart_of_accounts(account_code),
            mapping_confidence VARCHAR(20),
            notes TEXT,
            requires_review BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert mappings
    for old_cat, new_code in CATEGORY_MAPPINGS.items():
        confidence = 'high' if new_code in ['5110', '5410', '1010'] else 'medium'
        requires_review = old_cat in ['Business expense', 'OTHER_EXPENSE']
        
        cur.execute("""
            INSERT INTO category_mappings
            (old_category, new_account_code, mapping_confidence, requires_review)
            VALUES (%s, %s, %s, %s)
        """, (old_cat, new_code, confidence, requires_review))
    
    conn.commit()
    print(f"✓ Created category_mappings with {len(CATEGORY_MAPPINGS)} mappings")

def analyze_unmapped_categories():
    """Find categories that need manual mapping"""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT expense_account, COUNT(*) as count
        FROM receipts
        WHERE expense_account IS NOT NULL
        AND expense_account NOT IN (SELECT old_category FROM category_mappings)
        GROUP BY expense_account
        ORDER BY count DESC
    """)
    
    unmapped = cur.fetchall()
    
    if unmapped:
        print(f"\n⚠ Found {len(unmapped)} unmapped categories:")
        for cat, count in unmapped:
            print(f"  - {cat}: {count} receipts")
    else:
        print("\n✓ All receipt categories are mapped!")

def generate_migration_report():
    """Generate report on what will change"""
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("STANDARDIZED CHART OF ACCOUNTS - MIGRATION REPORT")
    print("="*80)
    
    # Summary by account type
    cur.execute("""
        SELECT account_type, COUNT(*) as account_count
        FROM chart_of_accounts
        WHERE parent_account IS NULL
        GROUP BY account_type
        ORDER BY account_type
    """)
    
    print("\nChart of Accounts Summary:")
    print("-" * 80)
    for acct_type, count in cur.fetchall():
        cur.execute("""
            SELECT COUNT(*) FROM chart_of_accounts
            WHERE parent_account IN (
                SELECT account_code FROM chart_of_accounts
                WHERE account_type = %s AND parent_account IS NULL
            )
        """, (acct_type,))
        sub_count = cur.fetchone()[0]
        print(f"{acct_type:20} {count:3} main accounts, {sub_count:3} sub-accounts")
    
    # Mapping impact
    print("\nCategory Mapping Impact:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            cm.old_category,
            cm.new_account_code,
            coa.account_name,
            coa.account_type,
            COUNT(r.id) as receipt_count,
            SUM(r.gross_amount) as total_amount,
            cm.requires_review
        FROM category_mappings cm
        JOIN chart_of_accounts coa ON cm.new_account_code = coa.account_code
        LEFT JOIN receipts r ON r.expense_account = cm.old_category
        GROUP BY cm.old_category, cm.new_account_code, coa.account_name, coa.account_type, cm.requires_review
        ORDER BY receipt_count DESC
    """)
    
    total_receipts = 0
    total_amount = 0
    review_count = 0
    
    for old, new, name, type_, count, amount, review in cur.fetchall():
        if count > 0:
            total_receipts += count
            total_amount += float(amount or 0)
            if review:
                review_count += 1
                marker = "⚠"
            else:
                marker = "✓"
            print(f"{marker} {old:30} → {new} {name:35} ({count:5} receipts, ${amount:>12,.2f})")
    
    print(f"\nTotal: {total_receipts:,} receipts affected, ${total_amount:,.2f}")
    print(f"Requires manual review: {review_count} categories")
    
    # Expense account distribution
    print("\nExpense Account Distribution (NEW):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            coa.account_code,
            coa.account_name,
            COUNT(r.id) as receipt_count,
            SUM(r.gross_amount) as total_amount
        FROM category_mappings cm
        JOIN chart_of_accounts coa ON cm.new_account_code = coa.account_code
        LEFT JOIN receipts r ON r.expense_account = cm.old_category
        WHERE coa.account_type = 'Expense'
        GROUP BY coa.account_code, coa.account_name
        ORDER BY receipt_count DESC
    """)
    
    for code, name, count, amount in cur.fetchall():
        if count > 0:
            print(f"{code}: {name:40} {count:5} receipts  ${amount:>12,.2f}")

def main():
    print("Creating Standardized Chart of Accounts...")
    print("="*80)
    
    create_chart_of_accounts_table()
    create_category_mapping_table()
    analyze_unmapped_categories()
    generate_migration_report()
    
    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("-"*80)
    print("1. Review categories marked with ⚠ (requires manual review)")
    print("2. Add vendor-based categorization for 'Business expense' items")
    print("3. Create update scripts to apply new GL accounts to receipts")
    print("4. Handle 'OTHER_EXPENSE' by analyzing vendor/description patterns")
    print("5. Test reporting with new standardized accounts")
    print("="*80)
    
    conn.close()

if __name__ == '__main__':
    main()
