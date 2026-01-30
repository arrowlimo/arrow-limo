import pandas as pd
import psycopg2
from pathlib import Path
import time
import os
import hashlib

def main():
    print("QuickBooks Missing Data Analyzer")
    print("===============================")
    
    # Configure paths and settings
    qb_path = Path('L:/limo/quickbooks')
    report_path = Path('L:/limo/reports/missing_data')
    report_path.mkdir(parents=True, exist_ok=True)
    
    # Check which QuickBooks files we have
    print("\nScanning QuickBooks directory...")
    all_files = list(qb_path.glob('**/*.[xc]*'))
    print(f"Found {len(all_files)} potential QuickBooks files")
    
    # Categorize files
    journal_files = [f for f in all_files if any(x in f.name.lower() for x in ['journal', 'general_ledger'])]
    payroll_files = [f for f in all_files if 'payroll' in f.name.lower()]
    gl_files = [f for f in all_files if any(x in f.name.lower() for x in ['ledger', 'gl', 'general'])]
    
    print(f"Journal files: {len(journal_files)}")
    print(f"Payroll files: {len(payroll_files)}")
    print(f"General Ledger files: {len(gl_files)}")
    
    # Database connection
    print("\nConnecting to database...")
    try:
        conn = psycopg2.connect(
            dbname='almsdata',
            user='postgres',
            password='***REDACTED***',
            host='localhost'
        )
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        return
    
    # Get tables in database
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    db_tables = [row[0] for row in cur.fetchall()]
    print(f"Database tables: {len(db_tables)}")
    print(f"Sample tables: {', '.join(db_tables[:5])}")
    
    # Check if journal exists
    if 'journal' in db_tables:
        check_journal_data(conn, journal_files, report_path)
    else:
        print("No journal table found in database")
        
    # Check if payroll exists
    if 'payroll' in db_tables:
        check_payroll_data(conn, payroll_files, report_path)
    else:
        print("No payroll table found in database")
    
    print("\nAnalysis complete!")

def check_journal_data(conn, journal_files, report_path):
    print("\nAnalyzing journal data...")
    
    # Get column names from database
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal'")
    db_columns = [row[0] for row in cur.fetchall()]
    print(f"Journal table columns: {', '.join(db_columns[:5])}...")
    
    # Extract case-sensitive column names
    date_col = next((col for col in db_columns if col.lower() == 'date'), 'Date')
    amount_col = next((col for col in db_columns if col.lower() == 'amount'), 'Amount')
    name_col = next((col for col in db_columns if col.lower() == 'name'), 'Name')
    memo_col = next((col for col in db_columns if col.lower() == 'memo'), 'Memo')
    
    # Get existing journal entries with correct case
    print("Retrieving journal entries from database...")
    start_time = time.time()
    query = f'SELECT "{date_col}", "{amount_col}", "{name_col}", "{memo_col}" FROM journal'
    try:
        cur.execute(query)
        db_entries = cur.fetchall()
        print(f"Retrieved {len(db_entries)} journal entries in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Error retrieving journal entries: {str(e)}")
        return
    
    # Create lookup set for fast comparison
    print("Building lookup table...")
    start_time = time.time()
    db_lookup = set()
    for entry in db_entries:
        date, amount, name, memo = entry
        key = f"{date}|{amount}|{name or ''}|{memo or ''}"
        db_lookup.add(hashlib.md5(key.encode()).hexdigest())
    print(f"Built lookup table in {time.time() - start_time:.2f} seconds")
    
    # Process a sample of journal files
    print("\nProcessing journal files (limited sample)...")
    missing_entries = []
    
    for i, file_path in enumerate(journal_files[:3]):  # Process just 3 files for now
        try:
            print(f"[{i+1}/3] Processing {file_path.name}...")
            start_time = time.time()
            
            # Read file
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                continue
                
            # Find relevant columns
            print(f"  File has {len(df)} rows and {len(df.columns)} columns")
            
            # Map columns
            file_date_col = None
            file_amount_col = None
            file_name_col = None
            file_memo_col = None
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 'date' in col_lower:
                    file_date_col = col
                elif any(term in col_lower for term in ['amount', 'total', 'sum']):
                    file_amount_col = col
                elif 'name' in col_lower or 'vendor' in col_lower:
                    file_name_col = col
                elif 'memo' in col_lower or 'desc' in col_lower:
                    file_memo_col = col
            
            print(f"  Mapped columns: date={file_date_col}, amount={file_amount_col}, name={file_name_col}, memo={file_memo_col}")
            
            if not file_date_col or not file_amount_col:
                print("  Skipping file - couldn't identify required columns")
                continue
            
            # Check each row
            file_missing = []
            for _, row in df.iterrows():
                try:
                    entry_date = pd.to_datetime(row[file_date_col]).date() if pd.notna(row[file_date_col]) else None
                    entry_amount = float(row[file_amount_col]) if pd.notna(row[file_amount_col]) else 0
                    entry_name = str(row[file_name_col]) if file_name_col and pd.notna(row[file_name_col]) else ''
                    entry_memo = str(row[file_memo_col]) if file_memo_col and pd.notna(row[file_memo_col]) else ''
                    
                    if not entry_date:
                        continue
                    
                    # Create hash for comparison
                    key = f"{entry_date}|{entry_amount}|{entry_name}|{entry_memo}"
                    entry_hash = hashlib.md5(key.encode()).hexdigest()
                    
                    # Check if in database
                    if entry_hash not in db_lookup:
                        file_missing.append({
                            'file': file_path.name,
                            'date': entry_date,
                            'amount': entry_amount,
                            'name': entry_name,
                            'memo': entry_memo
                        })
                except Exception as e:
                    print(f"  Error processing row: {str(e)}")
            
            missing_entries.extend(file_missing)
            print(f"  Found {len(file_missing)} missing entries in {time.time() - start_time:.2f} seconds")
            
        except Exception as e:
            print(f"  Error processing file {file_path.name}: {str(e)}")
    
    # Report results
    if missing_entries:
        print(f"\nFound {len(missing_entries)} missing journal entries")
        
        # Save to CSV
        df_missing = pd.DataFrame(missing_entries)
        csv_path = report_path / 'missing_journal_entries.csv'
        df_missing.to_csv(csv_path, index=False)
        print(f"Saved missing entries to {csv_path}")
    else:
        print("No missing journal entries found in sampled files")

def check_payroll_data(conn, payroll_files, report_path):
    print("\nAnalyzing payroll data...")
    # Similar implementation to journal check...
    print("Payroll analysis would go here (skipped for brevity)")

if __name__ == "__main__":
    main()