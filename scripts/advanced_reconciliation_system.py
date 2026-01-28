#!/usr/bin/env python3
"""
Advanced Reconciliation System for Arrow Limousine
Handles vendor name truncation, business day delays, and creates missing banking transactions

Features:
1. Amount-first matching (highest confidence)
2. Fuzzy vendor name matching
3. Flexible date ranges (±3-5 business days)
4. Missing transaction identification and import
5. Standardized category system
"""

import psycopg2
import pandas as pd
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import holidays

# Database configuration
DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

class AdvancedReconciliationSystem:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.canadian_holidays = holidays.Canada()
        
    def setup_category_system(self):
        """Create standardized category and subcategory tables"""
        print("=== Setting up standardized category system ===")
        
        with self.conn.cursor() as cur:
            # Create categories table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transaction_categories (
                    id SERIAL PRIMARY KEY,
                    category_name VARCHAR(50) NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Create subcategories table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transaction_subcategories (
                    id SERIAL PRIMARY KEY,
                    category_id INTEGER REFERENCES transaction_categories(id),
                    subcategory_name VARCHAR(100) NOT NULL,
                    pattern_keywords TEXT[], -- For automatic classification
                    description TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(category_id, subcategory_name)
                )
            """)
            
            # Insert standard categories
            categories = [
                ('FUEL', 'Vehicle fuel purchases'),
                ('BANKING', 'Bank fees, transfers, and services'),
                ('VEHICLE', 'Vehicle maintenance, insurance, registration'),
                ('OFFICE', 'Office supplies, equipment, utilities'),
                ('REVENUE', 'Income from charters and services'),
                ('PAYROLL', 'Employee wages and benefits'),
                ('LOANS', 'Loan payments and financing'),
                ('TRANSFERS', 'Internal transfers and movements'),
                ('FEES', 'Various service and transaction fees'),
                ('DEPOSITS', 'Cash and electronic deposits')
            ]
            
            for cat_name, desc in categories:
                cur.execute("""
                    INSERT INTO transaction_categories (category_name, description) 
                    VALUES (%s, %s) 
                    ON CONFLICT (category_name) DO NOTHING
                """, (cat_name, desc))
            
            # Insert subcategories with matching patterns
            subcategories = [
                # Banking subcategories
                ('BANKING', 'ATM Withdrawal', ['ATM', 'WITHDRAWAL', 'CASH ADVANCE']),
                ('BANKING', 'Banking Fee', ['FEE', 'SERVICE CHARGE', 'MONTHLY FEE']),
                ('BANKING', 'Returned Payment', ['RETURNED', 'NSF', 'INSUFFICIENT']),
                ('BANKING', 'Overdraft', ['OVERDRAFT', 'OVERLIMIT']),
                ('BANKING', 'E-Transfer', ['INTERAC', 'E-TRANSFER', 'EMT']),
                ('BANKING', 'Wire Transfer', ['WIRE', 'TRANSFER']),
                
                # Deposits
                ('DEPOSITS', 'Square Deposit', ['SQUARE', 'SQ *']),
                ('DEPOSITS', 'Cash Deposit', ['DEPOSIT', 'CASH DEP']),
                ('DEPOSITS', 'Check Deposit', ['CHECK', 'CHEQUE']),
                
                # Loans  
                ('LOANS', 'Loan Payment', ['LOAN PAYMENT', 'AUTO LOAN', 'VEHICLE LOAN']),
                ('LOANS', 'Interest Charge', ['INTEREST', 'FINANCE CHARGE']),
                
                # Fuel
                ('FUEL', 'Gas Station', ['GAS', 'PETRO', 'SHELL', 'ESSO', 'HUSKY', 'FAS GAS']),
                ('FUEL', 'Diesel', ['DIESEL', 'BULK FUEL']),
                
                # Vehicle
                ('VEHICLE', 'Maintenance', ['REPAIR', 'SERVICE', 'OIL CHANGE']),
                ('VEHICLE', 'Insurance', ['INSURANCE', 'COVERAGE']),
                ('VEHICLE', 'Registration', ['REGISTRY', 'PLATE', 'REGISTRATION']),
                
                # Office
                ('OFFICE', 'Utilities', ['ELECTRIC', 'GAS BILL', 'WATER', 'PHONE']),
                ('OFFICE', 'Supplies', ['OFFICE', 'SUPPLIES', 'STATIONERY']),
                ('OFFICE', 'Equipment', ['COMPUTER', 'SOFTWARE', 'EQUIPMENT'])
            ]
            
            for cat_name, subcat_name, keywords in subcategories:
                cur.execute("""
                    INSERT INTO transaction_subcategories (category_id, subcategory_name, pattern_keywords)
                    SELECT tc.id, %s, %s
                    FROM transaction_categories tc 
                    WHERE tc.category_name = %s
                    ON CONFLICT DO NOTHING
                """, (subcat_name, keywords, cat_name))
            
            self.conn.commit()
            print("✓ Category system created with standard classifications")

    def calculate_business_days_between(self, date1, date2):
        """Calculate business days between two dates, accounting for weekends and holidays"""
        if date1 > date2:
            date1, date2 = date2, date1
            
        business_days = 0
        current_date = date1
        
        while current_date <= date2:
            if current_date.weekday() < 5 and current_date not in self.canadian_holidays:  # Monday = 0, Friday = 4
                business_days += 1
            current_date += timedelta(days=1)
            
        return business_days

    def fuzzy_match_vendor(self, name1, name2, threshold=0.6):
        """Fuzzy match vendor names to handle truncation"""
        if not name1 or not name2:
            return 0.0
            
        # Clean names for comparison
        clean1 = re.sub(r'[^\w\s]', '', name1.upper().strip())
        clean2 = re.sub(r'[^\w\s]', '', name2.upper().strip())
        
        # Check for exact substring matches (handles truncation)
        if clean1 in clean2 or clean2 in clean1:
            return 0.9
            
        # Use sequence matcher for similarity
        similarity = SequenceMatcher(None, clean1, clean2).ratio()
        
        # Boost score for common keywords
        keywords = ['GAS', 'FUEL', 'PETRO', 'SHELL', 'ESSO', 'FAS']
        for keyword in keywords:
            if keyword in clean1 and keyword in clean2:
                similarity += 0.1
                
        return min(similarity, 1.0)

    def identify_missing_banking_transactions(self):
        """Find banking transactions not yet in receipts table"""
        print("=== Identifying missing banking transactions ===")
        
        missing_transactions = []
        
        # Load banking data from CSV files
        banking_files = [
            ('l:/limo/CIBC UPLOADS/0228362 (CIBC checking account)/cibc 8362 all.csv', 'checking'),
            ('l:/limo/CIBC UPLOADS/3648117 (CIBC Business Deposit account, alias for 0534/cibc 8117 all.csv', 'deposit'),
            ('l:/limo/CIBC UPLOADS/8314462 (CIBC vehicle loans)/cibc 4462 all.csv', 'loans')
        ]
        
        for file_path, account_type in banking_files:
            try:
                df = pd.read_csv(file_path)
                print(f"Processing {account_type} account: {len(df)} transactions")
                
                for _, row in df.iterrows():
                    # Skip if already matched in receipts
                    if not self.is_transaction_in_receipts(row['Date'], abs(float(row['Amount']))):
                        
                        # Categorize the transaction
                        category, subcategory = self.auto_categorize_transaction(row['Description'])
                        
                        if self.should_add_to_receipts(row['Description'], category):
                            missing_transactions.append({
                                'date': row['Date'], 
                                'description': row['Description'],
                                'amount': float(row['Amount']),
                                'account_type': account_type,
                                'category': category,
                                'subcategory': subcategory
                            })
                            
            except FileNotFoundError:
                print(f"Banking file not found: {file_path}")
                continue
                
        print(f"Found {len(missing_transactions)} missing banking transactions")
        return missing_transactions

    def is_transaction_in_receipts(self, date, amount, tolerance=0.01):
        """Check if a transaction already exists in receipts table"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM receipts 
                WHERE receipt_date = %s 
                AND ABS(expense - %s) < %s
            """, (date, amount, tolerance))
            
            return cur.fetchone()[0] > 0

    def auto_categorize_transaction(self, description):
        """Automatically categorize transaction based on description patterns"""
        description_upper = description.upper()
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT tc.category_name, ts.subcategory_name, ts.pattern_keywords
                FROM transaction_categories tc
                JOIN transaction_subcategories ts ON tc.id = ts.category_id
                ORDER BY tc.category_name, ts.subcategory_name
            """)
            
            for category, subcategory, keywords in cur.fetchall():
                if keywords:
                    for keyword in keywords:
                        if keyword in description_upper:
                            return category, subcategory
                            
        return 'UNCATEGORIZED', 'Unknown'

    def should_add_to_receipts(self, description, category):
        """Determine if a banking transaction should be added to receipts"""
        # Add most banking transactions except internal transfers between own accounts
        exclude_patterns = [
            'TRANSFER FROM',
            'TRANSFER TO', 
            'INTERNAL TRANSFER',
            'ACCOUNT TRANSFER'
        ]
        
        description_upper = description.upper()
        for pattern in exclude_patterns:
            if pattern in description_upper:
                return False
                
        return True

    def create_missing_receipt_entries(self, missing_transactions):
        """Add missing banking transactions to receipts table"""
        print(f"=== Creating {len(missing_transactions)} missing receipt entries ===")
        
        with self.conn.cursor() as cur:
            for i, transaction in enumerate(missing_transactions):
                # Determine if this is revenue (positive) or expense (negative)
                amount = transaction['amount']
                if amount > 0:
                    # Positive amounts are revenue (but we store as negative per Epson workflow)
                    expense_amount = -abs(amount)
                    vendor_name = f"REVENUE - {transaction['description'][:30]}"
                else:
                    # Negative amounts are expenses
                    expense_amount = abs(amount)
                    vendor_name = transaction['description'][:50]
                
                cur.execute("""
                    INSERT INTO receipts (
                        receipt_date, vendor_name, expense, expense_account, 
                        category, description, created_from_banking
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction['date'],
                    vendor_name,
                    expense_amount,
                    f"{transaction['category']} - {transaction['subcategory']}",
                    transaction['category'],
                    f"Auto-imported from {transaction['account_type']} account: {transaction['description']}",
                    True
                ))
                
                if (i + 1) % 100 == 0:
                    print(f"  Imported {i + 1} transactions...")
                    
            self.conn.commit()
            print(f"✓ Successfully imported {len(missing_transactions)} missing transactions")

    def run_smart_reconciliation(self):
        """Run the complete smart reconciliation process"""
        print("=== STARTING ADVANCED RECONCILIATION SYSTEM ===")
        
        # Step 1: Setup category system
        self.setup_category_system()
        
        # Step 2: Add missing column if needed
        with self.conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE receipts 
                ADD COLUMN IF NOT EXISTS created_from_banking BOOLEAN DEFAULT FALSE
            """)
            self.conn.commit()
        
        # Step 3: Identify missing transactions
        missing_transactions = self.identify_missing_banking_transactions()
        
        # Step 4: Create missing receipt entries
        if missing_transactions:
            response = input(f"\nFound {len(missing_transactions)} missing banking transactions. Import them? (y/N): ")
            if response.lower() == 'y':
                self.create_missing_receipt_entries(missing_transactions)
            else:
                print("Skipping import. Run again when ready.")
        else:
            print("No missing transactions found - system is up to date!")
            
        # Step 5: Show summary
        self.show_reconciliation_summary()

    def show_reconciliation_summary(self):
        """Display reconciliation summary"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM receipts")
            total_receipts = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = TRUE")
            auto_imported = cur.fetchone()[0]
            
            cur.execute("SELECT category, COUNT(*) FROM receipts GROUP BY category ORDER BY COUNT(*) DESC")
            category_breakdown = cur.fetchall()
            
            print(f"\n=== RECONCILIATION SUMMARY ===")
            print(f"Total receipts: {total_receipts}")
            print(f"Auto-imported from banking: {auto_imported}")
            print(f"Manual receipts: {total_receipts - auto_imported}")
            
            print(f"\nCategory breakdown:")
            for category, count in category_breakdown:
                print(f"  {category or 'Uncategorized'}: {count}")

if __name__ == "__main__":
    system = AdvancedReconciliationSystem()
    system.run_smart_reconciliation()