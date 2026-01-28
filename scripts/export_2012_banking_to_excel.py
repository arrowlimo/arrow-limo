#!/usr/bin/env python3
"""
Export all 2012 banking transactions from almsdata to Excel.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
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
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("📥 Fetching 2012 banking transactions from database...")
    
    cur.execute("""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            category,
            created_at
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
    """)
    
    rows = cur.fetchall()
    
    if not rows:
        print("[FAIL] No 2012 banking transactions found")
        cur.close()
        conn.close()
        return
    
    print(f"✓ Retrieved {len(rows)} transactions")
    
    # Convert to DataFrame
    df = pd.DataFrame(rows)
    
    # Format for Excel readability
    if 'transaction_date' in df.columns:
        df['transaction_date'] = pd.to_datetime(df['transaction_date']).dt.date
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'])
    
    # Create output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'2012_banking_transactions_{timestamp}.xlsx'
    
    print(f"💾 Writing to {output_file}...")
    
    # Write to Excel with formatting
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='2012 Banking', index=False)
        
        # Get the worksheet
        worksheet = writer.sheets['2012 Banking']
        
        # Auto-adjust column widths
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
    
    # Summary stats
    total_debits = df['debit_amount'].sum() if 'debit_amount' in df.columns else 0
    total_credits = df['credit_amount'].sum() if 'credit_amount' in df.columns else 0
    
    print(f"\n[OK] Export complete!")
    print(f"   File: {output_file}")
    print(f"   Records: {len(rows)}")
    print(f"   Date range: {df['transaction_date'].min()} to {df['transaction_date'].max()}")
    print(f"   Total debits: ${total_debits:,.2f}")
    print(f"   Total credits: ${total_credits:,.2f}")
    print(f"   Net: ${total_credits - total_debits:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
