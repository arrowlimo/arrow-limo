#!/usr/bin/env python3
"""
Import verified Scotia 2013-2014 transactions and reconcile with receipts.

Steps:
1. Load verified Excel file (2013_scotia_transactions_for_editingfinal.xlsx)
2. Delete all existing 2013-2014 Scotia banking transactions
3. Import new verified transactions
4. Map to existing receipts
5. Remove duplicates
6. Export all 2012-2014 receipts
"""

import pandas as pd
import psycopg2
import os
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

XLSX_FILE = "L:/limo/data/2013_scotia_transactions_for_editingfinal.xlsx"
SCOTIA_ACCOUNT = '903990106011'

def load_verified_transactions():
    """Load verified Scotia transactions from Excel"""
    print(f"📂 Loading verified transactions...")
    df = pd.read_excel(XLSX_FILE, sheet_name=0)
    print(f"✅ Loaded {len(df)} transactions")
    print(f"   Columns: {list(df.columns)}")
    
    # Show date range
    df['date'] = pd.to_datetime(df['date'])
    print(f"   Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    
    return df

def delete_existing_scotia_2013_2014(cur, conn):
    """Delete existing Scotia 2013-2014 banking transactions"""
    print(f"\n🗑️  Deleting existing Scotia 2013-2014 banking transactions...")
    
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s
          AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
    """, (SCOTIA_ACCOUNT,))
    count = cur.fetchone()[0]
    print(f"   Found {count} existing records to delete")
    
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = %s
          AND EXTRACT(YEAR FROM transaction_date) IN (2013, 2014)
    """, (SCOTIA_ACCOUNT,))
    
    conn.commit()
    print(f"✅ Deleted {cur.rowcount} banking transactions")

def import_verified_transactions(df, cur, conn):
    """Import verified transactions into banking_transactions"""
    print(f"\n📝 Importing {len(df)} verified transactions...")
    
    inserted = 0
    errors = 0
    
    for idx, row in df.iterrows():
        try:
            transaction_date = pd.to_datetime(row['date']).date()
            description = str(row['Description']).strip() if pd.notna(row['Description']) else ''
            debit_amount = float(row['debit/withdrawal']) if pd.notna(row['debit/withdrawal']) else None
            credit_amount = float(row['deposit/credit']) if pd.notna(row['deposit/credit']) else None
            balance = float(row['balance']) if pd.notna(row['balance']) else None
            
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number, transaction_date, description,
                    debit_amount, credit_amount, balance,
                    source_file, import_batch, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                SCOTIA_ACCOUNT,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance,
                'verified_2013_2014_scotia',
                'scotia_verified_import_2025_12_15'
            ))
            inserted += 1
            
            if inserted % 200 == 0:
                print(f"   Imported {inserted}/{len(df)}...")
                conn.commit()
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"⚠️  Row {idx}: {e}")
    
    conn.commit()
    print(f"✅ Import complete: {inserted} inserted, {errors} errors")
    
    return inserted

def map_to_receipts_and_remove_duplicates(cur, conn):
    """Map banking transactions to receipts and remove duplicates"""
    print(f"\n🔗 Mapping banking transactions to receipts...")
    
    # Match by date and amount (debit = receipt amount)
    cur.execute("""
        WITH matched_receipts AS (
            SELECT DISTINCT ON (r.receipt_id)
                r.receipt_id,
                bt.transaction_id,
                r.receipt_date,
                r.vendor_name,
                r.gross_amount,
                bt.description,
                bt.debit_amount
            FROM receipts r
            JOIN banking_transactions bt 
                ON r.receipt_date = bt.transaction_date
                AND ABS(r.gross_amount - bt.debit_amount) < 0.01
            WHERE bt.account_number = %s
              AND EXTRACT(YEAR FROM bt.transaction_date) IN (2013, 2014)
              AND r.mapped_bank_account_id = 2
            ORDER BY r.receipt_id, bt.transaction_id
        )
        SELECT COUNT(*) FROM matched_receipts
    """, (SCOTIA_ACCOUNT,))
    
    matches = cur.fetchone()[0]
    print(f"   Found {matches} receipt-banking matches")
    
    # Update receipts with banking_transaction_id
    cur.execute("""
        UPDATE receipts r
        SET banking_transaction_id = matched.transaction_id
        FROM (
            SELECT DISTINCT ON (r.receipt_id)
                r.receipt_id,
                bt.transaction_id
            FROM receipts r
            JOIN banking_transactions bt 
                ON r.receipt_date = bt.transaction_date
                AND ABS(r.gross_amount - bt.debit_amount) < 0.01
            WHERE bt.account_number = %s
              AND EXTRACT(YEAR FROM bt.transaction_date) IN (2013, 2014)
              AND r.mapped_bank_account_id = 2
            ORDER BY r.receipt_id, bt.transaction_id
        ) matched
        WHERE r.receipt_id = matched.receipt_id
    """, (SCOTIA_ACCOUNT,))
    
    conn.commit()
    print(f"✅ Mapped {cur.rowcount} receipts to banking transactions")
    
    # Find and remove duplicate receipts
    print(f"\n🔍 Checking for duplicate receipts...")
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                ROW_NUMBER() OVER (
                    PARTITION BY receipt_date, vendor_name, gross_amount 
                    ORDER BY receipt_id
                ) as rn
            FROM receipts
            WHERE mapped_bank_account_id = 2
              AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2013, 2014)
        )
        SELECT COUNT(*) FROM duplicates WHERE rn > 1
    """)
    
    dup_count = cur.fetchone()[0]
    
    if dup_count > 0:
        print(f"   Found {dup_count} duplicate receipts - removing...")
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id IN (
                SELECT receipt_id FROM (
                    SELECT 
                        receipt_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY receipt_date, vendor_name, gross_amount 
                            ORDER BY receipt_id
                        ) as rn
                    FROM receipts
                    WHERE mapped_bank_account_id = 2
                      AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2013, 2014)
                ) sub WHERE rn > 1
            )
        """)
        conn.commit()
        print(f"✅ Removed {cur.rowcount} duplicate receipts")
    else:
        print(f"✅ No duplicates found")

