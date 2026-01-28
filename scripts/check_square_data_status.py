#!/usr/bin/env python3
"""
Check the status of Square data in the database.
Verify if we have current Square payments, refunds, disputes, and fees.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("SQUARE DATA STATUS CHECK")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check Square payments in payments table
    print("1. SQUARE PAYMENTS (from payments table)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN amount > 0 THEN 1 END) as positive,
            COUNT(CASE WHEN amount < 0 THEN 1 END) as negative,
            MIN(payment_date) as earliest,
            MAX(payment_date) as latest,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_positive,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as total_negative
        FROM payments 
        WHERE square_transaction_id IS NOT NULL
    """)
    
    row = cur.fetchone()
    print(f"Total Square payments: {row[0]:,}")
    print(f"  Positive (charges): {row[1]:,} (${row[5]:,.2f})")
    print(f"  Negative (refunds): {row[2]:,} (${row[6]:,.2f})")
    print(f"  Date range: {row[3]} to {row[4]}")
    print()
    
    # Check if Square-specific tables exist
    print("2. SQUARE-SPECIFIC TABLES")
    print("-" * 80)
    
    square_tables = [
        'square_transactions',
        'square_refunds', 
        'square_disputes',
        'square_fees',
        'square_transactions_staging'
    ]
    
    for table in square_tables:
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = %s
        """, (table,))
        
        exists = cur.fetchone()[0] > 0
        
        if exists:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"✓ {table}: EXISTS ({count:,} rows)")
                
                # Try to get date range if table has date column
                date_columns = ['transaction_date', 'refund_date', 'dispute_date', 'fee_date', 'created_at']
                for col in date_columns:
                    try:
                        cur.execute(f"SELECT MIN({col}), MAX({col}) FROM {table} WHERE {col} IS NOT NULL")
                        min_date, max_date = cur.fetchone()
                        if min_date:
                            print(f"  Date range: {min_date} to {max_date}")
                            break
                    except:
                        continue
                        
            except Exception as e:
                print(f"✓ {table}: EXISTS (error reading: {e})")
        else:
            print(f"✗ {table}: DOES NOT EXIST")
    
    print()
    
    # Check for recent Square activity
    print("3. RECENT SQUARE ACTIVITY (Last 30 days)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            DATE(payment_date) as date,
            COUNT(*) as transactions,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as charges,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as refunds
        FROM payments
        WHERE square_transaction_id IS NOT NULL
        AND payment_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(payment_date)
        ORDER BY date DESC
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"{'Date':<12} {'Transactions':<15} {'Charges':<15} {'Refunds':<15}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]!s:<12} {row[1]:<15,} ${row[2]:<14,.2f} ${row[3]:<14,.2f}")
    else:
        print("⚠ NO SQUARE ACTIVITY in last 30 days")
    
    print()
    
    # Check unmatched balances after our fixes
    print("4. CURRENT UNMATCHED BALANCES")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN balance < -100 THEN 1 END) as large_credits,
            COUNT(CASE WHEN balance > 100 THEN 1 END) as large_outstanding,
            SUM(CASE WHEN balance < 0 THEN balance ELSE 0 END) as total_credits,
            SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END) as total_outstanding
        FROM charters
        WHERE cancelled = FALSE
    """)
    
    row = cur.fetchone()
    print(f"Total active charters: {row[0]:,}")
    print(f"  Large credits (< -$100): {row[1]:,} (Total: ${row[3]:,.2f})")
    print(f"  Large outstanding (> $100): {row[2]:,} (Total: ${row[4]:,.2f})")
    print()
    
    # Sample of large credits
    print("5. SAMPLE OF LARGE CREDITS (Top 10)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            total_amount_due,
            paid_amount,
            balance
        FROM charters
        WHERE balance < -100
        AND cancelled = FALSE
        ORDER BY balance ASC
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"{'Reserve':<10} {'Date':<12} {'Due':<12} {'Paid':<12} {'Balance':<12}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]:<10} {row[1]!s:<12} ${row[2]:<11,.2f} ${row[3]:<11,.2f} ${row[4]:<11,.2f}")
    else:
        print("✓ NO LARGE CREDITS found")
    
    print()
    
    # Check for Square payments without reserve numbers
    print("6. SQUARE PAYMENTS WITHOUT RESERVE NUMBERS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as unmatched,
            SUM(amount) as total_amount
        FROM payments
        WHERE square_transaction_id IS NOT NULL
        AND (reserve_number IS NULL OR reserve_number = '')
    """)
    
    row = cur.fetchone()
    amount_str = f"${row[1]:,.2f}" if row[1] else "$0.00"
    print(f"Unmatched Square payments: {row[0]:,} ({amount_str})")
    
    if row[0] > 0:
        print("\nSample unmatched Square payments:")
        cur.execute("""
            SELECT 
                payment_id,
                payment_date,
                amount,
                square_transaction_id,
                notes
            FROM payments
            WHERE square_transaction_id IS NOT NULL
            AND (reserve_number IS NULL OR reserve_number = '')
            ORDER BY payment_date DESC
            LIMIT 5
        """)
        
        for r in cur.fetchall():
            print(f"  Payment {r[0]}: ${r[2]:,.2f} on {r[1]} (Square: {r[3][:20]}...)")
    
    print()
    print("=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    # Determine what needs to be done
    needs_update = []
    
    # Check if Square data is recent
    cur.execute("""
        SELECT MAX(payment_date) 
        FROM payments 
        WHERE square_transaction_id IS NOT NULL
    """)
    latest = cur.fetchone()[0]
    
    if latest:
        days_old = (datetime.now().date() - latest).days
        if days_old > 7:
            needs_update.append(f"⚠ Square data is {days_old} days old - needs update")
    else:
        needs_update.append("⚠ No Square data found - needs initial import")
    
    # Check for missing Square tables
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name IN ('square_refunds', 'square_disputes', 'square_fees')
    """)
    
    if cur.fetchone()[0] < 3:
        needs_update.append("⚠ Missing Square refunds/disputes/fees tables - may need schema creation")
    
    if needs_update:
        for rec in needs_update:
            print(rec)
    else:
        print("✓ Square data appears current and complete")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
