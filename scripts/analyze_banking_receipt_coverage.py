"""
Analyze Banking Statement Coverage in Receipts Table
=====================================================

Identifies banking transactions (both credits and debits) that don't
have corresponding receipts.

Author: AI Agent
Date: December 19, 2025
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    print("="*70)
    print("BANKING STATEMENT COVERAGE ANALYSIS")
    print("="*70)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Analyze 2012
    year = 2012
    
    print(f"\n{year} Banking Transactions:")
    print("-"*70)
    
    # Credits (deposits)
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(credit_amount) as total_amount,
            COUNT(CASE WHEN transaction_id IN (
                SELECT banking_transaction_id FROM receipts 
                WHERE banking_transaction_id IS NOT NULL
            ) THEN 1 END) as has_receipt
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND credit_amount > 0
    """, (year,))
    
    credits = cur.fetchone()
    print(f"\nCredits (Deposits):")
    print(f"  Total: {credits[0]:,} transactions, ${credits[1]:,.2f}")
    print(f"  Linked to receipts: {credits[2]:,}")
    print(f"  NOT linked: {credits[0] - credits[2]:,}")
    
    # Debits (withdrawals)
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(debit_amount) as total_amount,
            COUNT(CASE WHEN transaction_id IN (
                SELECT banking_transaction_id FROM receipts 
                WHERE banking_transaction_id IS NOT NULL
            ) THEN 1 END) as has_receipt
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND debit_amount > 0
    """, (year,))
    
    debits = cur.fetchone()
    print(f"\nDebits (Withdrawals):")
    print(f"  Total: {debits[0]:,} transactions, ${debits[1]:,.2f}")
    print(f"  Linked to receipts: {debits[2]:,}")
    print(f"  NOT linked: {debits[0] - debits[2]:,}")
    
    # Sample unlinked credits
    print(f"\n{'-'*70}")
    print("Sample Unlinked Credits (first 10):")
    print(f"{'-'*70}")
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            credit_amount,
            category,
            vendor_extracted
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND credit_amount > 0
        AND transaction_id NOT IN (
            SELECT banking_transaction_id FROM receipts 
            WHERE banking_transaction_id IS NOT NULL
        )
        ORDER BY transaction_date
        LIMIT 10
    """, (year,))
    
    for row in cur.fetchall():
        print(f"{row[0]} | {row[1][:50]:50s} | ${row[2]:10,.2f} | {row[3] or 'N/A'}")
    
    # Sample unlinked debits
    print(f"\n{'-'*70}")
    print("Sample Unlinked Debits (first 10):")
    print(f"{'-'*70}")
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            category,
            vendor_extracted
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) = %s 
        AND debit_amount > 0
        AND transaction_id NOT IN (
            SELECT banking_transaction_id FROM receipts 
            WHERE banking_transaction_id IS NOT NULL
        )
        ORDER BY transaction_date
        LIMIT 10
    """, (year,))
    
    for row in cur.fetchall():
        print(f"{row[0]} | {row[1][:50]:50s} | ${row[2]:10,.2f} | {row[3] or 'N/A'}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    print("\nThe receipts table is missing entries for:")
    print("1. Banking CREDITS (deposits, customer payments)")
    print("2. Some banking DEBITS (unlinked withdrawals)")
    print("\nSuggested fix:")
    print("- Create receipts for ALL banking transactions")
    print("- Mark deposits with appropriate category (income/transfer)")
    print("- Ensure complete banking statement coverage")

if __name__ == '__main__':
    main()
