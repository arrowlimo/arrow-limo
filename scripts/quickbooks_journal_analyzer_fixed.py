import pandas as pd
import psycopg2
from pathlib import Path
import time
import os
from datetime import datetime

def main():
    print("QuickBooks Journal Data Importer - Fixed")
    print("=====================================")
    
    # Define file paths
    journal_file = Path("L:/limo/quickbooks/Arrow Limousine backup 2025_Journal.xlsx")
    
    if not journal_file.exists():
        print(f"Journal file not found: {journal_file}")
        return
    
    # Create output directory
    report_path = Path('L:/limo/reports/import_results')
    report_path.mkdir(parents=True, exist_ok=True)
    
    # First, analyze the Excel file structure more carefully
    print("\nAnalyzing Excel file structure...")
    analyze_excel_structure(journal_file)
    
    print("\nImporting specific rows and columns...")
    extract_journal_data(journal_file, report_path)
    
    print("\nProcess complete!")

def analyze_excel_structure(file_path):
    """Analyze Excel file structure more carefully"""
    # Read with no header first
    df = pd.read_excel(file_path, header=None)
    
    # Look at first 10 rows to find headers
    print("\nExamining first 10 rows:")
    for i in range(min(10, len(df))):
        row_data = [str(x) if pd.notna(x) else "NaN" for x in df.iloc[i].tolist()]
        print(f"Row {i}: {row_data}")
        
        # Check for common header terms
        if any("transaction date" in str(x).lower() for x in row_data if pd.notna(x)):
            print(f"  --> Possible header row: {i}")

def extract_journal_data(file_path, report_path):
    """Extract journal data with manual column mapping"""
    # Read with header at row 3 (index 3)
    df = pd.read_excel(file_path, header=3)
    
    # Show the first few rows
    print("\nFirst 5 rows with headers from row 3:")
    print(df.head().to_string())
    
    # Show column names
    print("\nColumn names:")
    for i, col in enumerate(df.columns):
        print(f"  {i}: {col}")
    
    # Manual column mapping based on inspection
    column_mapping = {
        'Date': 'Transaction date',
        'Transaction Type': 'Transaction type',
        '#': '#',
        'Name': 'Name',
        'Memo/Description': 'Memo/Description', 
        'Account': 'Account full name',
        'Debit': 'Debit',
        'Credit': 'Credit'
    }
    
    print("\nManual column mapping:")
    for db_col, file_col in column_mapping.items():
        if file_col in df.columns:
            print(f"  {db_col} -> {file_col} (Found)")
        else:
            print(f"  {db_col} -> {file_col} (Not found)")
    
    # Extract just the rows with actual data
    # Filter out header rows and summary rows
    print("\nFiltering data rows...")
    start_time = time.time()
    
    # Convert date column to datetime
    if 'Transaction date' in df.columns:
        df['Transaction date'] = pd.to_datetime(df['Transaction date'], errors='coerce')
        
        # Filter rows with valid dates
        before_count = len(df)
        df = df.dropna(subset=['Transaction date'])
        after_count = len(df)
        print(f"Filtered from {before_count} to {after_count} rows with valid dates")
    
    # Create a new dataframe with just the columns we need
    df_clean = pd.DataFrame()
    
    for db_col, file_col in column_mapping.items():
        if file_col in df.columns:
            df_clean[db_col] = df[file_col]
    
    # Save to CSV for inspection
    csv_file = report_path / "journal_data_clean.csv"
    df_clean.to_csv(csv_file, index=False)
    print(f"\nSaved {len(df_clean)} rows to {csv_file}")
    print(f"Processing completed in {time.time() - start_time:.2f} seconds")
    
    # Count entries by year
    if 'Date' in df_clean.columns:
        df_clean['Year'] = df_clean['Date'].dt.year
        year_counts = df_clean['Year'].value_counts().sort_index()
        print("\nEntries by year:")
        for year, count in year_counts.items():
            print(f"  {year}: {count:,} entries")

if __name__ == "__main__":
    main()