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
    
    print("\nImporting journal data...")
    extract_journal_data(journal_file, report_path)
    
    print("\nProcess complete!")

def extract_journal_data(file_path, report_path):
    """Extract journal data with manual column mapping"""
    # Read with header at row 4 (index 4)
    df = pd.read_excel(file_path, header=4)
    
    # Show the first few rows
    print("\nFirst 5 rows with headers from row 4:")
    print(df.head().to_string())
    
    # Show column names
    print("\nColumn names:")
    for i, col in enumerate(df.columns):
        print(f"  {i}: {col}")
    
    # Check if we have usable data
    if 'Transaction date' not in df.columns:
        renamed_cols = {}
        for i, col in enumerate(df.columns):
            if i == 1:
                renamed_cols[col] = 'Transaction date'
            elif i == 2:
                renamed_cols[col] = 'Transaction type'
            elif i == 3:
                renamed_cols[col] = '#'
            elif i == 4:
                renamed_cols[col] = 'Name'
            elif i == 5:
                renamed_cols[col] = 'Memo/Description'
            elif i == 6:
                renamed_cols[col] = 'Distribution account number'
            elif i == 7:
                renamed_cols[col] = 'Account full name'
            elif i == 8:
                renamed_cols[col] = 'Debit'
            elif i == 9:
                renamed_cols[col] = 'Credit'
        
        df = df.rename(columns=renamed_cols)
        print("\nRenamed columns:")
        for old, new in renamed_cols.items():
            print(f"  {old} -> {new}")
    
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
    
    print("\nColumn mapping:")
    for db_col, file_col in column_mapping.items():
        if file_col in df.columns:
            print(f"  {db_col} -> {file_col} (Found)")
        else:
            print(f"  {db_col} -> {file_col} (Not found)")
    
    # Extract just the rows with actual data
    print("\nFiltering data rows...")
    start_time = time.time()
    
    # Remove rows with NaN Transaction date
    before_count = len(df)
    df = df.dropna(subset=['Transaction date'])
    after_count = len(df)
    print(f"Filtered from {before_count} to {after_count} rows with valid dates")
    
    # Convert date column to datetime
    df['Transaction date'] = pd.to_datetime(df['Transaction date'], errors='coerce')
    df = df.dropna(subset=['Transaction date'])
    
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
    
    # Create SQL import script
    create_import_script(df_clean, report_path)

def create_import_script(df, report_path):
    """Create SQL import script for the journal data"""
    sql_file = report_path / "journal_import.sql"
    
    print(f"\nGenerating SQL import script to {sql_file}...")
    start_time = time.time()
    
    with open(sql_file, 'w') as f:
        # Write header
        f.write("-- Journal import script generated on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
        f.write("BEGIN;\n\n")
        
        # Get column names
        columns = df.columns.tolist()
        if 'Year' in columns:
            columns.remove('Year')  # Remove analysis column
            
        # Write INSERT statements - use batch inserts for efficiency
        batch_size = 100
        batches = 0
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            
            # Create multi-value INSERT
            col_list = ', '.join([f'"{col}"' for col in columns])
            f.write(f"INSERT INTO journal ({col_list}) VALUES\n")
            
            # Add each row as a value set
            values_list = []
            for _, row in batch.iterrows():
                row_values = []
                for col in columns:
                    val = row[col]
                    
                    if pd.isna(val):
                        row_values.append("NULL")
                    elif col == 'Date':
                        row_values.append(f"'{val.strftime('%Y-%m-%d')}'")
                    elif isinstance(val, (int, float)):
                        row_values.append(str(val))
                    else:
                        # Escape single quotes
                        val_str = str(val).replace("'", "''")
                        row_values.append(f"'{val_str}'")
                
                values_list.append("(" + ", ".join(row_values) + ")")
            
            # Join all values and end statement
            f.write(",\n".join(values_list))
            f.write(";\n\n")
            
            batches += 1
            
            # Add a comment every 10 batches
            if batches % 10 == 0:
                f.write(f"-- Inserted {batches * batch_size} rows\n\n")
        
        # Write footer
        f.write("\nCOMMIT;\n")
    
    print(f"Generated SQL script for {len(df)} rows in {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()