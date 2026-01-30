#!/usr/bin/env python3
"""
Enhanced Banking Import - Properly handles revenue columns for deposits and income
"""

import psycopg2
from psycopg2 import sql
import pandas as pd
from datetime import datetime
import hashlib
import os

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres', 
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

def generate_unique_reference(date_str, description, amount, account):
    """Generate a unique reference for each transaction"""
    timestamp = str(int(datetime.now().timestamp() * 1000000))  # microsecond precision
    combined = f"{date_str}_{description}_{amount}_{account}_{timestamp}"
    return hashlib.md5(combined.encode()).hexdigest()[:16]

def auto_categorize_transaction(description):
    """Categorize based on description keywords"""
    desc = description.upper()
    
    if any(word in desc for word in ['ATM', 'WITHDRAWAL', 'FEE', 'SERVICE CHARGE', 'NSF', 'OVERDRAFT']):
        return 'BANKING'
    elif any(word in desc for word in ['SQUARE', 'SQ *', 'DEPOSIT', 'CASH']):
        return 'DEPOSITS'  
    elif any(word in desc for word in ['LOAN', 'HEFFNER', 'INTEREST']):
        return 'LOANS'
    elif any(word in desc for word in ['GAS', 'FUEL', 'PETRO', 'SHELL', 'ESSO', 'HUSKY', 'FAS GAS']):
        return 'FUEL'
    elif any(word in desc for word in ['E-TRANSFER', 'INTERAC', 'EMT', 'TRANSFER']):
        return 'TRANSFERS'
    else:
        return 'UNCATEGORIZED'

def insert_enhanced_transaction(date_str, description, amount, account_type):
    """Insert transaction with proper revenue columns populated"""
    try:
        # Connect fresh for each transaction
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Parse date
        trans_date = pd.to_datetime(date_str).date()
        
        # Skip zero amounts  
        if abs(amount) < 0.01:
            conn.close()
            return False, "Zero amount"
            
        # Skip internal transfers
        if any(word in description.upper() for word in ['INTERNET TRANSFER 00000', 'INTERNAL TRANSFER']):
            conn.close()
            return False, "Internal transfer"
            
        # Categorize
        category = auto_categorize_transaction(description)
        
        # Prepare amounts and revenue fields
        if amount > 0:
            # REVENUE/INCOME - money coming in
            expense_amount = -abs(amount)  # Negative for Epson compatibility
            gross_amount = abs(amount)     # Positive gross revenue
            net_amount = abs(amount)       # Assume no tax for now
            vendor_name = f"REVENUE - {description[:25]}"
        else:
            # EXPENSE - money going out  
            expense_amount = abs(amount)   # Positive expense
            gross_amount = 0.0             # No revenue for expenses
            net_amount = abs(amount)       # Net expense amount
            vendor_name = description[:40]
            
        # Generate unique reference
        unique_ref = generate_unique_reference(date_str, description, amount, account_type)
        
        # Insert record with enhanced revenue columns
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name, 
                expense,
                gross_amount,
                net_amount,
                expense_account,
                category,
                created_from_banking,
                source_system,
                source_reference,
                source_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            trans_date,
            vendor_name,
            expense_amount,
            gross_amount,
            net_amount,
            f"{category} - {account_type}",
            category,
            True,
            'BANKING_IMPORT_ENHANCED',
            unique_ref,
            unique_ref
        ))
        
        conn.close()
        return True, f"Enhanced: {vendor_name[:30]}... (${amount:,.2f})"
        
    except Exception as e:
        if conn:
            conn.close()
        return False, str(e)[:100]

def update_existing_banking_records():
    """Update existing banking records to have proper revenue columns"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cur = conn.cursor()
        
        print("\nUpdating existing banking records with revenue columns...")
        
        # Update revenue transactions (negative expense) to have gross_amount
        cur.execute("""
            UPDATE receipts 
            SET 
                gross_amount = ABS(expense),
                net_amount = ABS(expense)
            WHERE 
                created_from_banking = true 
                AND expense < 0 
                AND (gross_amount = 0 OR gross_amount IS NULL)
        """)
        
        revenue_updated = cur.rowcount
        
        # Update expense transactions to have net_amount 
        cur.execute("""
            UPDATE receipts 
            SET 
                gross_amount = 0,
                net_amount = ABS(expense)
            WHERE 
                created_from_banking = true 
                AND expense > 0 
                AND (net_amount = 0 OR net_amount IS NULL)
        """)
        
        expense_updated = cur.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"  Updated {revenue_updated} revenue records with gross_amount")
        print(f"  Updated {expense_updated} expense records with net_amount")
        
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print(f"Error updating existing records: {e}")
        return False

def main():
    """Main function with option to update existing records or import new ones"""
    print("Enhanced Banking Import - Revenue Column Management")
    print("1. Update existing banking records with revenue columns")
    print("2. Import new transactions (if any)")
    
    # Update existing records first
    if update_existing_banking_records():
        print("[OK] Successfully updated existing banking records")
    else:
        print("[FAIL] Failed to update existing records")
        return
    
    # Check final status
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Get revenue summary
        cur.execute("""
            SELECT 
                category,
                COUNT(*) as transactions,
                SUM(CASE WHEN expense < 0 THEN ABS(expense) ELSE 0 END) as total_revenue,
                SUM(CASE WHEN expense > 0 THEN expense ELSE 0 END) as total_expenses,
                SUM(gross_amount) as total_gross,
                SUM(net_amount) as total_net
            FROM receipts 
            WHERE created_from_banking = true 
            GROUP BY category 
            ORDER BY total_revenue DESC
        """)
        
        print(f"\n=== ENHANCED REVENUE SUMMARY ===")
        print(f"{'Category':<15} {'Transactions':<12} {'Revenue':<12} {'Expenses':<12} {'Gross':<12} {'Net':<12}")
        print("-" * 80)
        
        total_revenue = 0
        total_expenses = 0
        
        for row in cur.fetchall():
            category, transactions, revenue, expenses, gross, net = row
            total_revenue += revenue or 0
            total_expenses += expenses or 0
            print(f"{category:<15} {transactions:<12} ${revenue or 0:<11,.0f} ${expenses or 0:<11,.0f} ${gross or 0:<11,.0f} ${net or 0:<11,.0f}")
        
        print("-" * 80)
        print(f"{'TOTALS':<15} {'':<12} ${total_revenue:<11,.0f} ${total_expenses:<11,.0f}")
        
        # Net position
        net_position = total_revenue - total_expenses
        print(f"\nNet Banking Position: ${net_position:,.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error getting final status: {e}")
    
    print(f"\n[OK] ENHANCED BANKING IMPORT COMPLETE!")
    print(f"All revenue and expense amounts are now properly tracked in gross_amount and net_amount columns.")

if __name__ == "__main__":
    main()