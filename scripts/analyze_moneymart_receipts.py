"""
Analyze all MoneyMart receipts to prepare for reclassification
MoneyMart Visa card loads should be asset transfers, not expenses
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def analyze_moneymart():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Find all MoneyMart receipts
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            payment_method,
            description,
            gl_account_code,
            comment,
            expense_account,
            is_transfer
        FROM receipts 
        WHERE UPPER(vendor_name) LIKE '%MONEY%MART%' 
           OR UPPER(vendor_name) LIKE '%MONEYMART%'
        ORDER BY receipt_date
    """)
    
    rows = cur.fetchall()
    
    print(f"\n{'='*120}")
    print(f"MONEYMART RECEIPTS ANALYSIS - {len(rows)} transactions found")
    print(f"{'='*120}\n")
    
    total_amount = 0
    category_breakdown = {}
    
    for r in rows:
        receipt_id, receipt_date, vendor_name, gross_amount, category, payment_method, description, gl_code, comment, expense_account, is_transfer = r
        total_amount += float(gross_amount or 0)
        
        cat = category or 'UNCATEGORIZED'
        category_breakdown[cat] = category_breakdown.get(cat, 0) + float(gross_amount or 0)
        
        transfer_flag = '🔄 TRANSFER' if is_transfer else ''
        print(f"ID: {receipt_id:6d} | Date: {receipt_date} | Vendor: {vendor_name[:35]:35s} | "
              f"Amount: ${gross_amount:8.2f} | Cat: {cat:20s} | GL: {gl_code or 'NULL':8s} {transfer_flag}")
        if description:
            print(f"           Desc: {description}")
        if comment:
            print(f"           Comment: {comment}")
        if expense_account:
            print(f"           Expense Acct: {expense_account}")
        print()
    
    print(f"\n{'='*120}")
    print(f"SUMMARY")
    print(f"{'='*120}")
    print(f"Total MoneyMart transactions: {len(rows)}")
    print(f"Total amount: ${total_amount:,.2f}\n")
    
    print("Category Breakdown:")
    for cat, amt in sorted(category_breakdown.items(), key=lambda x: -x[1]):
        print(f"  {cat:30s}: ${amt:10,.2f}")
    
    # Check if GL account for prepaid cards exists
    print(f"\n{'='*120}")
    print("GL ACCOUNT CHECK")
    print(f"{'='*120}")
    
    cur.execute("""
        SELECT account_code, account_name, account_type 
        FROM chart_of_accounts 
        WHERE account_code IN ('1130', '1135', '1200')
        ORDER BY account_code
    """)
    
    gl_accounts = cur.fetchall()
    print("\nRelevant GL accounts for prepaid expenses:")
    for acc in gl_accounts:
        print(f"  {acc[0]} - {acc[1]} ({acc[2]})")
    
    cur.close()
    conn.close()
    
    print(f"\n{'='*120}")
    print("RECOMMENDATION")
    print(f"{'='*120}")
    print("MoneyMart Visa card loads should be reclassified as:")
    print("  GL Code: 1130 (Prepaid Expenses) or create 1135 (Prepaid Visa Cards)")
    print("  Category: 'Prepaid Card Load' or 'Asset Transfer'")
    print("  Nature: Asset transfer (Cash → Prepaid Card), NOT an expense")
    print(f"{'='*120}\n")

if __name__ == "__main__":
    analyze_moneymart()
