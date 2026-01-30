#!/usr/bin/env python3
"""
Comprehensive Data Integrity Verification
Reviews database tables column by column with sample data
"""
import psycopg2
from decimal import Decimal
import sys

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REDACTED***"

def get_table_columns(cur, table_name):
    """Get all columns for a table with data types"""
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cur.fetchall()

def get_sample_data(cur, table_name, columns, limit=5):
    """Get sample data for specified columns"""
    col_names = ', '.join([f'"{col}"' for col in columns])
    try:
        cur.execute(f"SELECT {col_names} FROM {table_name} LIMIT {limit}")
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
    """Describe where this column is used in the application"""
    usage_map = {
        'charters': {
            'charter_id': 'Primary Key - Links to payments, receipts, driver assignments',
            'reserve_number': 'BUSINESS KEY - Used for payment matching, customer reference',
            'account_number': 'Legacy LMS customer account identifier',
            'charter_date': 'Service date - Used in reports, scheduling, tax year grouping',
            'total_amount_due': 'Total invoice amount - Revenue reporting, balance calculations',
            'paid_amount': 'Customer payments received - Cash flow tracking',
            'balance': 'Amount outstanding - Receivables aging, collections',
            'status': 'Charter state - Filtering active/cancelled/closed bookings',
            'client_id': 'Links to clients table - Customer history, contact info',
            'vehicle': 'Vehicle assignment - Fleet utilization, maintenance scheduling',
            'driver': 'Driver assignment - Payroll, performance tracking',
            'rate': 'Base rate charged - Pricing analysis, margin calculations',
            'deposit': 'Deposit amount - Cash flow, prepayments',
            'retainer_received': 'Whether deposit was paid - Payment tracking',
            'retainer_amount': 'Deposit amount field - Duplicate of deposit?',
            'payment_status': 'Payment state - Receivables reporting',
            'client_display_name': 'Customer name - Invoices, reports, UI display',
            'driver_gratuity': 'Tips to driver - Payroll, tax reporting (excluded from revenue)',
            'pickup_location': 'Start address - Route planning, dispatch',
            'dropoff_location': 'End address - Route planning, dispatch',
            'pickup_time': 'Scheduled pickup - Dispatch scheduling',
            'dropoff_time': 'Scheduled dropoff - Dispatch scheduling',
            'notes': 'Special instructions - Operations, customer service',
        },
        'payments': {
            'payment_id': 'Primary Key - Payment record identifier',
            'reserve_number': 'BUSINESS KEY - Links to charter, critical for matching',
            'account_number': 'Customer account - Legacy LMS reference',
            'amount': 'Payment amount - Revenue recognition, cash flow',
            'payment_date': 'Date received - Cash flow timing, aging',
            'payment_method': 'How paid (cash/card/transfer) - Reconciliation, deposit tracking',
            'payment_key': 'Unique transaction ID - Deduplication, audit trail',
            'status': 'Payment state - Active/refunded/cancelled',
            'notes': 'Payment details - Audit trail, reconciliation notes',
            'banking_transaction_id': 'Links to bank statement - Reconciliation verification',
            'client_id': 'Customer link - Payment history',
        },
        'receipts': {
            'receipt_id': 'Primary Key - Expense record identifier',
            'vendor_name': 'Vendor/supplier - Expense categorization, 1099 tracking',
            'gross_amount': 'Total with tax - Expense reporting',
            'net_amount': 'Amount before tax - Tax reporting',
            'gst_amount': 'GST/tax paid - Tax recovery claims',
            'receipt_date': 'Date of expense - Tax year, cash flow',
            'category': 'Expense type - P&L categorization, tax deductions',
            'payment_method': 'How paid - Cash tracking, credit card reconciliation',
        }
    }
    
    return usage_map.get(table_name, {}).get(column_name, 'Usage not documented')

def review_table(cur, table_name, batch_size=10):
    """Review a table in batches of columns"""
    print(f"\n{'=' * 100}")
    print(f"REVIEWING TABLE: {table_name.upper()}")
    print(f"{'=' * 100}\n")
    
    # Get total record count
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_records = cur.fetchone()[0]
    print(f"Total Records: {total_records:,}\n")
    
    # Get all columns
    columns = get_table_columns(cur, table_name)
    
    # Process in batches
    for batch_num, i in enumerate(range(0, len(columns), batch_size), 1):
        batch = columns[i:i+batch_size]
        col_names = [col[0] for col in batch]
        
        print(f"\n{'-' * 100}")
        print(f"BATCH {batch_num}: Columns {i+1}-{min(i+batch_size, len(columns))} of {len(columns)}")
        print(f"{'-' * 100}\n")
        
        # Display column info
        print(f"{'Column Name':<30} {'Type':<25} {'Nullable':<10} {'Null %':<10}")
        print("-" * 100)
        
        null_issues = []
        for col_name, data_type, is_nullable in batch:
            stats = check_null_percentage(cur, table_name, col_name)
            null_pct = stats[3] if stats[3] is not None else 0
            
            nullable_display = "YES" if is_nullable == "YES" else "NO"
            print(f"{col_name:<30} {data_type:<25} {nullable_display:<10} {null_pct:>8.1f}%")
            
            # Flag significant null percentages in required fields
            if null_pct > 50 and is_nullable == "NO":
                null_issues.append((col_name, null_pct))
        
        print()
        
        # Show usage for each column
        print("COLUMN USAGE:")
        print("-" * 100)
        for col_name, _, _ in batch:
            usage = get_column_usage(table_name, col_name)
            print(f"  {col_name}: {usage}")
        
        print()
        
        # Show sample data
        print("SAMPLE DATA (5 rows):")
        print("-" * 100)
        
        sample_data = get_sample_data(cur, table_name, col_names, 5)
        
        if isinstance(sample_data, str):
            print(f"ERROR: {sample_data}")
        else:
            # Print header
            header = " | ".join([f"{col[:12]:<12}" for col in col_names])
            print(header)
            print("-" * len(header))
            
            # Print rows
            for row in sample_data:
                row_str = " | ".join([
                    str(val)[:12].ljust(12) if val is not None else "NULL".ljust(12)
                    for val in row
                ])
                print(row_str)
        
        print()
        
        # Report null issues
        if null_issues:
            print("⚠️  NULL VALUE WARNINGS:")
            for col, pct in null_issues:
                print(f"  - {col}: {pct:.1f}% NULL (marked as NOT NULL in schema)")
        
        # Pause for review
        if i + batch_size < len(columns):
            response = input(f"\nPress ENTER to continue to next batch, 'q' to quit, 's' to skip to next table: ").strip().lower()
            if response == 'q':
                return False
            elif response == 's':
                return True
    
    return True

def main():
    """Main verification process"""
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("COMPREHENSIVE DATA INTEGRITY VERIFICATION")
    print("=" * 100)
    print("\nThis tool reviews database tables column by column.")
    print("For each batch of 10 columns, you'll see:")
    print("  1. Column data types and NULL percentages")
    print("  2. Where each column is used in the application")
    print("  3. 5 sample rows of actual data")
    print()
    
    # Key tables to review in order of importance
    tables = [
        'charters',
        'payments',
        'receipts',
        'banking_transactions',
        'employees',
        'vehicles',
        'clients',
    ]
    
    for table in tables:
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table,))
        
        if not cur.fetchone()[0]:
            print(f"\n⚠️  Table '{table}' does not exist, skipping...")
            continue
        
        continue_review = review_table(cur, table)
        if not continue_review:
            print("\nReview stopped by user.")
            break
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("VERIFICATION COMPLETE")
    print("=" * 100)

if __name__ == "__main__":
    main()
