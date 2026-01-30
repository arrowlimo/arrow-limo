import pandas as pd
import psycopg2
from pathlib import Path
import time
import os
import re
from datetime import datetime

def main():
    print("QuickBooks Journal Data Importer")
    print("==============================")
    
    # Define file paths
    journal_file = Path("L:/limo/quickbooks/Arrow Limousine backup 2025_Journal.xlsx")
    
    if not journal_file.exists():
        print(f"Journal file not found: {journal_file}")
        return
    
    # Create output directory
    report_path = Path('L:/limo/reports/import_results')
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
    
    # Import journal data
    import_journal_data(journal_file, conn, report_path)
    
    print("\nProcess complete!")

def import_journal_data(file_path, conn, report_path):
    """Import journal data from QuickBooks export file"""
    print(f"\nProcessing journal file: {file_path.name}")
    start_time = time.time()
    
    try:
        # Read the Excel file
        print("Reading Excel file...")
        df_raw = pd.read_excel(file_path)
        
        # Find the header row (usually row 3)
        header_row = find_header_row(df_raw)
        if header_row is None:
            print("Could not find header row")
            return
        
        print(f"Found header row at index {header_row}")
        
        # Re-read with proper header
        df = pd.read_excel(file_path, header=header_row)
        
        # Clean up column names
        df.columns = [str(col).strip() for col in df.columns]
        
        print(f"Processed file has {len(df)} rows and columns: {', '.join(df.columns)}")
        
        # Map columns to database fields
        column_mapping = map_columns(df.columns)
        print("\nColumn mapping:")
        for db_col, file_col in column_mapping.items():
            print(f"  {db_col} -> {file_col}")
        
        # Clean and transform the data
        print("\nCleaning and transforming data...")
        df_clean = clean_journal_data(df, column_mapping)
        
        # Save cleaned data to CSV for review
        clean_csv = report_path / f"{file_path.stem}_cleaned.csv"
        df_clean.to_csv(clean_csv, index=False)
        print(f"Saved cleaned data to {clean_csv}")
        
        # Check existing data in database
        cur = conn.cursor()
        cur.execute("SELECT MIN(\"Date\"), MAX(\"Date\") FROM journal WHERE \"Date\" IS NOT NULL")
        date_range = cur.fetchone()
        
        if date_range[0]:
            print(f"Existing journal date range in database: {date_range[0]} to {date_range[1]}")
        
        # Get min/max dates from file
        date_col = column_mapping.get('Date')
        if date_col and date_col in df_clean.columns:
            min_date = df_clean[date_col].min()
            max_date = df_clean[date_col].max()
            print(f"Journal date range in file: {min_date} to {max_date}")
        
        # Import options
        print("\nImport options:")
        print("1. Import all journal entries")
        print("2. Import only entries not in database date range")
        print("3. Generate SQL import script only (no direct import)")
        print("4. Cancel import")
        
        choice = input("Select option (1-4): ")
        
        if choice == '4':
            print("Import cancelled")
            return
        
        # Filter data if option 2 selected
        if choice == '2' and date_range[0] and date_col in df_clean.columns:
            min_db_date = date_range[0]
            max_db_date = date_range[1]
            
            # Convert to pandas datetime if needed
            if not pd.api.types.is_datetime64_any_dtype(df_clean[date_col]):
                df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors='coerce')
            
            # Filter out dates already in DB
            before_count = len(df_clean)
            df_clean = df_clean[(df_clean[date_col] < min_db_date) | (df_clean[date_col] > max_db_date)]
            after_count = len(df_clean)
            
            print(f"Filtered out {before_count - after_count} entries already in database date range")
        
        # Generate SQL script
        sql_file = report_path / f"{file_path.stem}_import.sql"
        row_count = generate_sql_script(df_clean, column_mapping, sql_file)
        print(f"Generated SQL script with {row_count} entries to {sql_file}")
        
        # Perform import if requested
        if choice in ['1', '2']:
            print("\nImporting data to database...")
            imported = import_to_database(conn, sql_file)
            print(f"Successfully imported {imported} journal entries")
        
        print(f"\nProcessing completed in {time.time() - start_time:.2f} seconds")
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")

def find_header_row(df):
    """Find the row containing column headers"""
    # Look for rows that might contain headers
    for i in range(min(10, len(df))):
        row = df.iloc[i]
        row_values = [str(v).lower() for v in row if pd.notna(v)]
        
        # Check if this row has typical header keywords
        header_keywords = ['date', 'transaction', 'debit', 'credit', 'account']
        matches = sum(1 for value in row_values for keyword in header_keywords if keyword in value)
        
        if matches >= 3:  # If at least 3 header keywords found
            return i
    
    return None

