#!/usr/bin/env python3
"""
Import Charter Payment Reconciliation Data

This script parses the charter payment reconciliation report and imports
payment data into the payments table, linking charter payments to transactions.
"""

import sys
import re
import psycopg2
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres'
}

def connect_to_database():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def parse_charter_report(file_path):
    """Parse the charter payment reconciliation report."""
    charter_payments = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return []
    
    # Split into individual charter records
    charter_blocks = content.split('----------------------------------------------------------------------------------------------------')
    
    print(f"Found {len(charter_blocks)} charter blocks to process")
    
    for block_num, block in enumerate(charter_blocks):
        if block_num % 1000 == 0 and block_num > 0:
            print(f"Processed {block_num} charter blocks...")
            
        try:
            # Parse charter header
            charter_match = re.search(r'Client:\s*(.+?)\s+Charter#:\s*(\d+)\s+Date:\s*(\d{4}-\d{2}-\d{2})', block)
            if not charter_match:
                continue
                
            client_name = charter_match.group(1).strip()
            charter_id = charter_match.group(2)
            charter_date = charter_match.group(3)
            
            # Parse payment details
            payment_matches = re.findall(r'PaymentID:\s*(\d+),\s*Amount:\s*\$?([\d,]+\.?\d*),\s*Date:\s*(\d{4}-\d{2}-\d{2}),\s*Method:\s*(\w+),\s*Key:\s*(\w+)', block)
            
            for payment_match in payment_matches:
                payment_id = int(payment_match[0])
                amount_str = payment_match[1].replace(',', '')
                try:
                    amount = Decimal(amount_str)
                except InvalidOperation:
                    continue
                    
                payment_date = payment_match[2]
                payment_method = payment_match[3]
                payment_key = payment_match[4]
                
                charter_payment = {
                    'payment_id': payment_id,
                    'charter_id': charter_id,
                    'client_name': client_name,
                    'charter_date': charter_date,
                    'amount': amount,
                    'payment_date': payment_date,
                    'payment_method': payment_method,
                    'payment_key': payment_key,
                    'source': 'charter_reconciliation_report'
                }
                
                charter_payments.append(charter_payment)
                
        except Exception as e:
            print(f"Error parsing charter block {block_num}: {e}")
            continue
    
    print(f"Successfully parsed {len(charter_payments)} charter payment records")
    return charter_payments

