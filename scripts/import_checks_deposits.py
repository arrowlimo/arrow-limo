#!/usr/bin/env python
"""
Import checks and deposits from 2004-2011
"""
import pandas as pd
import psycopg2
from pathlib import Path
from decimal import Decimal

def get_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def import_checks(filepath: Path):
    """Import check details"""
    print(f"\n{'='*80}")
    print(f"IMPORTING CHECKS: {filepath.name}")
    print(f"{'='*80}")
    
    df = pd.read_excel(filepath, header=3)
    print(f"Total rows: {len(df)}")
    
    # Filter valid rows
    df = df[df['Date'].notna() & df['Type'].notna()]
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'] < '2012-01-01']
    
    print(f"Rows in 2004-2011: {len(df)}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for idx, row in df.iterrows():
        try:
            txn_date = row['Date'].date()
            txn_type = str(row['Type'])
            num = str(row['Num']) if pd.notna(row['Num']) else None
            name = str(row['Name']) if pd.notna(row['Name']) else None
            account = str(row['Account']) if pd.notna(row['Account']) else None
            
            # Get amount
            amount = None
            if 'Paid Amount' in row.index and pd.notna(row['Paid Amount']):
                amount = Decimal(str(row['Paid Amount']))
            elif 'Amount' in row.index and pd.notna(row['Amount']):
                amount = Decimal(str(row['Amount']))
            
            if not account or not amount:
                skipped += 1
                continue
            
            # Checks are debits (payments out)
            cur.execute("""
                INSERT INTO general_ledger (
                    date, transaction_type, num, name,
                    account, debit, source_file, imported_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (txn_date, txn_type, num, name, account, amount, 'QB:check_details'))
            
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"  [WARN] Row {idx}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    return inserted

def import_deposits(filepath: Path):
    """Import deposit details"""
    print(f"\n{'='*80}")
    print(f"IMPORTING DEPOSITS: {filepath.name}")
    print(f"{'='*80}")
    
    df = pd.read_excel(filepath, header=3)
    print(f"Total rows: {len(df)}")
    
    df = df[df['Date'].notna() & df['Type'].notna()]
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'] < '2012-01-01']
    
    print(f"Rows in 2004-2011: {len(df)}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for idx, row in df.iterrows():
        try:
            txn_date = row['Date'].date()
            txn_type = str(row['Type'])
            num = str(row['Num']) if pd.notna(row['Num']) else None
            name = str(row['Name']) if pd.notna(row['Name']) else None
            account = str(row['Account']) if pd.notna(row['Account']) else None
            
            amount = None
            if 'Amount' in row.index and pd.notna(row['Amount']):
                amount = Decimal(str(row['Amount']))
            
            if not account or not amount:
                skipped += 1
                continue
            
            # Deposits are credits (money in)
            cur.execute("""
                INSERT INTO general_ledger (
                    date, transaction_type, num, name,
                    account, credit, source_file, imported_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (txn_date, txn_type, num, name, account, amount, 'QB:deposit_details'))
            
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"  [WARN] Row {idx}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    return inserted

def main():
    print("IMPORTING CHECKS AND DEPOSITS (2004-2011)")
    print("="*80)
    
    base = Path("L:/limo/quickbooks/old quickbooks")
    total = 0
    
    checks_file = base / "initial check details.xlsx"
    if checks_file.exists():
        total += import_checks(checks_file)
    
    deposits_file = base / "initial deposts.xlsx"
    if deposits_file.exists():
        total += import_deposits(deposits_file)
    
    print(f"\n{'='*80}")
    print(f"IMPORT COMPLETE: {total:,} records added")
    print(f"{'='*80}")

if __name__ == '__main__':
    main()
