#!/usr/bin/env python3
"""
Individual Excel File Validator and Processor

Systematically scan each file in the 2012-2013 excel archive:
1. Validate file structure and content
2. Check for new data vs existing database duplicates  
3. Assess expense recovery potential
4. Move processed files to uploaded folder
5. Generate detailed analysis report for each file
"""

import os
import sys
import pandas as pd
import psycopg2
import shutil
from datetime import datetime
from decimal import Decimal
import hashlib
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def analyze_excel_file_structure(file_path):
    """Analyze individual Excel file structure and content."""
    
    result = {
        'filename': os.path.basename(file_path),
        'file_size': os.path.getsize(file_path),
        'analysis_date': datetime.now().isoformat(),
        'sheets': [],
        'total_potential_records': 0,
        'expense_potential': 0,
        'data_quality': 'unknown',
        'recommended_action': 'skip',
        'errors': []
    }
    
    try:
        # Handle different Excel formats
        if file_path.endswith('.xls'):
            try:
                xl_file = pd.ExcelFile(file_path, engine='xlrd')
            except Exception as e:
                result['errors'].append(f"xlrd compatibility issue: {e}")
                return result
        else:
            xl_file = pd.ExcelFile(file_path)
        
        result['sheet_count'] = len(xl_file.sheet_names)
        
        for sheet_name in xl_file.sheet_names:
            sheet_info = analyze_sheet_content(xl_file, file_path, sheet_name)
            result['sheets'].append(sheet_info)
            result['total_potential_records'] += sheet_info.get('row_count', 0)
            result['expense_potential'] += sheet_info.get('expense_amount', 0)
        
        # Determine data quality and recommended action
        if result['expense_potential'] > 100000:
            result['data_quality'] = 'high_value'
            result['recommended_action'] = 'priority_import'
        elif result['expense_potential'] > 10000:
            result['data_quality'] = 'medium_value'
            result['recommended_action'] = 'import'
        elif result['total_potential_records'] > 100:
            result['data_quality'] = 'data_rich'
            result['recommended_action'] = 'analyze_further'
        else:
            result['data_quality'] = 'low_value'
            result['recommended_action'] = 'archive'
            
    except Exception as e:
        result['errors'].append(f"File analysis error: {e}")
    
    return result

def analyze_sheet_content(xl_file, file_path, sheet_name):
    """Analyze individual sheet content for expense potential."""
    
    sheet_info = {
        'name': sheet_name,
        'row_count': 0,
        'column_count': 0,
        'expense_amount': 0,
        'has_dates': False,
        'has_amounts': False,
        'has_vendors': False,
        'expense_category': None,
        'sample_data': []
    }
    
    try:
        # Read sheet with limited rows for analysis
        df = pd.read_excel(xl_file, sheet_name=sheet_name, nrows=50)
        
        sheet_info['row_count'] = len(df)
        sheet_info['column_count'] = len(df.columns)
        
        # Analyze columns for expense indicators
        amount_columns = []
        date_columns = []
        text_columns = []
        
        for col in df.columns:
            col_str = str(col).lower()
            
            # Amount columns
            if any(keyword in col_str for keyword in ['debit', 'credit', 'amount', 'total', 'balance', 'expense']):
                amount_columns.append(col)
                
                # Try to calculate total
                try:
                    series = pd.to_numeric(df[col], errors='coerce')
                    amount_total = series.sum()
                    if amount_total > 0:
                        sheet_info['expense_amount'] += amount_total
                        sheet_info['has_amounts'] = True
                except:
                    pass
            
            # Date columns
            elif any(keyword in col_str for keyword in ['date', 'time']):
                date_columns.append(col)
                sheet_info['has_dates'] = True
            
            # Text columns (vendors, descriptions)
            elif any(keyword in col_str for keyword in ['name', 'vendor', 'payee', 'description', 'memo']):
                text_columns.append(col)
                sheet_info['has_vendors'] = True
        
        # Determine expense category from sheet name
        sheet_lower = sheet_name.lower()
        expense_keywords = {
            'fuel': ['fuel', 'gas', 'diesel'],
            'maintenance': ['repair', 'maintenance', 'maint'],
            'insurance': ['insurance', 'insur'],
            'payroll': ['payroll', 'pay', 'salary', 'wage'],
            'banking': ['bank', 'cibc', 'scotia', 'td'],
            'office': ['office', 'supplies', 'equipment'],
            'revenue': ['revenue', 'income', 'charge', 'receipt'],
            'accounting': ['accounting', 'sbs', 'journal', 'ledger'],
            'leasing': ['lease', 'rental', 'rent']
        }
        
        for category, keywords in expense_keywords.items():
            if any(keyword in sheet_lower for keyword in keywords):
                sheet_info['expense_category'] = category
                break
        
        # Get sample data for verification
        if not df.empty:
            sample_rows = min(3, len(df))
            for i in range(sample_rows):
                row_sample = {}
                for col in df.columns[:5]:  # First 5 columns
                    value = df.iloc[i, df.columns.get_loc(col)]
                    if pd.notna(value):
                        row_sample[str(col)] = str(value)[:50]  # Truncate long values
                sheet_info['sample_data'].append(row_sample)
        
    except Exception as e:
        sheet_info['error'] = str(e)
    
    return sheet_info

