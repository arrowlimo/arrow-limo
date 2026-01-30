"""
Get comprehensive overview of almsdata database contents.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Get all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE' 
    ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]

print("=" * 80)
print(f"ALMSDATA DATABASE OVERVIEW - {len(tables)} TABLES")
print("=" * 80)

# Group tables by category
categories = {
    'Core Business': [],
    'Financial': [],
    'Employee/Payroll': [],
    'Vehicle': [],
    'Banking': [],
    'Staging': [],
    'Backup': [],
    'Other': []
}

for table in tables:
    if any(x in table for x in ['charter', 'client', 'booking', 'reservation']):
        categories['Core Business'].append(table)
    elif any(x in table for x in ['payment', 'receipt', 'journal', 'ledger', 'accounting', 'tax', 'invoice']):
        categories['Financial'].append(table)
    elif any(x in table for x in ['employee', 'driver', 'payroll', 't4', 'chauffeur']):
        categories['Employee/Payroll'].append(table)
    elif any(x in table for x in ['vehicle', 'fuel']):
        categories['Vehicle'].append(table)
    elif any(x in table for x in ['bank', 'cibc', 'transaction']):
        categories['Banking'].append(table)
    elif 'staging' in table:
        categories['Staging'].append(table)
    elif 'backup' in table:
        categories['Backup'].append(table)
    else:
        categories['Other'].append(table)

# Print each category
for category, table_list in categories.items():
    if table_list:
        print(f"\n{'=' * 80}")
        print(f"{category.upper()} ({len(table_list)} tables)")
        print(f"{'=' * 80}")
        print(f"{'Table Name':<45} {'Records':>15} {'Latest Date':>18}")
        print("-" * 80)
        
        for table in sorted(table_list):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                
                # Try to find a date column
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' 
                    AND (column_name LIKE '%date%' OR column_name LIKE '%created%')
                    ORDER BY ordinal_position 
                    LIMIT 1
                """)
                date_col = cur.fetchone()
                
                latest_date = 'N/A'
                if date_col:
                    try:
                        cur.execute(f"SELECT MAX({date_col[0]}) FROM {table}")
                        result = cur.fetchone()[0]
                        if result:
                            latest_date = str(result)[:10]
                    except:
                        pass
                
                print(f"{table:<45} {count:>15,} {latest_date:>18}")
            except Exception as e:
                print(f"{table:<45} {'ERROR':>15} {'':>18}")

# Overall summary
print("\n" + "=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)

# Key business metrics
metrics = [
    ("Charters (bookings)", "charters"),
    ("Clients (customers)", "clients"),
    ("Employees", "employees"),
    ("Vehicles", "vehicles"),
    ("Payments", "payments"),
    ("Receipts", "receipts"),
    ("Banking Transactions", "banking_transactions"),
    ("Driver Payroll Records", "driver_payroll"),
    ("Journal Entries", "journal"),
    ("Unified General Ledger", "unified_general_ledger"),
]

print(f"\n{'Metric':<30} {'Count':>15} {'Period':>20}")
print("-" * 80)

for name, table in metrics:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        
        # Try to get date range
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' 
            AND (column_name LIKE '%date%' OR column_name = 'year')
            ORDER BY ordinal_position 
            LIMIT 1
        """)
        date_col = cur.fetchone()
        
        period = 'N/A'
        if date_col:
            try:
                if date_col[0] == 'year':
                    cur.execute(f"SELECT MIN(year), MAX(year) FROM {table}")
                else:
                    cur.execute(f"SELECT MIN({date_col[0]}), MAX({date_col[0]}) FROM {table}")
                min_date, max_date = cur.fetchone()
                if min_date and max_date:
                    period = f"{str(min_date)[:10]} to {str(max_date)[:10]}"
            except:
                pass
        
        print(f"{name:<30} {count:>15,} {period:>20}")
    except:
        print(f"{name:<30} {'NOT FOUND':>15} {'':>20}")

cur.close()
conn.close()
