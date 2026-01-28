#!/usr/bin/env python3
"""
Extract and calculate actual totals from 2012 Expenses.xlsm.

Fix the amount extraction to get real expense totals from Debit/Credit columns.
"""

import sys
import os
import pandas as pd
from decimal import Decimal
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def extract_expense_totals_by_category(file_path):
    """Extract actual expense totals from each category sheet."""
    
    print("2012 EXPENSE TOTALS EXTRACTION")
    print("=" * 50)
    
    # Major expense categories to focus on
    priority_sheets = [
        'Fuel', 'Hosp Supp', 'Repairs & Maint', 'Insurance', 'Bank Fees',
        'Office Supplies', 'Rent', 'Phone', 'Utilities', 'Payroll',
        'Advertising', 'Meals', 'Lease', 'Misc Expenses'
    ]
    
    category_totals = {}
    grand_total = Decimal('0')
    
    for sheet_name in priority_sheets:
        try:
            print(f"\nProcessing: {sheet_name}")
            print("-" * 30)
            
            # Read the sheet
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Find Debit and Credit columns
            debit_col = None
            credit_col = None
            
            for col in df.columns:
                col_str = str(col).lower()
                if 'debit' in col_str:
                    debit_col = col
                elif 'credit' in col_str:
                    credit_col = col
            
            if not debit_col:
                print(f"  No debit column found")
                continue
                
            # Extract debit amounts (expenses)
            debit_series = pd.to_numeric(df[debit_col], errors='coerce')
            debit_total = debit_series.sum()
            debit_count = debit_series.count()
            
            # Extract credit amounts (if any)
            credit_total = Decimal('0')
            credit_count = 0
            if credit_col:
                credit_series = pd.to_numeric(df[credit_col], errors='coerce')
                credit_total = credit_series.sum()
                credit_count = credit_series.count()
            
            # Net expense for this category
            net_expense = Decimal(str(debit_total)) - Decimal(str(credit_total))
            
            if net_expense > 0:
                category_totals[sheet_name] = {
                    'debit_total': Decimal(str(debit_total)),
                    'credit_total': Decimal(str(credit_total)),
                    'net_expense': net_expense,
                    'debit_count': debit_count,
                    'credit_count': credit_count
                }
                
                grand_total += net_expense
                
                print(f"  Debit Total:   ${debit_total:,.2f} ({debit_count} entries)")
                if credit_total > 0:
                    print(f"  Credit Total:  ${credit_total:,.2f} ({credit_count} entries)")
                print(f"  Net Expense:   ${net_expense:,.2f}")
                
            else:
                print(f"  No significant amounts found")
                
        except Exception as e:
            print(f"  Error processing {sheet_name}: {e}")
    
    return category_totals, grand_total

def analyze_fuel_expenses_detail(file_path):
    """Detailed analysis of fuel expenses (largest category)."""
    
    print(f"\nDETAILED FUEL ANALYSIS")
    print("=" * 30)
    
    try:
        df = pd.read_excel(file_path, sheet_name='Fuel')
        
        # Clean and extract fuel transactions
        fuel_transactions = []
        
        for idx, row in df.iterrows():
            # Look for transactions with dates and amounts
            date_val = row.get('Date')
            debit_val = row.get('Debit')
            name_val = row.get('Name')
            memo_val = row.get('Memo')
            
            if pd.notna(date_val) and pd.notna(debit_val) and debit_val > 0:
                fuel_transactions.append({
                    'date': date_val,
                    'amount': float(debit_val),
                    'vendor': str(name_val) if pd.notna(name_val) else '',
                    'memo': str(memo_val) if pd.notna(memo_val) else ''
                })
        
        # Sort by amount (largest first)
        fuel_transactions.sort(key=lambda x: x['amount'], reverse=True)
        
        print(f"Found {len(fuel_transactions)} fuel transactions")
        
        if fuel_transactions:
            total_fuel = sum(t['amount'] for t in fuel_transactions)
            print(f"Total Fuel Expenses: ${total_fuel:,.2f}")
            
            print(f"\nTop 10 Fuel Transactions:")
            for i, transaction in enumerate(fuel_transactions[:10], 1):
                date_str = transaction['date'].strftime('%Y-%m-%d') if hasattr(transaction['date'], 'strftime') else str(transaction['date'])
                print(f"{i:2d}. {date_str} ${transaction['amount']:>8.2f} {transaction['vendor'][:20]} {transaction['memo'][:20]}")
        
        return fuel_transactions
        
    except Exception as e:
        print(f"Error analyzing fuel: {e}")
        return []

