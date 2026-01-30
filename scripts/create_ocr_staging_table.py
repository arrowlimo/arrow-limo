#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create ocr_documents_staging table to track OCR'd documents and their processing.
"""

import os
import sys
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def create_ocr_staging_table(conn):
    """Create ocr_documents_staging table with all necessary columns."""
    
    cur = conn.cursor()
    
    print("Creating ocr_documents_staging table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ocr_documents_staging (
            id SERIAL PRIMARY KEY,
            source_file TEXT NOT NULL,
            file_hash VARCHAR(64) UNIQUE NOT NULL,
            doc_type VARCHAR(50),
            confidence DECIMAL(3,2),
            raw_text TEXT,
            corrected_text TEXT,
            file_size INTEGER,
            processed_at TIMESTAMP,
            imported_at TIMESTAMP,
            import_status VARCHAR(50) DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- For linking to imported records (nullable, no FK constraints for flexibility)
            linked_receipt_id INTEGER,
            linked_banking_id INTEGER,
            linked_journal_id INTEGER,
            linked_payroll_id INTEGER,
            
            -- Notes for manual linking/review
            import_notes TEXT
        )
    """)
    
    # Create indexes for performance
    print("Creating indexes...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocr_doc_type ON ocr_documents_staging(doc_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocr_status ON ocr_documents_staging(import_status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocr_processed ON ocr_documents_staging(processed_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ocr_hash ON ocr_documents_staging(file_hash)")
    
    conn.commit()
    
    # Report status
    cur.execute("SELECT COUNT(*) FROM ocr_documents_staging")
    count = cur.fetchone()[0]
    
    print(f"\n✓ ocr_documents_staging table ready ({count} existing records)")
    
    cur.close()

def main():
    conn = get_db_connection()
    try:
        create_ocr_staging_table(conn)
    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
