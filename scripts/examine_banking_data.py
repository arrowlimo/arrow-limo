#!/usr/bin/env python3
"""
Examine banking transaction storage in receipts table
"""

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("=== CURRENT BANKING TRANSACTION STORAGE ===")
    
    # Check DEPOSITS category
    cur.execute("""
        SELECT vendor_name, expense, gross_amount, net_amount, category, expense_account 
        FROM receipts 
        WHERE created_from_banking = true AND category = 'DEPOSITS' 
        LIMIT 5
    """)
    print("\nDEPOSIT transactions:")
    for row in cur.fetchall():
        print(f"  Vendor: {row[0][:30]}")
        print(f"  Expense: {row[1]}, Gross: {row[2]}, Net: {row[3]}")
        print(f"  Category: {row[4]}, Account: {row[5]}")
        print()
    
    # Check revenue transactions (negative expense)
    cur.execute("""
        SELECT vendor_name, expense, gross_amount, net_amount, category, expense_account 
        FROM receipts 
        WHERE created_from_banking = true AND expense < 0 
        LIMIT 5
    """)
    print("\nRevenue transactions (negative expense):")
    for row in cur.fetchall():
        print(f"  Vendor: {row[0][:30]}")
        print(f"  Expense: {row[1]}, Gross: {row[2]}, Net: {row[3]}")
        print(f"  Category: {row[4]}, Account: {row[5]}")
        print()
    
    # Check positive expenses  
    cur.execute("""
        SELECT vendor_name, expense, gross_amount, net_amount, category, expense_account 
        FROM receipts 
        WHERE created_from_banking = true AND expense > 0 
        LIMIT 5
    """)
    print("\nExpense transactions (positive expense):")
    for row in cur.fetchall():
        print(f"  Vendor: {row[0][:30]}")
        print(f"  Expense: {row[1]}, Gross: {row[2]}, Net: {row[3]}")
        print(f"  Category: {row[4]}, Account: {row[5]}")
        print()
        
    # Summary by category and sign
    cur.execute("""
        SELECT 
            category,
            CASE WHEN expense < 0 THEN 'Revenue' ELSE 'Expense' END as type,
            COUNT(*),
            SUM(expense)
        FROM receipts 
        WHERE created_from_banking = true 
        GROUP BY category, CASE WHEN expense < 0 THEN 'Revenue' ELSE 'Expense' END
        ORDER BY category, type
    """)
    print("\nSUMMARY BY CATEGORY AND TYPE:")
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]}): {row[2]} transactions, Total: ${row[3]:,.2f}")
    
    conn.close()

if __name__ == "__main__":
    main()