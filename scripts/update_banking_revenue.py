#!/usr/bin/env python3
"""
Update Banking Records - Add revenue tracking via gross_amount column
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

def update_banking_revenue_tracking():
    """Update existing banking records to properly track revenue in gross_amount"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cur = conn.cursor()
        
        print("=== UPDATING BANKING REVENUE TRACKING ===")
        
        # For revenue transactions (negative expense), set gross_amount to the absolute value
        # This represents the gross revenue amount
        cur.execute("""
            UPDATE receipts 
            SET gross_amount = ABS(expense)
            WHERE 
                created_from_banking = true 
                AND expense < 0 
                AND (gross_amount = 0 OR gross_amount IS NULL)
        """)
        
        revenue_updated = cur.rowcount
        
        # For expense transactions (positive expense), leave gross_amount as 0
        # since these are not revenue-generating events
        cur.execute("""
            UPDATE receipts 
            SET gross_amount = 0
            WHERE 
                created_from_banking = true 
                AND expense > 0 
                AND gross_amount != 0
        """)
        
        expense_updated = cur.rowcount
        
        conn.commit()
        
        print(f"[OK] Updated {revenue_updated} revenue records with gross_amount")
        print(f"[OK] Updated {expense_updated} expense records (set gross_amount = 0)")
        
        # Get summary of updates
        cur.execute("""
            SELECT 
                category,
                CASE WHEN expense < 0 THEN 'Revenue' ELSE 'Expense' END as type,
                COUNT(*) as transactions,
                SUM(ABS(expense)) as total_amount,
                SUM(gross_amount) as total_gross
            FROM receipts 
            WHERE created_from_banking = true 
            GROUP BY category, CASE WHEN expense < 0 THEN 'Revenue' ELSE 'Expense' END
            ORDER BY category, type
        """)
        
        print(f"\n=== REVENUE TRACKING SUMMARY ===")
        print(f"{'Category':<15} {'Type':<8} {'Count':<8} {'Amount':<12} {'Gross':<12}")
        print("-" * 65)
        
        total_revenue = 0
        total_expenses = 0
        
        for row in cur.fetchall():
            category, tx_type, count, amount, gross = row
            if tx_type == 'Revenue':
                total_revenue += amount or 0
            else:
                total_expenses += amount or 0
                
            print(f"{category:<15} {tx_type:<8} {count:<8} ${amount or 0:<11,.0f} ${gross or 0:<11,.0f}")
        
        print("-" * 65)
        print(f"{'TOTALS':<24} {'':<8} {'':<12} Revenue: ${total_revenue:,.0f}")
        print(f"{'':>36} Expenses: ${total_expenses:,.0f}")
        print(f"{'':>36} Net: ${total_revenue - total_expenses:,.0f}")
        
        # Show deposit revenue specifically
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts 
            WHERE created_from_banking = true 
            AND category = 'DEPOSITS' 
            AND expense < 0
        """)
        
        deposit_row = cur.fetchone()
        print(f"\n🏦 DEPOSIT REVENUE: {deposit_row[0]} transactions = ${deposit_row[1] or 0:,.2f}")
        
        # Show transfer revenue (e-transfers received)
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts 
            WHERE created_from_banking = true 
            AND category = 'TRANSFERS' 
            AND expense < 0
        """)
        
        transfer_row = cur.fetchone()
        print(f"💸 TRANSFER REVENUE: {transfer_row[0]} transactions = ${transfer_row[1] or 0:,.2f}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"[FAIL] Error updating banking records: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def main():
    print("Banking Revenue Tracking Update")
    print("This will update gross_amount for all banking transactions to properly track revenue.")
    
    if update_banking_revenue_tracking():
        print("\n[OK] BANKING REVENUE TRACKING UPDATE COMPLETE!")
        print("\nNow your receipts table properly tracks:")
        print("  • Revenue transactions: gross_amount = revenue amount, expense = negative")
        print("  • Expense transactions: gross_amount = 0, expense = positive amount") 
        print("  • This maintains Epson compatibility while enabling revenue analysis")
    else:
        print("\n[FAIL] Update failed!")

if __name__ == "__main__":
    main()