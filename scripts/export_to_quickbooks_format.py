"""
Export ALMS Data to QuickBooks-Compatible CSV Files
====================================================

This script exports data from QuickBooks-compatible views to CSV files
that can be directly imported into QuickBooks.

Non-destructive approach: Uses views that map column names without
changing the underlying database tables.

Usage:
    python export_to_quickbooks_format.py

Output:
    Creates L:\limo\quickbooks_exports\ directory with CSV files
"""

import psycopg2
import pandas as pd
from pathlib import Path
from datetime import datetime
import os

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***'
}

# Output directory
OUTPUT_DIR = Path(r"L:\limo\quickbooks_exports")
OUTPUT_DIR.mkdir(exist_ok=True)

# QuickBooks export views to export
EXPORT_VIEWS = {
    'qb_export_chart_of_accounts': 'Chart_of_Accounts.csv',
    'qb_export_general_journal': 'General_Journal.csv',
    'qb_export_customers': 'Customer_List.csv',
    'qb_export_vendors': 'Vendor_List.csv',
    'qb_export_employees': 'Employee_List.csv',
    'qb_export_ar_aging': 'AR_Aging.csv',
    'qb_export_profit_loss': 'Profit_and_Loss.csv',
    'qb_export_balance_sheet': 'Balance_Sheet.csv',
    'qb_export_vehicles': 'Vehicle_List.csv',
    'qb_export_invoices': 'Invoice_List.csv'
}

def export_view_to_csv(conn, view_name, output_file, date_range=None):
    """Export a QuickBooks view to CSV file."""
    try:
        query = f"SELECT * FROM {view_name}"
        
        # Add date filtering if view has a Date column
        if date_range:
            start_date, end_date = date_range
            query += f" WHERE \"Date\" BETWEEN '{start_date}' AND '{end_date}'"
        
        print(f"Exporting {view_name}...", end=" ")
        df = pd.read_sql(query, conn)
        
        output_path = OUTPUT_DIR / output_file
        df.to_csv(output_path, index=False)
        
        print(f"✓ {len(df):,} records → {output_file}")
        return len(df), output_path
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return 0, None

def create_export_summary(exports):
    """Create a summary report of all exports."""
    summary_path = OUTPUT_DIR / "_Export_Summary.txt"
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("QuickBooks Export Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Export Location: {OUTPUT_DIR}\n\n")
        
        f.write("Exported Files:\n")
        f.write("-" * 80 + "\n")
        
        total_records = 0
        for view_name, (filename, record_count, file_path) in exports.items():
            if file_path:
                file_size = os.path.getsize(file_path) / 1024  # KB
                f.write(f"{filename:<35} {record_count:>10,} records  {file_size:>10,.1f} KB\n")
                total_records += record_count
        
        f.write("-" * 80 + "\n")
        f.write(f"{'TOTAL':<35} {total_records:>10,} records\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("Import Instructions:\n")
        f.write("-" * 80 + "\n")
        f.write("1. Open QuickBooks Desktop\n")
        f.write("2. Go to File → Utilities → Import → Excel Files\n")
        f.write("3. Select the CSV file you want to import\n")
        f.write("4. Follow the import wizard to map columns\n")
        f.write("5. Column names already match QuickBooks format\n\n")
        
        f.write("Files Ready for Import:\n")
        for filename in sorted([f for _, (f, _, p) in exports.items() if p]):
            f.write(f"  • {filename}\n")
        
    print(f"\nSummary report created: {summary_path}")
    return summary_path

def export_with_date_range(conn):
    """Export data with optional date range filtering."""
    print("\n" + "=" * 80)
    print("QuickBooks Export - Date Range Selection")
    print("=" * 80)
    print("\n1. Export All Time (all historical data)")
    print("2. Export Year to Date (YTD)")
    print("3. Export Custom Date Range")
    print("4. Export Current Month")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    date_range = None
    export_suffix = ""
    
    if choice == '1':
        print("\nExporting all historical data...")
        export_suffix = "_All_Time"
    
    elif choice == '2':
        start_date = f"{datetime.now().year}-01-01"
        end_date = datetime.now().strftime('%Y-%m-%d')
        date_range = (start_date, end_date)
        export_suffix = f"_YTD_{datetime.now().year}"
        print(f"\nExporting Year to Date: {start_date} to {end_date}")
    
    elif choice == '3':
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()
        date_range = (start_date, end_date)
        export_suffix = f"_{start_date}_to_{end_date}"
        print(f"\nExporting date range: {start_date} to {end_date}")
    
    elif choice == '4':
        start_date = datetime.now().strftime('%Y-%m-01')
        end_date = datetime.now().strftime('%Y-%m-%d')
        date_range = (start_date, end_date)
        export_suffix = f"_{datetime.now().strftime('%Y_%m')}"
        print(f"\nExporting current month: {start_date} to {end_date}")
    
    elif choice == '5':
        return None, None
    
    else:
        print("Invalid choice. Exporting all data.")
        export_suffix = "_All_Time"
    
    return date_range, export_suffix

def main():
    """Main export function."""
    print("=" * 80)
    print("QuickBooks Export Tool")
    print("=" * 80)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    
    # Get date range selection
    date_range, export_suffix = export_with_date_range(None)
    if date_range is None and export_suffix is None:
        print("Export cancelled.")
        return
    
    # Connect to database
    print("\nConnecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    
    # Export all views
    print("\n" + "=" * 80)
    print("Exporting Views to CSV")
    print("=" * 80 + "\n")
    
    exports = {}
    for view_name, filename in EXPORT_VIEWS.items():
        # Add suffix to filename
        base_name = filename.rsplit('.', 1)[0]
        ext = filename.rsplit('.', 1)[1]
        suffixed_filename = f"{base_name}{export_suffix}.{ext}"
        
        record_count, file_path = export_view_to_csv(conn, view_name, suffixed_filename, date_range)
        exports[view_name] = (suffixed_filename, record_count, file_path)
    
    # Create summary report
    print("\n" + "=" * 80)
    summary_path = create_export_summary(exports)
    
    # Close connection
    conn.close()
    
    print("\n" + "=" * 80)
    print("Export Complete!")
    print("=" * 80)
    print(f"\nFiles exported to: {OUTPUT_DIR}")
    print(f"Summary report: {summary_path}")
    print("\nYou can now import these CSV files into QuickBooks.")
    print("Column names already match QuickBooks format - no mapping needed!")

if __name__ == '__main__':
    main()
