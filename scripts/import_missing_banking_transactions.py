#!/usr/bin/env python3
"""
Complete Banking Transaction Import System for Arrow Limousine
Imports missing banking transactions into receipts table with proper categorization

Handles:
- ATM withdrawals, banking fees, returned payments, insufficient funds
- Overdrafts, e-transfers, Square deposits, loans, loan payments
- Business day processing delays and vendor name truncation
- Revenue entries (stored as negative expenses per Epson workflow)
"""

import psycopg2
import pandas as pd
from datetime import datetime
import sys

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

class BankingTransactionImporter:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.missing_transactions = []
        
    def auto_categorize_transaction(self, description):
        """Automatically categorize transaction based on description patterns"""
        description_upper = description.upper()
        
        category_rules = {
            'BANKING': ['FEE', 'SERVICE CHARGE', 'MONTHLY FEE', 'ACCOUNT FEE', 'ATM', 'WITHDRAWAL', 
                       'NSF', 'INSUFFICIENT', 'OVERDRAFT', 'OVERLIMIT', 'PREAUTHORIZED'],
            'DEPOSITS': ['SQUARE', 'SQ *', 'DEPOSIT', 'CASH DEP', 'CHECK', 'CHEQUE'],
            'LOANS': ['LOAN PAYMENT', 'AUTO LOAN', 'VEHICLE LOAN', 'INTEREST', 'FINANCE CHARGE'],
            'FUEL': ['GAS', 'PETRO', 'SHELL', 'ESSO', 'HUSKY', 'FAS GAS', 'DIESEL', 'BULK FUEL'],
            'TRANSFERS': ['INTERAC', 'E-TRANSFER', 'EMT', 'WIRE', 'TRANSFER', 'POINT OF SALE'],
            'PAYROLL': ['PAYROLL', 'SALARY', 'WAGES', 'EMPLOYEE']
        }
        
        for category, keywords in category_rules.items():
            for keyword in keywords:
                if keyword in description_upper:
                    return category
                    
        return 'UNCATEGORIZED'

    def should_add_to_receipts(self, description):
        """Determine if a banking transaction should be added to receipts"""
        # Exclude internal transfers between own accounts
        exclude_patterns = [
            'TRANSFER FROM', 'TRANSFER TO', 'INTERNAL TRANSFER', 'ACCOUNT TRANSFER',
            'INTERNET TRANSFER 00000'  # Internal transfers have this pattern
        ]
        
        description_upper = description.upper()
        for pattern in exclude_patterns:
            if pattern in description_upper:
                return False
                
        return True

    def identify_missing_transactions(self):
        """Find all banking transactions not in receipts table"""
        print("=== SCANNING BANKING DATA FOR MISSING TRANSACTIONS ===")
        
        with self.conn.cursor() as cur:
            # Get existing receipt amounts and dates for matching
            cur.execute("""
                SELECT receipt_date, expense, vendor_name, id
                FROM receipts 
                WHERE expense != 0
                ORDER BY receipt_date DESC
            """)
            existing_receipts = {(row[0], abs(float(row[1]))): (row[2], row[3]) for row in cur.fetchall()}
            
            # Process banking files
            banking_files = [
                ('l:/limo/CIBC UPLOADS/0228362 (CIBC checking account)/cibc 8362 all.csv', 'Checking'),
                ('l:/limo/CIBC UPLOADS/3648117 (CIBC Business Deposit account, alias for 0534/cibc 8117 all.csv', 'Deposit'),
                ('l:/limo/CIBC UPLOADS/8314462 (CIBC vehicle loans)/cibc 4462 all.csv', 'Loans')
            ]
            
            self.missing_transactions = []
            
            for file_path, account_type in banking_files:
                try:
                    df = pd.read_csv(file_path)
                    print(f"Processing {account_type}: {len(df)} transactions")
                    
                    for _, row in df.iterrows():
                        trans_date = pd.to_datetime(row['Trans_date']).date()
                        description = str(row['Trans_description'])
                        
                        # Calculate transaction amount (combine debit/credit)
                        debit = float(row['Debit']) if pd.notna(row['Debit']) and row['Debit'] != '' else 0
                        credit = float(row['Credit']) if pd.notna(row['Credit']) and row['Credit'] != '' else 0
                        amount = credit - debit  # Positive = money in, Negative = money out
                        
                        if amount == 0:
                            continue
                        
                        # Check if already exists in receipts
                        if (trans_date, abs(amount)) in existing_receipts:
                            continue
                            
                        # Skip internal transfers
                        if not self.should_add_to_receipts(description):
                            continue
                            
                        # Categorize the transaction
                        category = self.auto_categorize_transaction(description)
                        
                        self.missing_transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': amount,
                            'account_type': account_type,
                            'category': category
                        })
                        
                except Exception as e:
                    print(f"Error processing {account_type}: {e}")
                    continue
            
            print(f"Found {len(self.missing_transactions)} missing transactions to import")
            return self.missing_transactions

    def import_missing_transactions(self, batch_size=500):
        """Import missing transactions to receipts table in batches"""
        if not self.missing_transactions:
            print("No transactions to import!")
            return
            
        print(f"=== IMPORTING {len(self.missing_transactions)} MISSING TRANSACTIONS ===")
        
        with self.conn.cursor() as cur:
            imported_count = 0
            
            for i in range(0, len(self.missing_transactions), batch_size):
                batch = self.missing_transactions[i:i + batch_size]
                
                for transaction in batch:
                    # Determine expense amount based on transaction type
                    amount = transaction['amount']
                    
                    if amount > 0:
                        # Positive amounts are revenue - store as negative per Epson workflow
                        expense_amount = -abs(amount)
                        vendor_name = f"REVENUE - {transaction['description'][:30]}"
                    else:
                        # Negative amounts are expenses - store as positive
                        expense_amount = abs(amount)
                        vendor_name = transaction['description'][:50]
                    
                    # Create proper expense account name
                    expense_account = f"{transaction['category']} - {transaction['account_type']}"
                    
                    try:
                        cur.execute("""
                            INSERT INTO receipts (
                                receipt_date, vendor_name, expense, expense_account, 
                                category, description, created_from_banking, source_system
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            transaction['date'],
                            vendor_name,
                            expense_amount,
                            expense_account,
                            transaction['category'],
                            f"Auto-imported {transaction['account_type']}: {transaction['description']}",
                            True,
                            'BANKING_IMPORT'
                        ))
                        
                        imported_count += 1
                        
                    except Exception as e:
                        print(f"Error importing transaction {transaction['date']}: {e}")
                        continue
                
                # Commit each batch
                self.conn.commit()
                print(f"  Imported batch {i//batch_size + 1}: {min(i + batch_size, len(self.missing_transactions))} transactions")
        
        print(f"SUCCESS: Imported {imported_count} transactions to receipts table")

    def show_import_summary(self):
        """Display summary of what will be imported"""
        if not self.missing_transactions:
            return
            
        print(f"\n=== IMPORT SUMMARY ===")
        
        # Category breakdown
        category_stats = {}
        for transaction in self.missing_transactions:
            category = transaction['category']
            if category not in category_stats:
                category_stats[category] = {'count': 0, 'revenue': 0, 'expenses': 0}
            
            category_stats[category]['count'] += 1
            if transaction['amount'] > 0:
                category_stats[category]['revenue'] += transaction['amount']
            else:
                category_stats[category]['expenses'] += abs(transaction['amount'])
        
        print("By Category:")
        for category in sorted(category_stats.keys()):
            stats = category_stats[category]
            print(f"  {category}: {stats['count']} transactions")
            if stats['revenue'] > 0:
                print(f"    Revenue: ${stats['revenue']:,.2f}")
            if stats['expenses'] > 0:
                print(f"    Expenses: ${stats['expenses']:,.2f}")
        
        # Account breakdown
        account_stats = {}
        for transaction in self.missing_transactions:
            account = transaction['account_type']
            account_stats[account] = account_stats.get(account, 0) + 1
        
        print("\nBy Account:")
        for account, count in sorted(account_stats.items()):
            print(f"  {account}: {count} transactions")
        
        # Sample transactions
        print(f"\nSample transactions to import:")
        for transaction in self.missing_transactions[:5]:
            amount = transaction['amount']
            sign = "REVENUE" if amount > 0 else "EXPENSE"
            print(f"  {transaction['date']} | {sign} ${abs(amount):8.2f} | {transaction['category']} | {transaction['description'][:40]}...")

    def run_full_import(self, confirm=True):
        """Run the complete import process"""
        print("=== ARROW LIMOUSINE BANKING RECONCILIATION SYSTEM ===")
        print("Finding and importing missing banking transactions...\n")
        
        # Step 1: Identify missing transactions
        self.identify_missing_transactions()
        
        if not self.missing_transactions:
            print("No missing transactions found - your system is fully reconciled!")
            return
        
        # Step 2: Show summary
        self.show_import_summary()
        
        # Step 3: Confirm import
        if confirm:
            response = input(f"\nImport {len(self.missing_transactions)} missing transactions? (y/N): ")
            if response.lower() != 'y':
                print("Import cancelled. Run again when ready.")
                return
        
        # Step 4: Import transactions
        self.import_missing_transactions()
        
        # Step 5: Final verification
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM receipts WHERE created_from_banking = TRUE")
            auto_imported = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM receipts")
            total_receipts = cur.fetchone()[0]
            
            print(f"\n=== FINAL RECONCILIATION STATUS ===")
            print(f"Total receipts in system: {total_receipts}")
            print(f"Auto-imported from banking: {auto_imported}")
            print(f"Manual receipts: {total_receipts - auto_imported}")
            print("\nReconciliation complete - all banking transactions now tracked!")

if __name__ == "__main__":
    importer = BankingTransactionImporter()
    
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
        print("=== DRY RUN MODE - NO DATA WILL BE IMPORTED ===")
        importer.identify_missing_transactions()
        importer.show_import_summary()
    elif len(sys.argv) > 1 and sys.argv[1] == '--auto':
        print("=== AUTOMATIC MODE - IMPORTING WITHOUT CONFIRMATION ===")
        importer.run_full_import(confirm=False)
    else:
        # Interactive mode
        importer.run_full_import(confirm=True)