def export_all_receipts_2012_2014(cur):
    """Export all receipts from 2012-2014"""
    print(f"\n📊 Exporting all 2012-2014 receipts...")
    
    # Get all columns from receipts table
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in cur.fetchall()]
    
    # Get all receipts 2012-2014
    columns_str = ', '.join(columns)
    cur.execute(f"""
        SELECT {columns_str}
        FROM receipts
        WHERE mapped_bank_account_id = 2
          AND EXTRACT(YEAR FROM receipt_date) IN (2012, 2013, 2014)
        ORDER BY receipt_date ASC, receipt_id ASC
    """)
    
    rows = cur.fetchall()
    print(f"✅ Found {len(rows)} receipts")
    
    # Create DataFrame
    df = pd.DataFrame(rows, columns=columns)
    
    # Convert all datetime columns to naive (remove timezone)
    for col in df.columns:
        if df[col].dtype == 'object':
            # Try to detect datetime objects
            try:
                if pd.api.types.is_datetime64_any_dtype(pd.to_datetime(df[col], errors='coerce')):
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    if df[col].dt.tz is not None:
                        df[col] = df[col].dt.tz_localize(None)
            except:
                pass
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
                if hasattr(df[col].dt, 'tz') and df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)
            except:
                pass
    
    # Export to Excel
    output_file = "L:/limo/reports/scotia_receipts_2012_2014_complete.xlsx"
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"📁 Exported: {output_file}")
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"RECEIPT SUMMARY BY YEAR")
    print(f"{'='*80}")
    
    for year in [2012, 2013, 2014]:
        year_df = df[pd.to_datetime(df['receipt_date'], errors='coerce').dt.year == year]
        if 'gross_amount' in df.columns:
            # Convert to numeric if it's not already
            year_df_amount = pd.to_numeric(year_df['gross_amount'], errors='coerce').fillna(0)
            total_amount = year_df_amount.sum()
            print(f"  {year}: {len(year_df)} receipts, ${total_amount:,.2f}")
        else:
            print(f"  {year}: {len(year_df)} receipts")
    
    if 'gross_amount' in df.columns:
        total_amount = pd.to_numeric(df['gross_amount'], errors='coerce').fillna(0).sum()
        print(f"\n  Total: {len(df)} receipts, ${total_amount:,.2f}")
    else:
        print(f"\n  Total: {len(df)} receipts")
    
    return output_file

def main():
    print("="*80)
    print("SCOTIA 2013-2014 VERIFIED IMPORT & RECONCILIATION")
    print("="*80)
    
    # Load verified transactions
    df = load_verified_transactions()
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        # Delete existing 2013-2014
        delete_existing_scotia_2013_2014(cur, conn)
        
        # Import verified transactions
        import_verified_transactions(df, cur, conn)
        
        # Map to receipts and remove duplicates
        map_to_receipts_and_remove_duplicates(cur, conn)
        
        # Export all receipts
        output_file = export_all_receipts_2012_2014(cur)
        
        print(f"\n{'='*80}")
        print(f"✅ COMPLETE - All 2012-2014 receipts exported to:")
        print(f"   {output_file}")
        print(f"{'='*80}")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