def create_charter_payments_table(conn):
    """Create table for charter payment reconciliation data."""
    try:
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS charter_payments (
            id SERIAL PRIMARY KEY,
            payment_id INTEGER,
            charter_id VARCHAR(20),
            client_name VARCHAR(255),
            charter_date DATE,
            amount DECIMAL(10,2),
            payment_date DATE,
            payment_method VARCHAR(50),
            payment_key VARCHAR(50),
            source VARCHAR(100),
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(payment_id, charter_id, payment_date, amount)
        );
        """
        
        cursor.execute(create_table_sql)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_charter_payments_payment_id ON charter_payments(payment_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_charter_payments_charter_id ON charter_payments(charter_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_charter_payments_date ON charter_payments(payment_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_charter_payments_key ON charter_payments(payment_key);")
        
        conn.commit()
        print("Charter payments table created successfully")
        
    except Exception as e:
        print(f"Error creating charter payments table: {e}")
        conn.rollback()

def import_charter_payments(conn, charter_payments):
    """Import charter payment data into database."""
    if not charter_payments:
        print("No charter payments to import")
        return 0
        
    cursor = conn.cursor()
    inserted_count = 0
    duplicate_count = 0
    error_count = 0
    
    insert_sql = """
    INSERT INTO charter_payments 
    (payment_id, charter_id, client_name, charter_date, amount, payment_date, payment_method, payment_key, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (payment_id, charter_id, payment_date, amount) DO NOTHING
    """
    
    for i, payment in enumerate(charter_payments):
        if i % 1000 == 0:
            print(f"Importing charter payment {i+1}/{len(charter_payments)}...")
            
        try:
            cursor.execute(insert_sql, (
                payment['payment_id'],
                payment['charter_id'],
                payment['client_name'],
                payment['charter_date'],
                payment['amount'],
                payment['payment_date'],
                payment['payment_method'],
                payment['payment_key'],
                payment['source']
            ))
            
            if cursor.rowcount > 0:
                inserted_count += 1
            else:
                duplicate_count += 1
                
        except Exception as e:
            print(f"Error importing charter payment {i}: {e}")
            error_count += 1
            continue
    
    try:
        conn.commit()
        print(f"Charter payments import completed:")
        print(f"  Inserted: {inserted_count}")
        print(f"  Duplicates skipped: {duplicate_count}")
        print(f"  Errors: {error_count}")
        
    except Exception as e:
        print(f"Error committing charter payments: {e}")
        conn.rollback()
        return 0
    
    return inserted_count

def link_charter_payments_to_existing(conn):
    """Link charter payments to existing payments table by amount and date."""
    try:
        cursor = conn.cursor()
        
        # Find matches between charter payments and existing payments
        link_sql = """
        WITH matches AS (
            SELECT 
                cp.id as charter_payment_id,
                cp.payment_id as charter_payment_id_ref,
                cp.amount,
                cp.payment_date,
                cp.payment_key,
                p.id as existing_payment_id,
                p.amount as existing_amount,
                p.transaction_date as existing_date,
                p.description
            FROM charter_payments cp
            JOIN payments p ON (
                ABS(cp.amount - p.amount) < 0.01
                AND cp.payment_date = p.transaction_date
            )
            WHERE cp.payment_key IS NOT NULL
        )
        SELECT COUNT(*) FROM matches;
        """
        
        cursor.execute(link_sql)
        match_count = cursor.fetchone()[0]
        
        print(f"Found {match_count} potential matches between charter payments and existing payments")
        
        # Update charter payments with linked payment IDs
        if match_count > 0:
            update_sql = """
            UPDATE charter_payments 
            SET linked_payment_id = subq.existing_payment_id
            FROM (
                SELECT 
                    cp.id as charter_payment_id,
                    p.id as existing_payment_id
                FROM charter_payments cp
                JOIN payments p ON (
                    ABS(cp.amount - p.amount) < 0.01
                    AND cp.payment_date = p.transaction_date
                )
                WHERE cp.payment_key IS NOT NULL
                  AND cp.linked_payment_id IS NULL
            ) subq
            WHERE charter_payments.id = subq.charter_payment_id;
            """
            
            # Add column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE charter_payments ADD COLUMN linked_payment_id INTEGER;")
                conn.commit()
            except:
                conn.rollback()  # Column might already exist
            
            cursor.execute(update_sql)
            updated_count = cursor.rowcount
            
            conn.commit()
            print(f"Linked {updated_count} charter payments to existing payment records")
        
    except Exception as e:
        print(f"Error linking charter payments: {e}")
        conn.rollback()

def main():
    """Main execution function."""
    print("=== Charter Payment Reconciliation Import ===")
    
    # File path
    charter_report_file = "l:/limo/outlook_all_emails_scan/attachments/other/20250918_charter_client_detailed_report.txt"
    
    print(f"Processing file: {charter_report_file}")
    
    # Parse the charter report
    print("Parsing charter payment reconciliation report...")
    charter_payments = parse_charter_report(charter_report_file)
    
    if not charter_payments:
        print("No charter payment data found to import")
        return
    
    # Connect to database
    print("Connecting to database...")
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return
    
    try:
        # Create table
        print("Creating charter payments table...")
        create_charter_payments_table(conn)
        
        # Import data
        print("Importing charter payment data...")
        imported_count = import_charter_payments(conn, charter_payments)
        
        if imported_count > 0:
            # Link to existing payments
            print("Linking charter payments to existing payment records...")
            link_charter_payments_to_existing(conn)
        
        print(f"\n=== Import Complete ===")
        print(f"Successfully imported {imported_count} charter payment records")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()