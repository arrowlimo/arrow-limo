#!/usr/bin/env python
"""
Import missing 2004-2011 QuickBooks data into almsdata.general_ledger

Priority order:
1. initial journal.xlsx - Most complete, balanced (2007-2011)
2. initial adjusted journal entries.xlsx - Balanced (2005-2011)
3. initial check details.xlsx - Payment details (2004-2011)
4. initial deposits.xlsx - Deposit details (2005-2011)
5. initial tax agency detail report.xlsx - Tax data (2006-2011)
"""
import pandas as pd
import psycopg2
from pathlib import Path
from datetime import datetime
from decimal import Decimal

def get_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def import_journal_entries(filepath: Path, source_label: str):
    """Import from initial journal.xlsx"""
    print(f"\n{'='*80}")
    print(f"IMPORTING: {filepath.name}")
    print(f"{'='*80}")
    
    # Read with proper header (row 3)
    df = pd.read_excel(filepath, header=3)
    print(f"Total rows: {len(df)}")
    
    # Filter to 2004-2011 only (before current almsdata range)
    df = df[df['Date'].notna()]
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'] < '2012-01-01']
    
    print(f"Rows in 2004-2011 range: {len(df)}")
    
    if len(df) == 0:
        print("  [WARN] No data in missing period")
        return 0
    
    # Connect to DB
    conn = get_connection()
    cur = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for idx, row in df.iterrows():
        try:
            # Parse values
            txn_date = row['Date'].date() if pd.notna(row['Date']) else None
            txn_type = str(row['Type']) if pd.notna(row['Type']) else None
            num = str(row['Num']) if pd.notna(row['Num']) else None
            name = str(row['Name']) if pd.notna(row['Name']) else None
            memo = str(row['Memo']) if pd.notna(row['Memo']) else None
            account = str(row['Account']) if pd.notna(row['Account']) else None
            
            # Get debit/credit
            debit = None
            credit = None
            if 'Debit' in row.index and pd.notna(row['Debit']):
                debit = Decimal(str(row['Debit']))
            if 'Credit' in row.index and pd.notna(row['Credit']):
                credit = Decimal(str(row['Credit']))
            
            # Skip if no account or no amounts
            if not account or (not debit and not credit):
                skipped += 1
                continue
            
            # Insert into general_ledger
            cur.execute("""
                INSERT INTO general_ledger (
                    date, transaction_type, num, name, memo_description, 
                    account, debit, credit, source_file, imported_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (
                txn_date, txn_type, num, name, memo,
                account, debit, credit, source_label
            ))
            
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"  [WARN] Error on row {idx}: {e}")
            skipped += 1
            continue
    
    conn.commit()
    conn.close()
    
    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    
    return inserted

def import_adjusted_journal_entries(filepath: Path, source_label: str):
    """Import from initial adjusted journal entries.xlsx"""
    print(f"\n{'='*80}")
    print(f"IMPORTING: {filepath.name}")
    print(f"{'='*80}")
    
    df = pd.read_excel(filepath, header=3)
    print(f"Total rows: {len(df)}")
    
    # Filter to 2004-2011
    df = df[df['Date'].notna()]
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'] < '2012-01-01']
    
    print(f"Rows in 2004-2011 range: {len(df)}")
    
    if len(df) == 0:
        print("  [WARN] No data in missing period")
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for idx, row in df.iterrows():
        try:
            txn_date = row['Date'].date() if pd.notna(row['Date']) else None
            num = str(row['Num']) if pd.notna(row['Num']) else None
            name = str(row['Name']) if pd.notna(row['Name']) else None
            memo = str(row['Memo']) if pd.notna(row['Memo']) else None
            account = str(row['Account']) if pd.notna(row['Account']) else None
            
            debit = Decimal(str(row['Debit'])) if pd.notna(row['Debit']) else None
            credit = Decimal(str(row['Credit'])) if pd.notna(row['Credit']) else None
            
            if not account or (not debit and not credit):
                skipped += 1
                continue
            
            cur.execute("""
                INSERT INTO general_ledger (
                    date, transaction_type, num, name, memo_description,
                    account, debit, credit, source_file, imported_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (
                txn_date, 'Adjusting Journal Entry', num, name, memo,
                account, debit, credit, source_label
            ))
            
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"  [WARN] Error on row {idx}: {e}")
            skipped += 1
            continue
    
    conn.commit()
    conn.close()
    
    print(f"  [OK] Inserted: {inserted:,}")
    print(f"  ⏭️  Skipped: {skipped:,}")
    
    return inserted

def verify_import():
    """Verify the import results"""
    print(f"\n{'='*80}")
    print("IMPORT VERIFICATION")
    print(f"{'='*80}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Check new date range
    cur.execute("SELECT MIN(date), MAX(date) FROM general_ledger WHERE date IS NOT NULL")
    min_date, max_date = cur.fetchone()
    print(f"New date range: {min_date} to {max_date}")
    
    # Check total records
    cur.execute("SELECT COUNT(*) FROM general_ledger")
    total = cur.fetchone()[0]
    print(f"Total records: {total:,}")
    
    # Check records by source file
    cur.execute("""
        SELECT source_file, COUNT(*), MIN(date), MAX(date)
        FROM general_ledger
        WHERE source_file IS NOT NULL
        GROUP BY source_file
        ORDER BY MIN(date)
    """)
    
    print(f"\nRecords by source file:")
    for source, count, min_d, max_d in cur.fetchall():
        print(f"  {source}: {count:,} records ({min_d} to {max_d})")
    
    # Check 2004-2011 coverage
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM date) as year,
            COUNT(*) as records
        FROM general_ledger
        WHERE date < '2012-01-01'
        GROUP BY EXTRACT(YEAR FROM date)
        ORDER BY year
    """)
    
    print(f"\nRecords by year (2004-2011):")
    for year, count in cur.fetchall():
        print(f"  {int(year)}: {count:,} records")
    
    conn.close()

def main():
    print("IMPORTING MISSING QUICKBOOKS DATA (2004-2011)")
    print("="*80)
    
    base_path = Path("L:/limo/quickbooks/old quickbooks")
    
    total_inserted = 0
    
    # 1. Import initial journal.xlsx (most complete)
    file1 = base_path / "initial journal.xlsx"
    if file1.exists():
        total_inserted += import_journal_entries(file1, "QB:initial_journal")
    
    # 2. Import adjusted journal entries
    file2 = base_path / "initial adjusted journal entreis.xlsx"
    if file2.exists():
        total_inserted += import_adjusted_journal_entries(file2, "QB:adjusted_journal")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*80}")
    print(f"Total records inserted: {total_inserted:,}")
    
    # Verify
    verify_import()

if __name__ == '__main__':
    main()
