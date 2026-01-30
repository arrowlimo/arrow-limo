import pandas as pd
import psycopg2
from pathlib import Path
import time
import os
import hashlib
from datetime import datetime

def main():
    print("QuickBooks Missing Data Analyzer")
    print("===============================")
    
    # Configure paths and settings
    qb_path = Path('L:/limo/quickbooks')
    if not qb_path.exists():
        print(f"QuickBooks directory not found at {qb_path}")
        print("Searching for QuickBooks files in workspace...")
        qb_path = Path('L:/limo')
    
    report_path = Path('L:/limo/reports/missing_data')
    report_path.mkdir(parents=True, exist_ok=True)
    
    # Check which QuickBooks files we have
    print("\nScanning directory for QuickBooks files...")
    all_files = []
    for extension in ['.xls', '.xlsx', '.csv']:
        all_files.extend(list(qb_path.glob(f'**/*{extension}')))
    print(f"Found {len(all_files)} potential QuickBooks files")
    
    # Find all Excel and CSV files
    print("\nCategorizing files...")
    for file in all_files[:10]:  # Just show the first 10
        print(f"- {file.relative_to(qb_path) if file.is_relative_to(qb_path) else file.name}")
    
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
    
    # Analyze QuickBooks files
    analyze_quickbooks_files(all_files, conn, report_path)
    
    print("\nAnalysis complete!")
    conn.close()

def analyze_quickbooks_files(files, conn, report_path):
    print("\nAnalyzing QuickBooks files...")
    
    # Create reports dataframe
    file_reports = []
    missing_data = []
    
    # Process each file
    for i, file_path in enumerate(files[:20]):  # Process the first 20 files as a sample
        try:
            print(f"[{i+1}/20] Processing {file_path.name}...")
            start_time = time.time()
            
            # Read file
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                try:
                    df = pd.read_excel(file_path)
                    file_type = 'Excel'
                except Exception as e:
                    print(f"  Error reading Excel file: {str(e)}")
                    file_reports.append({
                        'file_name': file_path.name,
                        'file_path': str(file_path),
                        'file_type': 'Excel',
                        'rows': 0,
                        'columns': 0,
                        'status': f"Error: {str(e)}",
                        'processing_time': time.time() - start_time
                    })
                    continue
            elif file_path.suffix.lower() == '.csv':
                try:
                    df = pd.read_csv(file_path)
                    file_type = 'CSV'
                except Exception as e:
                    print(f"  Error reading CSV file: {str(e)}")
                    file_reports.append({
                        'file_name': file_path.name,
                        'file_path': str(file_path),
                        'file_type': 'CSV',
                        'rows': 0,
                        'columns': 0,
                        'status': f"Error: {str(e)}",
                        'processing_time': time.time() - start_time
                    })
                    continue
            else:
                continue
            
            # Basic file stats
            row_count = len(df)
            col_count = len(df.columns)
            print(f"  File has {row_count} rows and {col_count} columns")
            
            # Get column names
            columns = list(df.columns)
            print(f"  Columns: {', '.join(str(c) for c in columns[:5])}...")
            
            # Sample data from the file
            sample_data = []
            if not df.empty:
                sample_row = df.iloc[0].to_dict()
                for k, v in sample_row.items():
                    sample_data.append(f"{k}: {v}")
            
            # Try to determine file category and check for missing data
            file_category = categorize_file(file_path.name, columns)
            print(f"  Category: {file_category}")
            
            # Add file report
            file_reports.append({
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': file_type,
                'file_category': file_category,
                'rows': row_count,
                'columns': col_count,
                'column_names': "; ".join(str(c) for c in columns),
                'sample_data': "; ".join(sample_data[:5]),
                'status': 'Processed',
                'processing_time': time.time() - start_time
            })
            
            # Check if data might be missing from database
            if file_category and row_count > 0:
                check_missing_data(conn, df, file_path.name, file_category, missing_data)
            
            print(f"  Processed in {time.time() - start_time:.2f} seconds")
            
        except Exception as e:
            print(f"  Error processing file {file_path.name}: {str(e)}")
            file_reports.append({
                'file_name': file_path.name,
                'file_path': str(file_path),
                'rows': 0,
                'columns': 0,
                'status': f"Error: {str(e)}",
                'processing_time': 0
            })
    
    # Save reports to CSV
    df_reports = pd.DataFrame(file_reports)
    df_reports.to_csv(report_path / 'file_analysis_report.csv', index=False)
    print(f"\nFile analysis report saved to {report_path / 'file_analysis_report.csv'}")
    
    if missing_data:
        df_missing = pd.DataFrame(missing_data)
        df_missing.to_csv(report_path / 'missing_data_report.csv', index=False)
        print(f"Missing data report saved to {report_path / 'missing_data_report.csv'}")

