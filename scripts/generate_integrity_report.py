#!/usr/bin/env python3
"""
Automated Data Integrity Report Generator
Reviews all tables and saves detailed analysis to file
"""
import psycopg2
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def get_table_columns(cur, table_name):
    """Get all columns for a table with data types"""
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cur.fetchall()

def get_sample_data(cur, table_name, columns, limit=5, sample_year=2024):
    """Get sample data for specified columns (default: 2024 records)"""
    col_names = ', '.join([f'"{col}"' for col in columns])
    date_column_map = {
        'charters': 'charter_date',
        'payments': 'payment_date',
        'receipts': 'receipt_date'
    }
    date_column = date_column_map.get(table_name)
    try:
        if date_column:
            cur.execute(
                f"""
                SELECT {col_names}
                FROM {table_name}
                WHERE {date_column} >= %s AND {date_column} < %s
                ORDER BY {date_column} DESC
                LIMIT {limit}
                """,
                (f"{sample_year}-01-01", f"{sample_year + 1}-01-01")
            )
        else:
            cur.execute(f"SELECT {col_names} FROM {table_name} ORDER BY 1 DESC LIMIT {limit}")
        return cur.fetchall()
    except Exception as e:
        return f"Error: {e}"

def check_null_percentage(cur, table_name, column_name):
    """Check percentage of NULL values in a column"""
    cur.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT("{column_name}") as non_null,
            COUNT(*) - COUNT("{column_name}") as null_count,
            ROUND(100.0 * (COUNT(*) - COUNT("{column_name}")) / NULLIF(COUNT(*), 0), 2) as null_pct
        FROM {table_name}
    """)
    return cur.fetchone()

def get_column_usage(table_name, column_name):
    """Describe where this column is used"""
    usage_map = {
        'charters': {
            'charter_id': 'PK - Links payments, receipts, assignments',
            'reserve_number': '★ BUSINESS KEY - Payment matching, customer reference',
            'account_number': 'Legacy LMS customer account ID',
            'charter_date': 'Service date - Reports, tax year grouping',
            'total_amount_due': '★ Total invoice - Revenue, balance calc',
            'paid_amount': '★ Payments received - Cash flow tracking',
            'balance': '★ Outstanding amount - Receivables, collections',
            'status': 'Charter state - Active/cancelled/closed filter',
            'client_id': 'FK to clients - Customer history',
            'vehicle': 'Vehicle assignment - Fleet utilization',
            'driver': 'Driver assignment - Payroll tracking',
            'rate': 'Base rate - Pricing analysis',
            'deposit': 'Deposit amount - Prepayments',
            'driver_gratuity': 'Tips - Excluded from taxable revenue',
            'client_display_name': 'Customer name - Invoices, UI',
        },
        'payments': {
            'payment_id': 'PK - Payment record ID',
            'reserve_number': '★ BUSINESS KEY - Links to charter',
            'amount': '★ Payment amount - Revenue, cash flow',
            'payment_date': 'Date received - Cash flow, aging',
            'payment_method': 'Payment type - Reconciliation',
            'banking_transaction_id': 'Links to bank statement',
        },
        'receipts': {
            'receipt_id': 'PK - Expense record ID',
            'vendor_name': 'Vendor - Expense categorization',
            'gross_amount': '★ Total with tax - Expense reporting',
            'net_amount': 'Amount before tax - Tax reporting',
            'gst_amount': 'Tax paid - Tax recovery',
            'receipt_date': 'Expense date - Tax year',
        }
    }
    return usage_map.get(table_name, {}).get(column_name, 'Not documented')

def get_column_source(table_name, column_name):
    """Describe which program section or source fills this field"""
    source_map = {
        'charters': {
            'charter_id': 'Database PK (auto-generated)',
            'reserve_number': 'LMS import + booking system; business key',
            'account_number': 'LMS import (customer account)',
            'client_id': 'LMS import + client assignment',
            'charter_date': 'Booking creation / LMS import',
            'pickup_time': 'Booking details / LMS import',
            'pickup_address': 'Booking details / LMS import',
            'dropoff_address': 'Booking details / LMS import',
            'passenger_count': 'Booking details (manual/dispatch)',
            'vehicle': 'Dispatch assignment / LMS import',
            'driver': 'Dispatch assignment / LMS import',
            'rate': 'Pricing engine / LMS import',
            'driver_paid': 'Driver pay workflow (payroll calc)',
            'driver_percentage': 'Legacy LMS field (unused)',
            'driver_total': 'Driver pay calc / LMS import',
            'balance': 'Derived from charges - payments',
            'deposit': 'Booking payment / LMS import',
            'status': 'Booking lifecycle / LMS import',
            'closed': 'Booking lifecycle / LMS import',
            'cancelled': 'Booking lifecycle / LMS import',
        },
        'payments': {
            'payment_id': 'Database PK (auto-generated)',
            'reserve_number': 'Payment import (business key)',
            'amount': 'Payment import',
            'payment_date': 'Payment import',
            'payment_method': 'Payment import + normalization',
            'banking_transaction_id': 'Banking reconciliation link',
        },
        'receipts': {
            'receipt_id': 'Database PK (auto-generated)',
            'vendor_name': 'Receipt import / manual entry',
            'gross_amount': 'Receipt import',
            'net_amount': 'Derived / import (if provided)',
            'gst_amount': 'Derived / import (if provided)',
            'receipt_date': 'Receipt import',
        }
    }
    return source_map.get(table_name, {}).get(column_name, 'Not documented')

def analyze_table(cur, table_name, f, batch_size=20, sample_year=2024):
    """Analyze table and write to file"""
    f.write(f"\n{'=' * 120}\n")
    f.write(f"TABLE: {table_name.upper()}\n")
    f.write(f"{'=' * 120}\n\n")
    
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_records = cur.fetchone()[0]
    f.write(f"Total Records: {total_records:,}\n\n")
    
    columns = get_table_columns(cur, table_name)
    
    for batch_num, i in enumerate(range(0, len(columns), batch_size), 1):
        batch = columns[i:i+batch_size]
        col_names = [col[0] for col in batch]
        
        f.write(f"\n{'-' * 120}\n")
        f.write(f"BATCH {batch_num}: Columns {i+1}-{min(i+batch_size, len(columns))} of {len(columns)}\n")
        f.write(f"{'-' * 120}\n\n")
        
        # Column info
        f.write(f"{'Column':<30} {'Type':<20} {'Null?':<8} {'%Null':<8} {'Usage':<45} {'Source'}\n")
        f.write("-" * 120 + "\n")
        
        issues = []
        for col_name, data_type, is_nullable in batch:
            stats = check_null_percentage(cur, table_name, col_name)
            null_pct = stats[3] if stats[3] is not None else 0
            usage = get_column_usage(table_name, col_name)
            source = get_column_source(table_name, col_name)
            
            f.write(f"{col_name:<30} {data_type:<20} {is_nullable:<8} {null_pct:>6.1f}%  {usage:<45} {source}\n")
            
            # Flag issues
            if null_pct > 80:
                issues.append(f"  ⚠️  {col_name}: {null_pct:.1f}% NULL - Investigate why")
            elif null_pct > 50 and '★' in usage:
                issues.append(f"  ⚠️  {col_name}: {null_pct:.1f}% NULL in critical field")
        
        # Sample data
        f.write(f"\nSAMPLE DATA (5 rows from {sample_year}):\n")
        f.write("-" * 120 + "\n")
        
        sample_data = get_sample_data(cur, table_name, col_names, 5, sample_year)
        
        if isinstance(sample_data, str):
            f.write(f"ERROR: {sample_data}\n")
        else:
            # Header
            header = " | ".join([f"{col[:15]:<15}" for col in col_names])
            f.write(header + "\n")
            f.write("-" * len(header) + "\n")
            
            # Rows
            for row in sample_data:
                row_str = " | ".join([
                    str(val)[:15].ljust(15) if val is not None else "NULL".ljust(15)
                    for val in row
                ])
                f.write(row_str + "\n")
        
        # Issues
        if issues:
            f.write(f"\nISSUES FOUND:\n")
            for issue in issues:
                f.write(f"{issue}\n")
        else:
            f.write(f"\n✓ No critical issues in this batch\n")
        
        f.write("\n")

def main():
    """Generate comprehensive report"""
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"reports/DATA_INTEGRITY_REPORT_{timestamp}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 120 + "\n")
        f.write("COMPREHENSIVE DATA INTEGRITY VERIFICATION REPORT\n")
        f.write("=" * 120 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Database: {DB_NAME}@{DB_HOST}\n\n")
        
        # Priority tables
        tables = ['charters', 'payments', 'receipts']
        
        sample_year = 2024
        f.write(f"Sample Year: {sample_year}\n\n")

        for table in tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            if cur.fetchone()[0]:
                analyze_table(cur, table, f, sample_year=sample_year)
                print(f"[OK] Analyzed {table}")
            else:
                f.write(f"\n[WARNING] Table '{table}' not found\n")
                print(f"[WARNING] Table '{table}' not found")
        
        f.write("\n" + "=" * 120 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 120 + "\n")
    
    cur.close()
    conn.close()
    
    print(f"\n✓ Report saved to: {report_file}")
    print(f"\nNow displaying CHARTERS table - Batch 1 (20 columns)...")
    
    # Show first batch of charters interactively
    display_charters_batch1(sample_year=2024)

def display_charters_batch1(sample_year=2024):
    """Display first 20 columns of charters for immediate review (default: 2024)"""
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("\n" + "=" * 120)
    print("CHARTERS TABLE - BATCH 1 (Columns 1-20)")
    print("=" * 120 + "\n")
    
    cur.execute("SELECT COUNT(*) FROM charters")
    print(f"Total charters: {cur.fetchone()[0]:,}\n")
    
    columns = ['charter_id', 'reserve_number', 'account_number', 'client_id', 'charter_date',
               'pickup_time', 'pickup_address', 'dropoff_address', 'passenger_count', 'vehicle',
               'driver', 'rate', 'driver_paid', 'driver_percentage', 'driver_total',
               'balance', 'deposit', 'status', 'closed', 'cancelled']
    
    # Show nulls
    print(f"{'Column':<25} {'Type':<20} {'% NULL':<10} {'Usage':<45} {'Source'}")
    print("-" * 120)
    for col in columns:
        stats = check_null_percentage(cur, 'charters', col)
        null_pct = stats[3] if stats[3] is not None else 0
        usage = get_column_usage('charters', col)
        source = get_column_source('charters', col)
        
        cur.execute(f"""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name='charters' AND column_name='{col}'
        """)
        dtype = cur.fetchone()[0]
        
        print(f"{col:<25} {dtype:<20} {null_pct:>7.1f}%  {usage:<45} {source}")
    
    # Show sample
    print(f"\nSample Data (5 charters from {sample_year}):")
    print("-" * 120)
    
    col_str = ', '.join([f'"{c}"' for c in columns])
    cur.execute(
        f"""
        SELECT {col_str}
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
        ORDER BY charter_date DESC
        LIMIT 5
        """,
        (f"{sample_year}-01-01", f"{sample_year + 1}-01-01")
    )
    
    for row in cur.fetchall():
        print(f"\nCharter ID: {row[0]}")
        for i, col in enumerate(columns[1:], 1):
            val = row[i] if row[i] is not None else "NULL"
            print(f"  {col}: {val}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