def map_columns(file_columns):
    """Map file columns to database columns"""
    db_columns = {
        'Date': None,
        'Transaction Type': None,
        '#': None,
        'Name': None,
        'Memo/Description': None,
        'Account': None,
        'Debit': None,
        'Credit': None,
        'merchant': None,
        'transaction_type': None,
        'reference_number': None,
        'Reference': None
    }
    
    # Try to match columns by name
    for col in file_columns:
        col_lower = str(col).lower()
        
        if 'date' in col_lower and 'transaction' in col_lower:
            db_columns['Date'] = col
        elif 'transaction' in col_lower and 'type' in col_lower:
            db_columns['Transaction Type'] = col
        elif col_lower == '#' or 'num' in col_lower:
            db_columns['#'] = col
        elif col_lower == 'name' or 'payee' in col_lower:
            db_columns['Name'] = col
        elif 'memo' in col_lower or 'description' in col_lower:
            db_columns['Memo/Description'] = col
        elif 'account' in col_lower and 'full' in col_lower:
            db_columns['Account'] = col
        elif col_lower == 'debit':
            db_columns['Debit'] = col
        elif col_lower == 'credit':
            db_columns['Credit'] = col
        elif col_lower == 'reference':
            db_columns['Reference'] = col
    
    # Use fallbacks for important columns
    if not db_columns['Date'] and 'Transaction date' in file_columns:
        db_columns['Date'] = 'Transaction date'
    
    if not db_columns['Transaction Type'] and 'Transaction type' in file_columns:
        db_columns['Transaction Type'] = 'Transaction type'
    
    if not db_columns['Account'] and 'Account full name' in file_columns:
        db_columns['Account'] = 'Account full name'
    
    if not db_columns['Debit'] and 'Amount' in file_columns:
        # In some files Amount is used instead of separate Debit/Credit
        db_columns['Debit'] = 'Amount'
        db_columns['Credit'] = 'Amount'  # Will need special handling in data cleaning
    
    # Ensure the most critical columns are mapped
    if not db_columns['Date']:
        for col in file_columns:
            if 'date' in str(col).lower():
                db_columns['Date'] = col
                break
    
    return db_columns

def clean_journal_data(df, column_mapping):
    """Clean and transform journal data"""
    # Create a new DataFrame for cleaned data
    df_clean = pd.DataFrame()
    
    # Copy mapped columns
    for db_col, file_col in column_mapping.items():
        if file_col and file_col in df.columns:
            df_clean[db_col] = df[file_col]
    
    # Handle dates
    if 'Date' in df_clean.columns:
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
    
    # Handle amount fields
    if 'Debit' in df_clean.columns and 'Credit' in df_clean.columns:
        # If using the same column for both
        if column_mapping['Debit'] == column_mapping['Credit']:
            # Split Amount into Debit and Credit based on sign
            amount_col = column_mapping['Debit']
            df_clean['Debit'] = df[amount_col].apply(lambda x: float(x) if pd.notna(x) and float(x) > 0 else None)
            df_clean['Credit'] = df[amount_col].apply(lambda x: -float(x) if pd.notna(x) and float(x) < 0 else None)
    
    # Remove rows without date
    if 'Date' in df_clean.columns:
        df_clean = df_clean.dropna(subset=['Date'])
    
    # Fill NaN with None for database compatibility
    df_clean = df_clean.where(pd.notna(df_clean), None)
    
    return df_clean

def generate_sql_script(df, column_mapping, output_file):
    """Generate SQL script for importing data"""
    with open(output_file, 'w') as f:
        # Write header
        f.write("-- Journal import script generated on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
        f.write("BEGIN;\n\n")
        
        # Get column names that have mappings
        columns = [col for col in df.columns if col in column_mapping.values()]
        
        # Write INSERT statements
        count = 0
        for _, row in df.iterrows():
            values = []
            for col in df.columns:
                val = row[col]
                
                # Format by data type
                if val is None:
                    values.append("NULL")
                elif col == 'Date' and pd.notna(val):
                    values.append(f"'{val}'::date")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    # Escape single quotes
                    val_str = str(val).replace("'", "''")
                    values.append(f"'{val_str}'")
            
            # Create INSERT statement
            columns_str = ', '.join([f'"{c}"' for c in df.columns])
            values_str = ', '.join(values)
            insert_sql = f"INSERT INTO journal ({columns_str}) VALUES ({values_str});\n"
            f.write(insert_sql)
            count += 1
            
            # Add a comment every 1000 rows for readability
            if count % 1000 == 0:
                f.write(f"\n-- Inserted {count} rows\n\n")
        
        # Write footer
        f.write("\nCOMMIT;\n")
    
    return count

def import_to_database(conn, sql_file):
    """Import data using the generated SQL script"""
    cur = conn.cursor()
    
    # Read SQL script
    with open(sql_file, 'r') as f:
        sql = f.read()
    
    # Execute script
    try:
        cur.execute(sql)
        conn.commit()
        
        # Count inserted rows
        cur.execute("SELECT COUNT(*) FROM journal")
        after_count = cur.fetchone()[0]
        
        return after_count
    except Exception as e:
        conn.rollback()
        print(f"Import failed: {str(e)}")
        return 0

if __name__ == "__main__":
    main()