def categorize_file(file_name, columns):
    """Categorize the file based on name and columns"""
    file_name_lower = file_name.lower()
    columns_lower = [str(c).lower() for c in columns]
    
    # Detect file type by name
    if any(term in file_name_lower for term in ['journal', 'general_ledger']):
        return 'Journal'
    elif any(term in file_name_lower for term in ['payroll', 'pay']):
        return 'Payroll'
    elif any(term in file_name_lower for term in ['account', 'chart']):
        return 'Accounts'
    elif any(term in file_name_lower for term in ['vendor', 'supplier']):
        return 'Vendors'
    elif any(term in file_name_lower for term in ['customer', 'client']):
        return 'Customers'
    elif any(term in file_name_lower for term in ['invoice', 'bill']):
        return 'Invoices'
    elif any(term in file_name_lower for term in ['receipt']):
        return 'Receipts'
    
    # Try to detect by columns
    if any('journal' in c for c in columns_lower) or ('debit' in columns_lower and 'credit' in columns_lower):
        return 'Journal'
    elif any('pay' in c for c in columns_lower) or any('salary' in c for c in columns_lower):
        return 'Payroll'
    elif any('account' in c for c in columns_lower):
        return 'Accounts'
    elif any('vendor' in c for c in columns_lower):
        return 'Vendors'
    elif any('customer' in c for c in columns_lower) or any('client' in c for c in columns_lower):
        return 'Customers'
    elif any('invoice' in c for c in columns_lower):
        return 'Invoices'
    elif any('receipt' in c for c in columns_lower):
        return 'Receipts'
    
    return 'Unknown'

def check_missing_data(conn, df, file_name, file_category, missing_data):
    """Check if data in the file might be missing from the database"""
    cur = conn.cursor()
    
    if file_category == 'Journal':
        # Check if this journal entry exists in database
        # First, find date and amount columns
        date_col = None
        amount_col = None
        name_col = None
        memo_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'date' in col_lower:
                date_col = col
            elif any(term in col_lower for term in ['amount', 'debit', 'credit', 'total']):
                amount_col = col
            elif any(term in col_lower for term in ['name', 'vendor', 'payee']):
                name_col = col
            elif any(term in col_lower for term in ['memo', 'desc', 'note']):
                memo_col = col
        
        if date_col:
            # Get date range in file
            try:
                min_date = pd.to_datetime(df[date_col].min()).strftime('%Y-%m-%d')
                max_date = pd.to_datetime(df[date_col].max()).strftime('%Y-%m-%d')
                
                # Check if these dates exist in the journal table
                cur.execute("SELECT COUNT(*) FROM journal WHERE \"Date\" >= %s AND \"Date\" <= %s", (min_date, max_date))
                count = cur.fetchone()[0]
                
                # If there are significantly fewer entries in the database than in the file
                if count < len(df) * 0.5:  # Less than 50% match
                    missing_data.append({
                        'file_name': file_name,
                        'category': file_category,
                        'date_range': f"{min_date} to {max_date}",
                        'file_entries': len(df),
                        'db_entries': count,
                        'missing_percentage': round((len(df) - count) / len(df) * 100 if len(df) > 0 else 0, 2),
                        'recommendation': 'Check for missing journal entries'
                    })
            except:
                pass
    
    # Similar checks for other categories
    elif file_category == 'Payroll':
        pass  # Implement payroll check
    
    elif file_category == 'Invoices':
        pass  # Implement invoice check
    
    elif file_category == 'Receipts':
        pass  # Implement receipts check

if __name__ == "__main__":
    main()