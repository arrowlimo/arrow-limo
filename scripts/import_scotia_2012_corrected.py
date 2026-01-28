#!/usr/bin/env python3
"""
Import corrected Scotia 2012 receipts from Excel and REPLACE all existing
Scotia 2012 receipts in the database.

File: data/2012_scotia_transactions_for_editing.xlsx
This file has columns: date, Description, debit/withdrawal, deposit/credit, balance
"""

import pandas as pd
import psycopg2
import os
import sys
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

SCOTIA_ACCOUNT_ID = 2  # Scotia Bank
XLSX_FILE = "L:\\limo\\data\\2012_scotia_transactions_for_editing.xlsx"

def load_excel_data():
    """Load corrected Scotia 2012 data from Excel"""
    print(f"📂 Loading {XLSX_FILE}...")
    try:
        df = pd.read_excel(XLSX_FILE, sheet_name=0)
        print(f"✅ Loaded {len(df)} rows")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Data types:\n{df.dtypes}")
        return df
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")
        sys.exit(1)

def delete_existing_scotia_2012(cur, conn):
    """Delete all existing Scotia 2012 receipts from database"""
    print("\n🗑️  Deleting existing Scotia 2012 receipts...")
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
          AND mapped_bank_account_id = %s
    """, (SCOTIA_ACCOUNT_ID,))
    count = cur.fetchone()[0]
    print(f"   Found {count} existing records to replace")
    
    cur.execute("""
        DELETE FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
          AND mapped_bank_account_id = %s
    """, (SCOTIA_ACCOUNT_ID,))
    
    conn.commit()
    print(f"✅ Deleted {cur.rowcount} records")

def normalize_column_names(df):
    """Normalize column names"""
    pass

def insert_scotia_2012_receipts(df, cur, conn):
    """Insert corrected Scotia 2012 receipts into database"""
    print(f"\n📝 Importing {len(df)} corrected receipts...")
    
    inserted = 0
    errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Parse date
            receipt_date = pd.to_datetime(row['date']).date()
            
            # Description becomes vendor_name (it's the transaction description)
            vendor_name = str(row['Description']).strip() if pd.notna(row['Description']) else 'Unknown'
            
            # Use debit or credit amount (whichever is populated)
            amount = None
            if pd.notna(row['debit/withdrawal']) and row['debit/withdrawal'] != 0:
                amount = float(row['debit/withdrawal'])
                payment_method = 'cheque'  # Debits are typically cheques
            elif pd.notna(row['deposit/credit']) and row['deposit/credit'] != 0:
                amount = float(row['deposit/credit'])
                payment_method = 'deposit'
            else:
                amount = 0.0
                payment_method = 'unknown'
            
            if amount is None or amount == 0:
                errors += 1
                continue
            
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date, vendor_name, receipt_amount, description,
                    payment_method, mapped_bank_account_id,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                receipt_date, vendor_name, abs(amount), f"Scotia 2012 banking transaction",
                payment_method, SCOTIA_ACCOUNT_ID
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"   Inserted {inserted} records...")
                
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"⚠️  Row {idx}: {e}")
    
    conn.commit()
    print(f"\n✅ Import complete:")
    print(f"   Inserted: {inserted}")
    print(f"   Skipped/Errors: {errors}")
    print(f"   Total rows: {len(df)}")
    
    return inserted, errors

def verify_import(cur):
    """Verify import was successful"""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    cur.execute("""
        SELECT COUNT(*) as total,
               MIN(receipt_date) as earliest,
               MAX(receipt_date) as latest,
               SUM(CAST(receipt_amount AS DECIMAL)) as total_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
          AND mapped_bank_account_id = %s
    """, (SCOTIA_ACCOUNT_ID,))
    
    result = cur.fetchone()
    print(f"\nScotia 2012 receipts in database:")
    print(f"  Total records: {result[0]}")
    print(f"  Date range: {result[1]} to {result[2]}")
    print(f"  Total amount: ${result[3]:,.2f}" if result[3] else "  Total amount: $0.00")
    
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, receipt_amount, payment_method
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
          AND mapped_bank_account_id = %s
        ORDER BY receipt_date ASC
        LIMIT 5
    """, (SCOTIA_ACCOUNT_ID,))
    
    print(f"\n  Sample records (first 5):")
    for row in cur.fetchall():
        print(f"    ID {row[0]}: {row[1]} | {row[2]} | ${row[3]:,.2f} | {row[4]}")

def main():
    print("=" * 80)
    print("SCOTIA 2012 RECEIPT IMPORT - REPLACE ALL")
    print("=" * 80)
    
    # Load Excel data
    df = load_excel_data()
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)
    
    try:
        # Delete existing Scotia 2012 records
        delete_existing_scotia_2012(cur, conn)
        
        # Import corrected records
        inserted, errors = insert_scotia_2012_receipts(df, cur, conn)
        
        # Verify
        verify_import(cur)
        
        if errors == 0:
            print("\n✅ ALL SCOTIA 2012 RECEIPTS SUCCESSFULLY REPLACED!")
        else:
            print(f"\n⚠️  Import complete with {errors} records skipped")
    
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
