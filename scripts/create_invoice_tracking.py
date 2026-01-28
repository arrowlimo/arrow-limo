#!/usr/bin/env python3
"""
Create Invoice Tracking System

This script analyzes financial documents found in the email attachments
and creates tables to track invoice numbers, dates, and file references.
"""

import sys
import re
import os
import psycopg2
from datetime import datetime
from decimal import Decimal

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

def scan_financial_files():
    """Scan the financial directory for invoice and receipt files."""
    financial_records = []
    
    # Path to financial directory
    financial_dir = "l:/limo/outlook_all_emails_scan/attachments/financial"
    
    if not os.path.exists(financial_dir):
        print(f"Financial directory not found: {financial_dir}")
        return []
    
    print(f"Scanning financial directory: {financial_dir}")
    
    # Walk through all files
    for root, dirs, files in os.walk(financial_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            file_size = os.path.getsize(file_path)
            
            # Parse filename for patterns
            record = parse_filename(filename, file_path, file_size)
            if record:
                financial_records.append(record)
    
    print(f"Found {len(financial_records)} financial files to track")
    return financial_records

def parse_filename(filename, file_path, file_size):
    """Parse filename to extract invoice/receipt information."""
    
    # Remove file extension
    base_name = os.path.splitext(filename)[0]
    
    # Try different filename patterns
    
    # Pattern 1: YYYYMMDD_invoice_number.pdf
    match = re.match(r'^(\d{8})_(\d+)\.pdf$', filename)
    if match:
        date_str = match.group(1)
        invoice_number = match.group(2)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()
            return {
                'file_name': filename,
                'file_path': file_path,
                'file_size': file_size,
                'document_date': file_date,
                'invoice_number': invoice_number,
                'document_type': 'invoice',
                'pattern': 'date_invoice_number'
            }
        except ValueError:
            pass
    
    # Pattern 2: YYYYMMDD_reservation_number.pdf
    match = re.match(r'^(\d{8})_(\d{6})\.pdf$', filename)
    if match:
        date_str = match.group(1)
        reservation_number = match.group(2)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()
            return {
                'file_name': filename,
                'file_path': file_path,
                'file_size': file_size,
                'document_date': file_date,
                'reservation_number': reservation_number,
                'document_type': 'reservation',
                'pattern': 'date_reservation'
            }
        except ValueError:
            pass
    
    # Pattern 3: YYYYMMDD_SCAN####.PDF
    match = re.match(r'^(\d{8})_SCAN(\d+)\.PDF$', filename)
    if match:
        date_str = match.group(1)
        scan_number = match.group(2)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()
            return {
                'file_name': filename,
                'file_path': file_path,
                'file_size': file_size,
                'document_date': file_date,
                'scan_number': scan_number,
                'document_type': 'scan',
                'pattern': 'date_scan'
            }
        except ValueError:
            pass
    
    # Pattern 4: YYYYMMDD_Invoice_...
    match = re.match(r'^(\d{8})_Invoice_(.+)\.pdf$', filename)
    if match:
        date_str = match.group(1)
        invoice_ref = match.group(2)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()
            return {
                'file_name': filename,
                'file_path': file_path,
                'file_size': file_size,
                'document_date': file_date,
                'reference': invoice_ref,
                'document_type': 'invoice',
                'pattern': 'date_invoice_ref'
            }
        except ValueError:
            pass
    
    # Pattern 5: YYYYMMDD_Receipt...
    match = re.match(r'^(\d{8})_Receipt.*\.pdf$', filename)
    if match:
        date_str = match.group(1)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()
            return {
                'file_name': filename,
                'file_path': file_path,
                'file_size': file_size,
                'document_date': file_date,
                'document_type': 'receipt',
                'pattern': 'date_receipt'
            }
        except ValueError:
            pass
    
    # Pattern 6: YYYYMMDD_INV#####...
    match = re.match(r'^(\d{8})_INV(\d+).*\.pdf$', filename)
    if match:
        date_str = match.group(1)
        invoice_number = match.group(2)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()
            return {
                'file_name': filename,
                'file_path': file_path,
                'file_size': file_size,
                'document_date': file_date,
                'invoice_number': invoice_number,
                'document_type': 'invoice',
                'pattern': 'date_inv_number'
            }
        except ValueError:
            pass
    
    # Pattern 7: Files with descriptive names
    if any(keyword in filename.lower() for keyword in ['invoice', 'receipt', 'payment', 'statement']):
        # Try to extract date from beginning
        match = re.match(r'^(\d{8})', filename)
        if match:
            date_str = match.group(1)
            try:
                file_date = datetime.strptime(date_str, '%Y%m%d').date()
                
                doc_type = 'document'
                if 'invoice' in filename.lower():
                    doc_type = 'invoice'
                elif 'receipt' in filename.lower():
                    doc_type = 'receipt'
                elif 'payment' in filename.lower():
                    doc_type = 'payment'
                elif 'statement' in filename.lower():
                    doc_type = 'statement'
                
                return {
                    'file_name': filename,
                    'file_path': file_path,
                    'file_size': file_size,
                    'document_date': file_date,
                    'document_type': doc_type,
                    'pattern': 'date_descriptive'
                }
            except ValueError:
                pass
    
    # If no pattern matches, still record basic info if it looks like a financial doc
    if filename.lower().endswith('.pdf'):
        return {
            'file_name': filename,
            'file_path': file_path,
            'file_size': file_size,
            'document_type': 'pdf_document',
            'pattern': 'unmatched'
        }
    
    return None

def create_invoice_tracking_tables(conn):
    """Create tables for invoice and document tracking."""
    try:
        cursor = conn.cursor()
        
        # Create financial documents table
        create_docs_sql = """
        CREATE TABLE IF NOT EXISTS financial_documents (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255) NOT NULL,
            file_path TEXT NOT NULL,
            file_size BIGINT,
            document_date DATE,
            document_type VARCHAR(50),
            invoice_number VARCHAR(50),
            reservation_number VARCHAR(50),
            scan_number VARCHAR(50),
            reference VARCHAR(255),
            pattern VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_path)
        );
        """
        
        cursor.execute(create_docs_sql)
        
        # Create invoice tracking table
        create_invoices_sql = """
        CREATE TABLE IF NOT EXISTS invoice_tracking (
            id SERIAL PRIMARY KEY,
            invoice_number VARCHAR(50) NOT NULL,
            invoice_date DATE,
            document_id INTEGER REFERENCES financial_documents(id),
            amount DECIMAL(10,2),
            status VARCHAR(20) DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_number, invoice_date)
        );
        """
        
        cursor.execute(create_invoices_sql)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_financial_docs_date ON financial_documents(document_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_financial_docs_type ON financial_documents(document_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_financial_docs_invoice ON financial_documents(invoice_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_tracking_number ON invoice_tracking(invoice_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_tracking_date ON invoice_tracking(invoice_date);")
        
        conn.commit()
        print("Invoice tracking tables created successfully")
        
    except Exception as e:
        print(f"Error creating invoice tracking tables: {e}")
        conn.rollback()

def import_financial_documents(conn, financial_records):
    """Import financial document records into database."""
    if not financial_records:
        print("No financial documents to import")
        return 0
        
    cursor = conn.cursor()
    inserted = 0
    duplicates = 0
    errors = 0
    
    # Insert financial documents
    docs_sql = """
    INSERT INTO financial_documents 
    (file_name, file_path, file_size, document_date, document_type, 
     invoice_number, reservation_number, scan_number, reference, pattern)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (file_path) DO NOTHING
    """
    
    for i, record in enumerate(financial_records):
        if i % 100 == 0:
            print(f"Importing document {i+1}/{len(financial_records)}...")
            
        try:
            cursor.execute(docs_sql, (
                record.get('file_name'),
                record.get('file_path'),
                record.get('file_size'),
                record.get('document_date'),
                record.get('document_type'),
                record.get('invoice_number'),
                record.get('reservation_number'),
                record.get('scan_number'),
                record.get('reference'),
                record.get('pattern')
            ))
            
            if cursor.rowcount > 0:
                inserted += 1
            else:
                duplicates += 1
                
        except Exception as e:
            print(f"Error importing document {i}: {e}")
            errors += 1
            continue
    
    # Create invoice tracking entries for documents with invoice numbers
    invoice_sql = """
    INSERT INTO invoice_tracking (invoice_number, invoice_date, document_id)
    SELECT fd.invoice_number, fd.document_date, fd.id
    FROM financial_documents fd
    WHERE fd.invoice_number IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM invoice_tracking it 
        WHERE it.invoice_number = fd.invoice_number 
        AND it.invoice_date = fd.document_date
    )
    """
    
    cursor.execute(invoice_sql)
    invoice_tracking_created = cursor.rowcount
    
    try:
        conn.commit()
        print(f"Financial documents import completed:")
        print(f"  Documents inserted: {inserted}")
        print(f"  Invoice tracking entries created: {invoice_tracking_created}")
        print(f"  Duplicates skipped: {duplicates}")
        print(f"  Errors: {errors}")
        
    except Exception as e:
        print(f"Error committing financial documents: {e}")
        conn.rollback()
        return 0
    
    return inserted

def analyze_patterns(financial_records):
    """Analyze filename patterns for reporting."""
    pattern_counts = {}
    type_counts = {}
    
    for record in financial_records:
        pattern = record.get('pattern', 'unknown')
        doc_type = record.get('document_type', 'unknown')
        
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
    
    print("\n=== Filename Pattern Analysis ===")
    for pattern, count in sorted(pattern_counts.items()):
        print(f"  {pattern}: {count} files")
    
    print("\n=== Document Type Analysis ===")
    for doc_type, count in sorted(type_counts.items()):
        print(f"  {doc_type}: {count} files")

def main():
    """Main execution function."""
    print("=== Invoice Tracking System Creation ===")
    
    # Scan for financial files
    print("Scanning financial documents...")
    financial_records = scan_financial_files()
    
    if not financial_records:
        print("No financial documents found to process")
        return
    
    # Analyze patterns
    analyze_patterns(financial_records)
    
    # Connect to database
    print("\nConnecting to database...")
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return
    
    try:
        # Create tables
        print("Creating invoice tracking tables...")
        create_invoice_tracking_tables(conn)
        
        # Import documents
        print("Importing financial documents...")
        imported_count = import_financial_documents(conn, financial_records)
        
        print(f"\n=== Import Complete ===")
        print(f"Successfully processed {len(financial_records)} financial documents")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()