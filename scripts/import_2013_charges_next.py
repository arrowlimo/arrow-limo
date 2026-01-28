#!/usr/bin/env python3
"""
Import chargesummary2013.xls - Critical 2013 charge data.

This file should contain comprehensive 2013 charge/expense data
to fill the massive gap (only 55 records currently).
"""

import os
import sys
import pandas as pd
import psycopg2
from datetime import datetime
from decimal import Decimal

def import_2013_charges():
    """Import 2013 charge summary data."""
    
    file_path = "L:/limo/docs/2012-2013 excel/chargesummary2013.xls"
    
    print("IMPORTING 2013 CHARGE SUMMARY - CRITICAL GAP FILLER")
    print("=" * 60)
    print(f"File: {file_path}")
    print("Current 2013 records: 55 (massive gap)")
    print("Expected recovery: $150,000+")
    
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Read Excel file (handle .xls format)
        df = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
        
        print(f"\n📋 FILE STRUCTURE:")
        print("-" * 40)
        
        for sheet_name, sheet_df in df.items():
            print(f"Sheet: {sheet_name}")
            print(f"Rows: {len(sheet_df)}")
            print(f"Columns: {list(sheet_df.columns)[:5]}...")  # First 5 columns
            
            # Look for amount/charge data
            amount_cols = []
            for col in sheet_df.columns:
                if any(term in str(col).lower() for term in ['amount', 'total', 'charge', 'expense', 'cost']):
                    amount_cols.append(col)
            
            if amount_cols:
                print(f"Amount columns: {amount_cols}")
        
        # TODO: Add actual import logic here
        print(f"\n[WARN]  IMPORT LOGIC NEEDED:")
        print("1. Identify main data sheet")
        print("2. Map columns to receipts table")  
        print("3. Handle 2013 date validation")
        print("4. Import with unique source_hash")
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")

if __name__ == "__main__":
    import_2013_charges()
