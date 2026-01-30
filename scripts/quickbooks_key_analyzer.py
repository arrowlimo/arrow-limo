import pandas as pd
import psycopg2
from pathlib import Path
import time
import os
import hashlib
from datetime import datetime

def main():
    print("QuickBooks Key Data Analyzer")
    print("==========================")
    
    # Look at the largest QuickBooks files
    print("\nAnalyzing largest journal files...")
    journal_files = [
        "L:/limo/quickbooks/Arrow Limousine backup 2025_Journal.xlsx",  # 81,671 rows
        "L:/limo/quickbooks/medium Arrow Limousine_Transaction Detail by Account.xlsx",  # 46,326 rows
        "L:/limo/quickbooks/general ledger2.xlsx"  # 2,248 rows
    ]
    
    # Create output directory
    report_path = Path('L:/limo/reports/missing_data')
    report_path.mkdir(parents=True, exist_ok=True)
    
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
    
    # Check journal structure
    print("\nExamining journal table structure...")
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal'")
    columns = [row[0] for row in cur.fetchall()]
    print(f"Journal table columns: {', '.join(columns)}")
    
    # Get journal data stats
    cur.execute("SELECT COUNT(*) FROM journal")
    journal_count = cur.fetchone()[0]
    print(f"Journal entries in database: {journal_count}")
    
    if journal_count > 0:
        cur.execute("SELECT MIN(\"Date\"), MAX(\"Date\") FROM journal WHERE \"Date\" IS NOT NULL")
        date_range = cur.fetchone()
        if date_range[0]:
            print(f"Journal date range: {date_range[0]} to {date_range[1]}")
    
    # Check samples from each file to compare with database
    for file_path in journal_files:
        analyze_journal_file(Path(file_path), conn, report_path)
    
    print("\nAnalysis complete!")
    conn.close()

def analyze_journal_file(file_path, conn, report_path):
    """Analyze a journal file and compare with database"""
    print(f"\nAnalyzing {file_path.name}...")
    start_time = time.time()
    
    try:
        # Read file
        print("Loading file...")
        df = pd.read_excel(file_path)
        print(f"File has {len(df)} rows and {len(df.columns)} columns")
        
        # Print column names
        print("Column names:")
        for i, col in enumerate(df.columns):
            print(f"  {i}: {col}")
        
        # Try to locate key columns
        date_col = None
        debit_col = None
        credit_col = None
        account_col = None
        memo_col = None
        name_col = None
        
        # Look for key columns by name patterns
        for col in df.columns:
            col_str = str(col).lower()
            if 'date' in col_str:
                date_col = col
            elif 'debit' in col_str:
                debit_col = col
            elif 'credit' in col_str:
                credit_col = col
            elif 'account' in col_str:
                account_col = col
            elif any(term in col_str for term in ['memo', 'desc', 'note']):
                memo_col = col
            elif any(term in col_str for term in ['name', 'payee', 'vendor']):
                name_col = col
        
        # Print identified columns
        print("\nIdentified columns:")
        print(f"Date column: {date_col}")
        print(f"Debit column: {debit_col}")
        print(f"Credit column: {credit_col}")
        print(f"Account column: {account_col}")
        print(f"Memo column: {memo_col}")
        print(f"Name column: {name_col}")
        
        # If headers are not in first row, they might be in rows 1-5
        if not date_col:
            print("\nSearching for headers in first few rows...")
            for i in range(min(5, len(df))):
                row = df.iloc[i]
                for j, val in enumerate(row):
                    val_str = str(val).lower()
                    if 'date' in val_str:
                        print(f"Possible date header at row {i}, col {j}: {val}")
                    elif any(term in val_str for term in ['debit', 'amount']):
                        print(f"Possible debit header at row {i}, col {j}: {val}")
                    elif 'credit' in val_str:
                        print(f"Possible credit header at row {i}, col {j}: {val}")
        
        # Look at sample data
        print("\nSample data from file:")
        for i in range(min(5, len(df))):
            print(f"Row {i}: {df.iloc[i].tolist()}")
        
        # Get the data shape and structure
        cols_with_data = []
        for col in df.columns:
            non_null = df[col].count()
            percent_filled = non_null / len(df) * 100 if len(df) > 0 else 0
            if percent_filled > 5:  # More than 5% of rows have data
                cols_with_data.append((col, non_null, percent_filled))
        
        print("\nColumns with data:")
        for col, non_null, percent in cols_with_data:
            print(f"  {col}: {non_null} non-null values ({percent:.1f}%)")
        
        # Extract date range if possible
        if date_col and df[date_col].count() > 0:
            try:
                min_date = pd.to_datetime(df[date_col].min())
                max_date = pd.to_datetime(df[date_col].max())
                print(f"\nDate range in file: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
                
                # Check if these dates exist in database
                cur = conn.cursor()
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM journal 
                    WHERE "Date" >= %s AND "Date" <= %s
                """, (min_date.strftime('%Y-%m-%d'), max_date.strftime('%Y-%m-%d')))
                db_count = cur.fetchone()[0]
                print(f"Journal entries in database for this date range: {db_count}")
                
                # Compare counts
                if len(df) > db_count * 1.2:  # 20% more entries in file than DB
                    print(f"WARNING: File has {len(df)} entries but database only has {db_count} entries for this date range")
                    print("This suggests data might be missing from the database")
            except Exception as e:
                print(f"Error analyzing date range: {str(e)}")
        
        # Extract the structure of the file
        try:
            # Save file structure report
            structure_report = pd.DataFrame({
                'Column': df.columns,
                'Non-Null Count': [df[col].count() for col in df.columns],
                'Percent Filled': [df[col].count() / len(df) * 100 if len(df) > 0 else 0 for col in df.columns],
                'Data Type': [str(df[col].dtype) for col in df.columns],
                'Sample Values': [', '.join([str(x) for x in df[col].dropna().head(3).tolist()]) for col in df.columns]
            })
            
            report_file = report_path / f"{file_path.stem}_structure.csv"
            structure_report.to_csv(report_file, index=False)
            print(f"\nFile structure report saved to {report_file}")
        except Exception as e:
            print(f"Error creating structure report: {str(e)}")
        
        print(f"\nAnalysis completed in {time.time() - start_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error analyzing file: {str(e)}")

if __name__ == "__main__":
    main()