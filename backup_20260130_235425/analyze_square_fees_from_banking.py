#!/usr/bin/env python3
"""
Calculate Square processing fees from banking reconciliation.
Compares Square deposits in banking_transactions to identify fee deductions.
"""

import os
import psycopg2
from decimal import Decimal
from datetime import datetime

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REDACTED***")


def analyze_square_deposits(conn):
    """Analyze Square deposits in banking to calculate fees."""
    cur = conn.cursor()
    
    print("=" * 70)
    print("SQUARE PROCESSING FEE ANALYSIS (from Banking)")
    print("=" * 70)
    
    # Find Square deposits in banking
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            credit_amount,
            transaction_id
        FROM banking_transactions
        WHERE (description ILIKE '%square%' 
           OR description ILIKE '%sqr%'
           OR description ILIKE '%payment%processing%')
        AND credit_amount > 0
        ORDER BY transaction_date
    """)
    
    square_deposits = cur.fetchall()
    
    print(f"\n📋 Found {len(square_deposits)} Square-related deposits in banking")
    
    if len(square_deposits) > 0:
        print(f"\nSample deposits:")
        for i in range(min(5, len(square_deposits))):
            date, desc, amt, txn_id = square_deposits[i]
            print(f"  {date}: ${amt:,.2f} - {desc[:60]}")
    
    # Check if we have Square sales/payment data
    cur.execute("""
        SELECT COUNT(*) 
        FROM payments 
        WHERE payment_method = 'credit_card'
        AND payment_date >= '2020-01-01'
    """)
    
    cc_payments = cur.fetchone()[0]
    print(f"\n💳 Credit card payments in system: {cc_payments:,}")
    
    # Check square-specific tables
    cur.execute("SELECT COUNT(*) FROM square_transactions")
    sq_txns = cur.fetchone()[0]
    
    print(f"📊 Square transactions table: {sq_txns:,} records")
    
    if sq_txns > 0:
        cur.execute("""
            SELECT 
                COUNT(*) as txn_count,
                SUM(gross_sales_money) as gross_sales,
                SUM(net_sales_money) as net_sales,
                SUM(processing_fee_money) as total_fees,
                MIN(created_at::date) as first_txn,
                MAX(created_at::date) as last_txn
            FROM square_transactions
        """)
        
        row = cur.fetchone()
        if row:
            txn_count, gross, net, fees, first, last = row
            print(f"\n✓ Square Transaction Data Available:")
            print(f"  Period: {first} to {last}")
            print(f"  Transactions: {txn_count:,}")
            if gross:
                print(f"  Gross Sales: ${gross:,.2f}")
                print(f"  Net Sales: ${net:,.2f}")
                print(f"  Processing Fees: ${fees:,.2f}")
                print(f"  Effective Rate: {(fees/gross*100):.2f}%")
    
    # Summary
    print(f"\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    if sq_txns > 0:
        print("\n✅ You have Square transaction data!")
        print("   Processing fees are already captured in square_transactions table")
        print("   Run: scripts/import_square_fees_from_transactions.py")
    else:
        print("\n⚠️  No Square transaction detail data found")
        print("   Options:")
        print("   1. Download Square transaction reports from Square Dashboard")
        print("   2. Use Square API to fetch transaction history")  
        print("   3. Estimate fees at ~2.9% + $0.30 per transaction")
    
    cur.close()


def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    try:
        analyze_square_deposits(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
