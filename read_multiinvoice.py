import pandas as pd
import sys

file_path = r"Z:\multiinvoice.xls"

print("="*80)
print("READING Z:\\multiinvoice.xls - LEGACY LMS DATA")
print("="*80)

try:
    # Try reading the Excel file
    df = pd.read_excel(file_path, engine='xlrd')
    
    print(f"\n📊 FILE INFO:")
    print(f"  Total Rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    
    # Show first few rows
    print(f"\n📋 FIRST 10 ROWS:")
    print(df.head(10).to_string())
    
    # Search for Perron Ventures
    print(f"\n" + "="*80)
    print("SEARCHING FOR PERRON VENTURES")
    print("="*80)
    
    # Try different column names that might contain client names
    client_columns = [col for col in df.columns if 'client' in col.lower() or 'name' in col.lower() or 'company' in col.lower()]
    
    if client_columns:
        print(f"\nFound potential client columns: {client_columns}")
        
        for col in client_columns:
            perron_rows = df[df[col].astype(str).str.contains('Perron', case=False, na=False)]
            if len(perron_rows) > 0:
                print(f"\n✅ Found {len(perron_rows)} Perron Ventures records in column '{col}':")
                print(perron_rows.to_string())
    else:
        # Search all columns
        print(f"\nSearching all columns for 'Perron'...")
        for col in df.columns:
            perron_rows = df[df[col].astype(str).str.contains('Perron', case=False, na=False)]
            if len(perron_rows) > 0:
                print(f"\n✅ Found in column '{col}': {len(perron_rows)} rows")
                print(perron_rows[[col]].to_string())
    
except Exception as e:
    print(f"\n❌ ERROR reading file: {e}")
    print(f"\nTrying alternative approach...")
    
    # Try reading with different parameters
    try:
        df = pd.read_excel(file_path, engine='xlrd', header=None)
        print(f"\n📊 FILE INFO (no header):")
        print(f"  Total Rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        print(f"\n📋 FIRST 20 ROWS:")
        print(df.head(20).to_string())
    except Exception as e2:
        print(f"❌ FAILED: {e2}")
