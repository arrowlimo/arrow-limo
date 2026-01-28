#!/usr/bin/env python3
"""
Export Scotia Bank transactions for manual editing - 2013, 2014, 2015, 2016, 2017
Creates Excel files with: date, Description, debit/withdrawal, deposit/credit, balance
"""

import pandas as pd
import psycopg2
import os

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

SCOTIA_ACCOUNT_ID = 2  # Scotia Bank account #903990106011
OUTPUT_DIR = "L:/limo/data"

def export_scotia_year(year, cur):
    """Export Scotia banking transactions for a given year"""
    print(f"\n{'='*80}")
    print(f"SCOTIA BANK {year} TRANSACTIONS")
    print(f"{'='*80}")
    
    # Get banking transactions for Scotia account
    cur.execute("""
        SELECT 
            transaction_date as date,
            description as "Description",
            debit_amount as "debit/withdrawal",
            credit_amount as "deposit/credit",
            balance
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
          AND account_number = '903990106011'
        ORDER BY transaction_date ASC, transaction_id ASC
    """, (year,))
    
    rows = cur.fetchall()
    
    if not rows:
        print(f"❌ No transactions found for {year}")
        return None
    
    print(f"✅ Found {len(rows)} transactions")
    
    # Create DataFrame
    df = pd.DataFrame(rows, columns=['date', 'Description', 'debit/withdrawal', 'deposit/credit', 'balance'])
    
    # Calculate totals
    total_debits = df['debit/withdrawal'].sum()
    total_credits = df['deposit/credit'].sum()
    
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"   Total debits: ${total_debits:,.2f}")
    print(f"   Total credits: ${total_credits:,.2f}")
    
    # Export to Excel
    filename = f"{OUTPUT_DIR}/{year}_scotia_transactions_for_editing.xlsx"
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"📁 Exported: {filename}")
    
    return filename

def main():
    print("="*80)
    print("SCOTIA BANK TRANSACTION EXPORT - MULTI-YEAR")
    print("="*80)
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Export each year
    years = [2013, 2014, 2015, 2016, 2017]
    exported_files = []
    
    for year in years:
        filename = export_scotia_year(year, cur)
        if filename:
            exported_files.append(filename)
    
    cur.close()
    conn.close()
    
    # Summary
    print(f"\n{'='*80}")
    print("EXPORT COMPLETE")
    print(f"{'='*80}")
    print(f"\n✅ Exported {len(exported_files)} files:")
    for f in exported_files:
        print(f"   - {os.path.basename(f)}")
    
    if len(exported_files) < len(years):
        print(f"\n⚠️  {len(years) - len(exported_files)} years had no transactions")

if __name__ == "__main__":
    main()
