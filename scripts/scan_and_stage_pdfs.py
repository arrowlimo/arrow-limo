#!/usr/bin/env python3
"""
Scan and stage PDF files from L:\limo\pdf for processing
Creates staging records for batch PDF parsing and data extraction
"""
import os
import psycopg2
from pathlib import Path
from datetime import datetime
import hashlib

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def get_file_hash(filepath):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def categorize_pdf(filename):
    """Categorize PDF based on filename patterns"""
    filename_lower = filename.lower()
    
    # Insurance documents
    if any(x in filename_lower for x in ['insurance', 'policy', 'pink card', 'coverage', 'endorsement', 'broker']):
        return 'insurance'
    
    # Payroll documents
    if any(x in filename_lower for x in ['payroll', 'pay stub', 'pay cheque', 'pd7a', 'pda', 'pdta', 't4']):
        return 'payroll'
    
    # Banking/statements
    if any(x in filename_lower for x in ['statement', 'cibc', 'rbc', 'capital', 'mastercard', 'visa']):
        return 'banking'
    
    # Vehicle documents
    if any(x in filename_lower for x in ['vehicle', 'lease', 'bill of sale', 'registration', 'vin', 'heffner']):
        return 'vehicle'
    
    # Receipts
    if any(x in filename_lower for x in ['receipt', 'invoice', 'bill', 'fas gas', 'shell', 'esso', 'petro']):
        return 'receipt'
    
    # Tax/accounting
    if any(x in filename_lower for x in ['tax', 'cra', 't2', 'balance sheet', 'p&l', 'quickbooks']):
        return 'accounting'
    
    # Contracts/agreements
    if any(x in filename_lower for x in ['contract', 'agreement', 'lease agreement']):
        return 'contract'
    
    return 'other'

def create_staging_table(cur):
    """Create PDF staging table if it doesn't exist"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pdf_staging (
            id SERIAL PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size BIGINT,
            file_hash TEXT UNIQUE,
            category TEXT,
            date_detected DATE,
            year_detected INTEGER,
            status TEXT DEFAULT 'pending',
            processing_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            extracted_data JSONB
        )
    """)
    
    # Create index on hash for duplicate detection
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pdf_staging_hash 
        ON pdf_staging(file_hash)
    """)
    
    # Create index on status for querying pending files
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pdf_staging_status 
        ON pdf_staging(status)
    """)

def extract_date_from_filename(filename):
    """Try to extract date from filename"""
    import re
    
    # Pattern: YYYY-MM-DD or YYYY_MM_DD (try this first - standard format)
    match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', filename)
    if match:
        year, month, day = match.groups()
        try:
            if 2000 <= int(year) <= 2025 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                return f"{year}-{month}-{day}", int(year)
        except:
            pass
    
    # Pattern: MMDDYYYY (8 digits in sequence)
    match = re.search(r'(\d{2})(\d{2})(\d{4})', filename)
    if match:
        month, day, year = match.groups()
        try:
            if 2000 <= int(year) <= 2025 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                return f"{year}-{month}-{day}", int(year)
        except:
            pass
    
    # Pattern: Month YYYY or Month.YYYY
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    for month_name, month_num in months.items():
        pattern = rf'{month_name}[\s._-]*(\d{{4}})'
        match = re.search(pattern, filename.lower())
        if match:
            year = match.group(1)
            return f"{year}-{month_num}-01", int(year)
    
    # Pattern: YYYY only
    match = re.search(r'(\d{4})', filename)
    if match:
        year = match.group(1)
        if 2000 <= int(year) <= 2025:
            return None, int(year)
    
    return None, None

def main():
    pdf_dir = Path('L:/limo/pdf')
    
    print("="*70)
    print("PDF SCANNING AND STAGING")
    print("="*70)
    
    if not pdf_dir.exists():
        print(f"[FAIL] Directory not found: {pdf_dir}")
        return
    
    # Find all PDFs
    pdf_files = list(pdf_dir.glob('*.pdf'))
    print(f"\n📁 Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    # Connect to database
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()
    
    # Create staging table
    print("\n🗄️  Creating staging table...")
    create_staging_table(cur)
    conn.commit()
    print("[OK] Staging table ready")
    
    # Check for existing staged files
    cur.execute("SELECT COUNT(*) FROM pdf_staging")
    existing_count = cur.fetchone()[0]
    print(f"📊 Existing staged files: {existing_count}")
    
    # Category statistics
    categories = {}
    new_files = 0
    duplicate_files = 0
    errors = []
    
    print(f"\n🔍 Scanning and staging PDF files...")
    
    for i, pdf_path in enumerate(pdf_files, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(pdf_files)} files scanned...")
        
        try:
            # Get file info
            file_size = pdf_path.stat().st_size
            file_hash = get_file_hash(pdf_path)
            category = categorize_pdf(pdf_path.name)
            date_str, year = extract_date_from_filename(pdf_path.name)
            
            # Track categories
            categories[category] = categories.get(category, 0) + 1
            
            # Check if already staged
            cur.execute("""
                SELECT id, status FROM pdf_staging 
                WHERE file_hash = %s
            """, (file_hash,))
            
            existing = cur.fetchone()
            if existing:
                duplicate_files += 1
                continue
            
            # Insert into staging
            cur.execute("""
                INSERT INTO pdf_staging (
                    file_path, file_name, file_size, file_hash,
                    category, date_detected, year_detected, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(pdf_path),
                pdf_path.name,
                file_size,
                file_hash,
                category,
                date_str,
                year,
                'pending'
            ))
            
            new_files += 1
            
        except Exception as e:
            errors.append(f"{pdf_path.name}: {str(e)}")
    
    conn.commit()
    
    # Summary
    print("\n" + "="*70)
    print("STAGING SUMMARY")
    print("="*70)
    print(f"Total PDFs scanned: {len(pdf_files)}")
    print(f"New files staged: {new_files}")
    print(f"Duplicates skipped: {duplicate_files}")
    print(f"Total staged files: {existing_count + new_files}")
    
    print(f"\n📊 Files by category:")
    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category:15} {count:5} files")
    
    if errors:
        print(f"\n[WARN]  Errors ({len(errors)}):")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    # Status breakdown
    print(f"\n📋 Processing status:")
    cur.execute("""
        SELECT status, COUNT(*) 
        FROM pdf_staging 
        GROUP BY status 
        ORDER BY COUNT(*) DESC
    """)
    for status, count in cur.fetchall():
        print(f"  {status:15} {count:5} files")
    
    # Year distribution
    print(f"\n📅 Files by year:")
    cur.execute("""
        SELECT year_detected, COUNT(*) 
        FROM pdf_staging 
        WHERE year_detected IS NOT NULL
        GROUP BY year_detected 
        ORDER BY year_detected
    """)
    year_data = cur.fetchall()
    if year_data:
        for year, count in year_data:
            print(f"  {year}: {count:5} files")
    else:
        print("  No year information extracted")
    
    print(f"\n[OK] PDF staging complete!")
    print(f"\n📋 Next steps:")
    print(f"  1. Review staged files: SELECT * FROM pdf_staging WHERE status='pending' LIMIT 10")
    print(f"  2. Process by category: SELECT * FROM pdf_staging WHERE category='insurance'")
    print(f"  3. Start extraction: python scripts/extract_staged_pdfs.py")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