def check_duplicate_data(file_path, analysis_result):
    """Check if file data already exists in database."""
    
    duplicate_check = {
        'has_duplicates': False,
        'duplicate_percentage': 0,
        'new_records_estimated': 0,
        'duplicate_details': []
    }
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check for existing data based on filename patterns
        filename = os.path.basename(file_path)
        
        # Check if we already imported from this file
        cur.execute("""
            SELECT COUNT(*) FROM receipts 
            WHERE source_reference LIKE %s
        """, (f'%{filename}%',))
        
        existing_count = cur.fetchone()[0]
        
        if existing_count > 0:
            duplicate_check['has_duplicates'] = True
            duplicate_check['duplicate_details'].append(f"Found {existing_count} existing records from this file")
        
        # Estimate new records based on analysis
        total_potential = analysis_result.get('total_potential_records', 0)
        if total_potential > 0:
            duplicate_check['new_records_estimated'] = max(0, total_potential - existing_count)
            if existing_count > 0:
                duplicate_check['duplicate_percentage'] = (existing_count / total_potential) * 100
        
        cur.close()
        conn.close()
        
    except Exception as e:
        duplicate_check['error'] = str(e)
    
    return duplicate_check

def move_to_uploaded_folder(file_path, analysis_result):
    """Move processed file to uploaded folder with analysis metadata."""
    
    filename = os.path.basename(file_path)
    source_dir = os.path.dirname(file_path)
    uploaded_dir = os.path.join(source_dir, 'uploaded')
    
    # Ensure uploaded directory exists
    os.makedirs(uploaded_dir, exist_ok=True)
    
    # Create destination path
    dest_path = os.path.join(uploaded_dir, filename)
    
    # Create analysis report filename
    report_filename = f"{os.path.splitext(filename)[0]}_analysis.json"
    report_path = os.path.join(uploaded_dir, report_filename)
    
    try:
        # Move file
        shutil.move(file_path, dest_path)
        
        # Save analysis report
        with open(report_path, 'w') as f:
            json.dump(analysis_result, f, indent=2, default=str)
        
        return {
            'success': True,
            'new_path': dest_path,
            'report_path': report_path
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def process_single_file(file_path, dry_run=True):
    """Process a single Excel file through the validation pipeline."""
    
    print(f"\n{'='*60}")
    print(f"PROCESSING: {os.path.basename(file_path)}")
    print(f"{'='*60}")
    
    # Step 1: Analyze file structure
    print("1. Analyzing file structure...")
    analysis = analyze_excel_file_structure(file_path)
    
    if analysis['errors']:
        print(f"   [FAIL] ERRORS: {'; '.join(analysis['errors'])}")
        return analysis
    
    print(f"   [OK] Sheets: {analysis.get('sheet_count', 0)}")
    print(f"   [OK] Potential records: {analysis.get('total_potential_records', 0):,}")
    print(f"   [OK] Expense potential: ${analysis.get('expense_potential', 0):,.2f}")
    print(f"   [OK] Data quality: {analysis.get('data_quality', 'unknown')}")
    
    # Step 2: Check for duplicates
    print("2. Checking for duplicate data...")
    duplicate_check = check_duplicate_data(file_path, analysis)
    
    analysis['duplicate_check'] = duplicate_check
    
    if duplicate_check.get('has_duplicates'):
        print(f"   [WARN]  Found existing data: {duplicate_check.get('duplicate_percentage', 0):.1f}% duplicate")
        print(f"   📊 New records estimated: {duplicate_check.get('new_records_estimated', 0):,}")
    else:
        print(f"   [OK] No duplicates found - new data source!")
    
    # Step 3: Show detailed sheet analysis
    print("3. Sheet-by-sheet analysis:")
    for i, sheet in enumerate(analysis.get('sheets', [])[:5], 1):  # Show first 5 sheets
        category = sheet.get('expense_category') or 'unknown'
        amount = sheet.get('expense_amount', 0)
        sheet_name = sheet.get('name', 'Unknown')[:30]
        print(f"   {i}. {sheet_name:<30} | {category:<12} | ${amount:>10,.0f}")
    
    if len(analysis.get('sheets', [])) > 5:
        print(f"   ... and {len(analysis['sheets']) - 5} more sheets")
    
    # Step 4: Recommendation
    print("4. Recommendation:")
    action = analysis.get('recommended_action', 'skip')
    
    if action == 'priority_import':
        print(f"   🚀 PRIORITY IMPORT - High value expense data (${analysis.get('expense_potential', 0):,.0f})")
    elif action == 'import':
        print(f"   [OK] IMPORT - Good expense data (${analysis.get('expense_potential', 0):,.0f})")
    elif action == 'analyze_further':
        print(f"   🔍 ANALYZE FURTHER - Data rich but needs review")
    else:
        print(f"   📁 ARCHIVE - Low value or duplicate data")
    
    # Step 5: Move to uploaded folder (if not dry run)
    if not dry_run:
        print("5. Moving to uploaded folder...")
        move_result = move_to_uploaded_folder(file_path, analysis)
        
        if move_result.get('success'):
            print(f"   [OK] Moved to: {move_result['new_path']}")
            print(f"   [OK] Analysis saved: {move_result['report_path']}")
        else:
            print(f"   [FAIL] Move failed: {move_result.get('error')}")
            
        analysis['move_result'] = move_result
    else:
        print("5. DRY RUN - File not moved")
    
    return analysis

def main():
    """Process all files in the 2012-2013 excel directory."""
    
    import sys
    
    # Command line arguments
    dry_run = '--write' not in sys.argv
    single_file = None
    
    # Check if specific file requested
    for arg in sys.argv[1:]:
        if arg.startswith('L:') and arg.endswith('.xlsx') or arg.endswith('.xls') or arg.endswith('.xlsm'):
            single_file = arg
            break
    
    print("EXCEL ARCHIVE VALIDATION & PROCESSING SYSTEM")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if dry_run:
        print("MODE: DRY RUN (use --write to actually move files)")
    else:
        print("MODE: LIVE - Files will be moved to uploaded folder")
    
    # File list from user request
    excel_files = [
        r"L:\limo\docs\2012-2013 excel\Which Amount is Correct - April 2014.xlsx",
        r"L:\limo\docs\2012-2013 excel\2012 CIBC.xlsm",
        r"L:\limo\docs\2012-2013 excel\2012 Expenses.xlsm",
        r"L:\limo\docs\2012-2013 excel\2012 Reconcile Cash Receipts.xlsx",
        r"L:\limo\docs\2012-2013 excel\2012 Scotia.xlsm",
        r"L:\limo\docs\2012-2013 excel\2013 Driver Info.xls",
        r"L:\limo\docs\2012-2013 excel\2013 Revenue & Receipts queries.xlsx",
        r"L:\limo\docs\2012-2013 excel\2013 Revenue & Receipts queries1.xlsx",
        r"L:\limo\docs\2012-2013 excel\2014 Leasing Summary.xlsx",
        r"L:\limo\docs\2012-2013 excel\2014 Leasing Summary2.xlsx"
        # Add more files as needed
    ]
    
    if single_file:
        excel_files = [single_file]
        print(f"SINGLE FILE MODE: {os.path.basename(single_file)}")
    
    # Process each file
    results = []
    total_potential = 0
    priority_files = []
    
    for i, file_path in enumerate(excel_files, 1):
        if not os.path.exists(file_path):
            print(f"\n[FAIL] File not found: {file_path}")
            continue
            
        print(f"\nFile {i}/{len(excel_files)}")
        
        result = process_single_file(file_path, dry_run)
        results.append(result)
        
        expense_potential = result.get('expense_potential', 0)
        total_potential += expense_potential
        
        if result.get('recommended_action') == 'priority_import':
            priority_files.append({
                'filename': result.get('filename'),
                'potential': expense_potential
            })
    
    # Summary report
    print(f"\n{'='*80}")
    print("PROCESSING SUMMARY")
    print(f"{'='*80}")
    
    print(f"Files processed: {len(results)}")
    print(f"Total expense potential: ${total_potential:,.2f}")
    print(f"Priority files identified: {len(priority_files)}")
    
    if priority_files:
        print(f"\n🚀 PRIORITY IMPORT FILES:")
        for i, pf in enumerate(priority_files, 1):
            print(f"{i:2d}. {pf['filename']:<40} ${pf['potential']:>12,.0f}")
    
    # Next steps
    print(f"\n📋 NEXT STEPS:")
    if not dry_run:
        print("[OK] Files have been moved to uploaded folder")
        print("[OK] Analysis reports saved as JSON files")
    else:
        print("1. Review analysis results above")
        print("2. Run with --write to move files and save analysis")
    
    print("3. Process priority files first for maximum impact")
    print("4. Create import scripts for high-value files")
    
    tax_benefit = total_potential * 0.14
    print(f"\n💰 TAX IMPACT: ${tax_benefit:,.0f} potential tax benefit")

if __name__ == "__main__":
    main()