def compare_with_database_receipts():
    """Compare Excel totals with database receipts."""
    
    print(f"\nDATABASE COMPARISON")
    print("=" * 30)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'almsdata'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '***REMOVED***'),
            port=os.getenv('DB_PORT', '5432')
        )
        
        cur = conn.cursor()
        
        # Get 2012 receipts from database
        cur.execute("""
            SELECT 
                category,
                COUNT(*) as receipt_count,
                SUM(gross_amount) as total_amount
            FROM receipts 
            WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
            GROUP BY category
            ORDER BY total_amount DESC
        """)
        
        db_receipts = cur.fetchall()
        
        # Get total
        cur.execute("""
            SELECT 
                COUNT(*) as total_receipts,
                SUM(gross_amount) as total_amount
            FROM receipts 
            WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
        """)
        
        db_total = cur.fetchone()
        
        cur.close()
        conn.close()
        
        print(f"Database 2012 Receipts:")
        print(f"Total: ${db_total[1] or 0:,.2f} ({db_total[0] or 0} receipts)")
        
        if db_receipts:
            print(f"\nTop Categories:")
            for category, count, amount in db_receipts[:10]:
                category_name = category or 'Uncategorized'
                print(f"  {category_name[:20]:<20} ${amount:>10,.2f} ({count:>4} receipts)")
        
        return db_total[1] or 0
        
    except Exception as e:
        print(f"Database comparison error: {e}")
        return 0

def main():
    """Extract all expense totals and compare with database."""
    
    file_path = r"L:\limo\docs\2012 Expenses.xlsm"
    
    print("2012 EXPENSE DATA EXTRACTION & RECOVERY")
    print("=" * 60)
    
    # Extract category totals
    category_totals, grand_total = extract_expense_totals_by_category(file_path)
    
    # Detailed fuel analysis
    fuel_transactions = analyze_fuel_expenses_detail(file_path)
    
    # Compare with database
    db_total = compare_with_database_receipts()
    
    # Summary
    print(f"\nRECOVERY ANALYSIS SUMMARY")
    print("=" * 40)
    print(f"Excel Categories Processed: {len(category_totals)}")
    print(f"Excel Total Expenses:       ${grand_total:,.2f}")
    print(f"Database Total Receipts:    ${db_total:,.2f}")
    
    if grand_total > 0:
        variance = grand_total - Decimal(str(db_total))
        variance_pct = (variance / grand_total * 100) if grand_total > 0 else 0
        
        print(f"Variance (Excel - DB):      ${variance:,.2f}")
        print(f"Variance Percentage:        {variance_pct:.1f}%")
        
        print(f"\nTOP EXPENSE CATEGORIES FROM EXCEL:")
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1]['net_expense'], reverse=True)
        
        for category, data in sorted_categories[:10]:
            print(f"  {category:<20} ${data['net_expense']:>10,.2f}")
        
        if variance > 10000:  # Significant variance
            print(f"\n🎯 SIGNIFICANT MISSING DATA IDENTIFIED!")
            print(f"Excel file contains ${variance:,.2f} more in expenses")
            print(f"This represents {variance_pct:.1f}% additional business expenses")
            print(f"Potential tax deduction recovery: ${variance * Decimal('0.14'):,.2f} (14% corporate rate)")
            
            print(f"\n📋 NEXT STEPS:")
            print("1. Import Excel expense data to receipts table")
            print("2. Validate and categorize imported expenses") 
            print("3. Update 2012 tax calculations with recovered data")
            print("4. Apply same methodology to 2013+ Excel files")

if __name__ == "__main__":
    main()