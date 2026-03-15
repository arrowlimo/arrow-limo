"""
Critical backup - Focus on recently modified data and key tables
"""
import psycopg2
from datetime import datetime
import os

def backup_table(cur, table_name, output_dir):
    """Backup a single table to SQL file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{output_dir}/{table_name}_backup_{timestamp}.sql"
    
    print(f"  Backing up {table_name}...")
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"-- Backup of {table_name}\n")
        f.write(f"-- Created: {datetime.now()}\n\n")
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        f.write(f"-- Total rows: {count:,}\n\n")
        
        if count == 0:
            print(f"    (empty table)")
            return filename
        
        # Get column names
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        
        # Export data with COPY
        copy_sql = f"COPY {table_name} ({', '.join(columns)}) TO STDOUT WITH CSV HEADER"
        csv_file = filename.replace('.sql', '.csv')
        
        with open(csv_file, 'w', encoding='utf-8') as csv_f:
            cur.copy_expert(copy_sql, csv_f)
        
        f.write(f"-- Data exported to: {os.path.basename(csv_file)}\n")
        f.write(f"-- To restore: \\COPY {table_name} ({', '.join(columns)}) FROM '{csv_file}' WITH CSV HEADER\n")
        
        print(f"    ✅ {count:,} rows backed up")
    
    return filename

def main():
    print("=" * 80)
    print("CRITICAL DATA BACKUP")
    print("=" * 80)
    
    # Create backup directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f'l:/limo/backups/critical_backup_{timestamp}'
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nBackup directory: {output_dir}")
    
    # Connect to database
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    # Critical tables to backup
    critical_tables = [
        'charters',           # Core bookings data
        'payments',           # Payment records
        'receipts',           # Expense receipts
        'clients',            # Customer data
        'employees',          # Staff data
        'vehicles',           # Fleet data
        'driver_payroll',     # Payroll records
        'banking_transactions',  # Bank statement data
    ]
    
    print("\n" + "=" * 80)
    print("BACKING UP CRITICAL TABLES")
    print("=" * 80)
    
    backup_files = []
    
    for table in critical_tables:
        try:
            filename = backup_table(cur, table, output_dir)
            backup_files.append(filename)
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    # Backup recent work - Scotia 2012 analysis
    print("\n" + "=" * 80)
    print("BACKING UP SCOTIA 2012 DATA")
    print("=" * 80)
    
    # Export Scotia 2012 receipts
    print("  Exporting Scotia 2012 receipts...")
    scotia_file = f"{output_dir}/scotia_2012_receipts_{timestamp}.csv"
    
    with open(scotia_file, 'w', encoding='utf-8') as f:
        cur.copy_expert("""
            COPY (
                SELECT 
                    receipt_id,
                    receipt_date,
                    vendor_name,
                    description,
                    gross_amount,
                    gst_amount,
                    net_amount,
                    category,
                    payment_method,
                    banking_transaction_id
                FROM receipts
                WHERE mapped_bank_account_id = 2
                AND EXTRACT(YEAR FROM receipt_date) = 2012
                ORDER BY receipt_date
            ) TO STDOUT WITH CSV HEADER
        """, f)
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE mapped_bank_account_id = 2
        AND EXTRACT(YEAR FROM receipt_date) = 2012
    """)
    result = cur.fetchone()
    print(f"    ✅ {result[0]:,} receipts (${result[1]:,.2f}) backed up")
    
    # Export Scotia 2012 banking transactions
    print("  Exporting Scotia 2012 banking...")
    banking_file = f"{output_dir}/scotia_2012_banking_{timestamp}.csv"
    
    with open(banking_file, 'w', encoding='utf-8') as f:
        cur.copy_expert("""
            COPY (
                SELECT *
                FROM banking_transactions
                WHERE account_number = '903990106011'
                AND EXTRACT(YEAR FROM transaction_date) = 2012
                ORDER BY transaction_date
            ) TO STDOUT WITH CSV HEADER
        """, f)
    
    cur.execute("""
        SELECT COUNT(*), 
               SUM(credit_amount), 
               SUM(debit_amount)
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    result = cur.fetchone()
    print(f"    ✅ {result[0]:,} transactions (Credits: ${result[1]:,.2f}, Debits: ${result[2]:,.2f})")
    
    # Create backup manifest
    manifest_file = f"{output_dir}/BACKUP_MANIFEST.txt"
    with open(manifest_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("CRITICAL DATA BACKUP MANIFEST\n")
        f.write("=" * 80 + "\n")
        f.write(f"Created: {datetime.now()}\n")
        f.write(f"Database: almsdata\n")
        f.write(f"Host: localhost\n\n")
        
        f.write("BACKED UP TABLES:\n")
        f.write("-" * 80 + "\n")
        for table in critical_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            f.write(f"  {table}: {count:,} rows\n")
        
        f.write("\nSPECIAL EXPORTS:\n")
        f.write("-" * 80 + "\n")
        f.write(f"  Scotia 2012 receipts: {scotia_file}\n")
        f.write(f"  Scotia 2012 banking: {banking_file}\n")
        
        f.write("\nRESTORE INSTRUCTIONS:\n")
        f.write("-" * 80 + "\n")
        f.write("To restore a table:\n")
        f.write("  1. Locate the corresponding CSV file\n")
        f.write("  2. Use: \\COPY table_name FROM 'file.csv' WITH CSV HEADER\n")
        f.write("  3. Or use pgAdmin import tool\n")
    
    print("\n" + "=" * 80)
    print("BACKUP COMPLETE")
    print("=" * 80)
    print(f"\nLocation: {output_dir}")
    print(f"Manifest: {manifest_file}")
    print("\n✅ All critical data backed up successfully!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
