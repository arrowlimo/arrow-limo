#!/usr/bin/env python3
"""
Archive QuickBooks receipts to backup and delete from database
Keep only verified banking, email, and Square records
"""
import psycopg2
import pandas as pd
from datetime import datetime
import os

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("ARCHIVE QUICKBOOKS RECEIPTS - BACKUP AND DELETE")
    print("Keeping only: verified_banking, BANKING_IMPORT (from verified banks), Square")
    print("="*100)
    
    # Identify QuickBooks-sourced records
    print("\nIdentifying QuickBooks-sourced receipts...")
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            gst_amount,
            net_amount,
            payment_method,
            source_system,
            source_reference,
            banking_transaction_id,
            created_from_banking,
            vehicle_id,
            category
        FROM receipts
        WHERE source_system LIKE '%general_ledger%'
           OR source_system LIKE '%quickbooks%'
           OR source_system LIKE '%LEGACY%'
           OR (source_system = 'BANKING_IMPORT' AND banking_transaction_id IS NULL)
           OR source_reference LIKE '%GL ID%'
        ORDER BY receipt_date, receipt_id
    """)
    
    qb_receipts = cur.fetchall()
    
    print(f"\nFound {len(qb_receipts)} QuickBooks-sourced receipts to archive")
    
    if not qb_receipts:
        print("\nNo QuickBooks receipts found. Nothing to archive.")
        cur.close()
        conn.close()
        return
    
    # Calculate totals
    total_amount = sum(float(r[4]) if r[4] else 0 for r in qb_receipts)
    
    print(f"Total amount: ${total_amount:,.2f}")
    
    # Show breakdown by source
    cur.execute("""
        SELECT 
            source_system,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE source_system LIKE '%general_ledger%'
           OR source_system LIKE '%quickbooks%'
           OR source_system LIKE '%LEGACY%'
           OR (source_system = 'BANKING_IMPORT' AND banking_transaction_id IS NULL)
           OR source_reference LIKE '%GL ID%'
        GROUP BY source_system
        ORDER BY COUNT(*) DESC
    """)
    
    breakdown = cur.fetchall()
    
    print("\nBreakdown by source:")
    for source, count, total in breakdown:
        total_str = f"${total:,.2f}" if total else "NULL"
        print(f"  {source or 'NULL'}: {count:,} receipts, {total_str}")
    
    # Create backup directory
    backup_dir = "l:/limo/backups/quickbooks_archive"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Export to CSV
    print(f"\n{'='*100}")
    print("CREATING BACKUP FILES")
    print(f"{'='*100}")
    
    csv_file = f"{backup_dir}/quickbooks_receipts_archive_{timestamp}.csv"
    
    # Convert to DataFrame
    columns = [
        'receipt_id', 'receipt_date', 'vendor_name', 'description',
        'gross_amount', 'gst_amount', 'net_amount', 'payment_method',
        'source_system', 'source_reference', 'banking_transaction_id',
        'created_from_banking', 'vehicle_id', 'category'
    ]
    
    df = pd.DataFrame(qb_receipts, columns=columns)
    df.to_csv(csv_file, index=False)
    
    print(f"\nCSV backup created: {csv_file}")
    print(f"  Rows: {len(df):,}")
    
    # Create SQL backup
    sql_file = f"{backup_dir}/quickbooks_receipts_archive_{timestamp}.sql"
    
    with open(sql_file, 'w', encoding='utf-8') as f:
        f.write("-- QuickBooks Receipts Archive\n")
        f.write(f"-- Created: {datetime.now()}\n")
        f.write(f"-- Total receipts: {len(qb_receipts):,}\n")
        f.write(f"-- Total amount: ${total_amount:,.2f}\n\n")
        
        f.write("-- To restore: Run this SQL against almsdata database\n\n")
        
        # Create archived receipts table
        f.write("CREATE TABLE IF NOT EXISTS archived_quickbooks_receipts (\n")
        f.write("    receipt_id INTEGER,\n")
        f.write("    receipt_date DATE,\n")
        f.write("    vendor_name TEXT,\n")
        f.write("    description TEXT,\n")
        f.write("    gross_amount NUMERIC(10,2),\n")
        f.write("    gst_amount NUMERIC(10,2),\n")
        f.write("    net_amount NUMERIC(10,2),\n")
        f.write("    payment_method TEXT,\n")
        f.write("    source_system TEXT,\n")
        f.write("    source_reference TEXT,\n")
        f.write("    banking_transaction_id INTEGER,\n")
        f.write("    created_from_banking BOOLEAN,\n")
        f.write("    vehicle_id INTEGER,\n")
        f.write("    category TEXT,\n")
        f.write("    archived_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n")
        f.write(");\n\n")
        
        f.write("-- Insert archived receipts\n")
        f.write("INSERT INTO archived_quickbooks_receipts \n")
        f.write("(receipt_id, receipt_date, vendor_name, description, gross_amount, ")
        f.write("gst_amount, net_amount, payment_method, source_system, source_reference, ")
        f.write("banking_transaction_id, created_from_banking, vehicle_id, category)\n")
        f.write("VALUES\n")
        
        for i, row in enumerate(qb_receipts):
            values = []
            for val in row:
                if val is None:
                    values.append("NULL")
                elif isinstance(val, str):
                    # Escape single quotes
                    escaped = val.replace("'", "''")
                    values.append(f"'{escaped}'")
                elif isinstance(val, bool):
                    values.append("TRUE" if val else "FALSE")
                else:
                    values.append(str(val))
            
            line = f"({', '.join(values)})"
            if i < len(qb_receipts) - 1:
                line += ","
            else:
                line += ";"
            
            f.write(line + "\n")
    
    print(f"SQL backup created: {sql_file}")
    
    # Verify backups exist
    if not os.path.exists(csv_file) or not os.path.exists(sql_file):
        print("\nERROR: Backup files not created properly!")
        print("ABORTING - will not delete records")
        cur.close()
        conn.close()
        return
    
    print(f"\n{'='*100}")
    print("BACKUPS VERIFIED - Ready to delete from database")
    print(f"{'='*100}")
    
    # Show what will remain
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE NOT (
            source_system LIKE '%general_ledger%'
            OR source_system LIKE '%quickbooks%'
            OR source_system LIKE '%LEGACY%'
            OR (source_system = 'BANKING_IMPORT' AND banking_transaction_id IS NULL)
            OR source_reference LIKE '%GL ID%'
        )
    """)
    
    remaining_count, remaining_total = cur.fetchone()
    
    print(f"\nCurrent database:")
    print(f"  Total receipts: {len(qb_receipts) + (remaining_count or 0):,}")
    
    print(f"\nAfter deletion:")
    print(f"  Receipts to DELETE: {len(qb_receipts):,} (${total_amount:,.2f})")
    remaining_total_str = f"${remaining_total:,.2f}" if remaining_total else "$0.00"
    print(f"  Receipts to KEEP: {remaining_count or 0:,} ({remaining_total_str})")
    
    print(f"\n{'='*100}")
    print("DELETING QUICKBOOKS RECEIPTS FROM DATABASE")
    print(f"{'='*100}")
    
    # Delete QuickBooks receipts
    cur.execute("""
        DELETE FROM receipts
        WHERE source_system LIKE '%general_ledger%'
           OR source_system LIKE '%quickbooks%'
           OR source_system LIKE '%LEGACY%'
           OR (source_system = 'BANKING_IMPORT' AND banking_transaction_id IS NULL)
           OR source_reference LIKE '%GL ID%'
    """)
    
    deleted_count = cur.rowcount
    
    print(f"\nDeleted {deleted_count:,} QuickBooks receipts")
    
    # Commit the deletion
    conn.commit()
    print("\nCOMMITTED - QuickBooks receipts deleted")
    
    # Verify deletion
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE source_system LIKE '%general_ledger%'
           OR source_system LIKE '%quickbooks%'
           OR source_reference LIKE '%GL ID%'
    """)
    
    remaining_qb = cur.fetchone()[0]
    
    print(f"\n{'='*100}")
    print("VERIFICATION")
    print(f"{'='*100}")
    
    if remaining_qb == 0:
        print(f"\nSUCCESS: All QuickBooks receipts removed")
        print(f"  Archived: {deleted_count:,} receipts")
        print(f"  Backup files:")
        print(f"    - {csv_file}")
        print(f"    - {sql_file}")
    else:
        print(f"\nWARNING: {remaining_qb} QuickBooks receipts still in database")
    
    # Show final database status
    cur.execute("""
        SELECT source_system, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE source_system IS NOT NULL
        GROUP BY source_system
        ORDER BY COUNT(*) DESC
    """)
    
    final_sources = cur.fetchall()
    
    print(f"\nFinal database (verified sources only):")
    for source, count, total in final_sources:
        total_str = f"${total:,.2f}" if total else "NULL"
        print(f"  {source}: {count:,} receipts, {total_str}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
