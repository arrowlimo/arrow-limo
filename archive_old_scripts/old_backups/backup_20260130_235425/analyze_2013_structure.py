#!/usr/bin/env python3
"""
Analyze chargesummary2013.xls structure to understand the data format.
"""

import pandas as pd
import os

def analyze_2013_structure():
    """Analyze the structure of the 2013 charge summary file."""
    
    file_path = "L:/limo/docs/2012-2013 excel/chargesummary2013.xls"
    
    print("ANALYZING 2013 CHARGE SUMMARY STRUCTURE")
    print("=" * 50)
    
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Read the file
        df = pd.read_excel(file_path, engine='xlrd')
        
        print(f"📋 FILE OVERVIEW:")
        print(f"Rows: {len(df)}")
        print(f"Columns: {len(df.columns)}")
        print()
        
        print(f"📋 COLUMN STRUCTURE:")
        print("-" * 30)
        for i, col in enumerate(df.columns):
            print(f"{i}: '{col}'")
        
        print(f"\n📋 FIRST 10 ROWS:")
        print("-" * 50)
        print(df.head(10).to_string())
        
        print(f"\n📋 SAMPLE DATA (rows 10-20):")
        print("-" * 50)
        print(df.iloc[10:20].to_string())
        
        print(f"\n📋 DATA TYPES:")
        print("-" * 30)
        print(df.dtypes)
        
        print(f"\n📋 NON-NULL COUNTS:")
        print("-" * 30)
        print(df.count())
        
        # Look for numeric columns
        print(f"\n📋 NUMERIC DATA ANALYSIS:")
        print("-" * 30)
        
        for col in df.columns:
            try:
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                non_null = numeric_series.count()
                total_sum = numeric_series.sum()
                
                if non_null > 10 and total_sum > 1000:
                    print(f"{col}: {non_null} numeric values, sum=${total_sum:,.2f}")
            except:
                pass
        
        # Check for patterns in specific areas
        print(f"\n📋 SEARCHING FOR DATA PATTERNS:")
        print("-" * 30)
        
        # Look for header rows
        for i in range(min(20, len(df))):
            row_text = ' '.join(str(df.iloc[i, j]) for j in range(min(8, len(df.columns))))
            if any(term in row_text.lower() for term in ['date', 'amount', 'vendor', 'expense', 'total']):
                print(f"Row {i} (potential header): {row_text[:100]}")
        
    except Exception as e:
        print(f"[FAIL] Error analyzing file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_2013_structure()