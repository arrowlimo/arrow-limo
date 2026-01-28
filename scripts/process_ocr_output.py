#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Process OCR output from PDF24 and classify documents for import.

Handles:
- Text extraction from OCR'd PDFs and text files
- Document type classification (receipts, statements, QB reports, tax forms)
- Common OCR error correction (character substitutions)
- Staging into ocr_documents_staging table
- Routing to appropriate import pipelines
"""

import os
import sys
import re
import hashlib
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
import argparse

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# OCR error correction patterns
OCR_CORRECTIONS = {
    # Common character misreads
    r'\b1NV\b': 'INV',  # Invoice
    r'\bNV\b': 'INV',
    r'\b0(\d)': r'O\1',  # Zero as O in dates
    r'(\d)l': r'\g<1>1',  # lowercase L as 1
    r'(\d)O': r'\g<1>0',  # O as zero in numbers
    r'\$\s*([Oo0])': r'$\1',  # Dollar signs
    # Date separators
    r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})': r'\1/\2/\3',
    # Amount patterns (preserve decimals)
    r'(\d),(\d{3})': r'\1\2',  # Remove comma thousands
}

def correct_ocr_text(text):
    """Apply common OCR error corrections."""
    corrected = text
    for pattern, replacement in OCR_CORRECTIONS.items():
        corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
    return corrected

def classify_document(filename, text):
    """
    Classify document type based on filename and content patterns.
    
    Returns: (doc_type, confidence)
    """
    fname_lower = filename.lower()
    text_lower = text.lower()
    
    # Payroll patterns
    if any(x in fname_lower for x in ['pd7a', 'pdta', 'payroll', 'paystub', 't4']):
        return ('payroll', 0.95)
    if re.search(r'(payroll|remittance|t4|pd7a)', text_lower):
        return ('payroll', 0.85)
    
    # QuickBooks reports
    if any(x in fname_lower for x in ['arrow limousine 20', 'profit', 'balance sheet', 'general ledger', 'journal']):
        return ('quickbooks', 0.95)
    if re.search(r'(profit\s*and\s*loss|balance\s*sheet|general\s*ledger|trial\s*balance)', text_lower):
        return ('quickbooks', 0.85)
    
    # Banking statements
    if any(x in fname_lower for x in ['cibc', 'statement', 'chequing', 'mastercard', 'triangle']):
        return ('banking', 0.95)
    if re.search(r'(account\s*number|statement\s*period|beginning\s*balance)', text_lower):
        return ('banking', 0.85)
    
    # Tax documents
    if any(x in fname_lower for x in ['t4', 'cra', 'gst', 'hst', 'efile']):
        return ('tax', 0.95)
    if re.search(r'(canada\s*revenue|tax\s*return|gst/hst|t4\s*slip)', text_lower):
        return ('tax', 0.85)
    
    # Receipts
    if any(x in fname_lower for x in ['receipt', 'invoice', 'fibrenew', 'heffner']):
        return ('receipts', 0.90)
    if re.search(r'(invoice\s*#|receipt|total\s*amount|gst|subtotal)', text_lower):
        return ('receipts', 0.75)
    
    # Insurance documents
    if any(x in fname_lower for x in ['insurance', 'policy', 'coverage', 'aviva']):
        return ('insurance', 0.90)
    if re.search(r'(policy\s*number|insurance|premium|coverage)', text_lower):
        return ('insurance', 0.75)
    
    return ('uncategorized', 0.5)

def compute_file_hash(filepath):
    """SHA-256 hash of file contents for deduplication."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def extract_text_from_pdf(pdf_path):
    """
    Extract text from PDF. Try multiple methods:
    1. PyPDF2 (if searchable PDF from PDF24)
    2. Plain text file with same name
    3. Return raw filename if extraction fails
    """
    text = ""
    
    # Try .txt file first (PDF24 often outputs separate text)
    txt_path = pdf_path.with_suffix('.txt')
    if txt_path.exists():
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
            return text
    
    # Try PyPDF2 on searchable PDF
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        if text.strip():
            return text
    except Exception as e:
        print(f"PyPDF2 extraction failed for {pdf_path}: {e}")
    
    # Fallback: return filename as minimal context
    return f"Filename: {pdf_path.name}"

def process_ocr_file(filepath, conn, dry_run=True):
    """
    Process a single OCR'd file:
    1. Extract text
    2. Correct OCR errors
    3. Classify document
    4. Stage into database
    
    Returns: (doc_type, confidence, text_preview)
    """
    filepath = Path(filepath)
    
    # Compute hash for deduplication
    file_hash = compute_file_hash(filepath)
    
    # Check if already processed
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ocr_documents_staging WHERE file_hash = %s", (file_hash,))
    if cur.fetchone()[0] > 0:
        cur.close()
        return ('duplicate', 1.0, 'Already processed')
    
    # Extract text
    if filepath.suffix.lower() == '.pdf':
        raw_text = extract_text_from_pdf(filepath)
    elif filepath.suffix.lower() == '.txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            raw_text = f.read()
    else:
        cur.close()
        return ('unsupported', 0.0, f'Unsupported file type: {filepath.suffix}')
    
    # Correct OCR errors
    corrected_text = correct_ocr_text(raw_text)
    
    # Classify document
    doc_type, confidence = classify_document(filepath.name, corrected_text)
    
    # Preview (first 500 chars)
    preview = corrected_text[:500]
    
    if not dry_run:
        # Insert into staging table
        cur.execute("""
            INSERT INTO ocr_documents_staging 
            (source_file, file_hash, doc_type, confidence, raw_text, corrected_text, 
             file_size, processed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            str(filepath),
            file_hash,
            doc_type,
            confidence,
            raw_text,
            corrected_text,
            filepath.stat().st_size
        ))
        conn.commit()
    
    cur.close()
    return (doc_type, confidence, preview)

def scan_and_process_directory(directory, conn, dry_run=True, extensions=None):
    """
    Recursively scan directory for OCR output files and process them.
    
    Args:
        directory: Path to scan
        conn: Database connection
        dry_run: If True, don't insert into database
        extensions: List of file extensions to process (default: ['.pdf', '.txt'])
    """
    if extensions is None:
        extensions = ['.pdf', '.txt']
    
    directory = Path(directory)
    stats = {
        'payroll': 0,
        'quickbooks': 0,
        'banking': 0,
        'tax': 0,
        'receipts': 0,
        'insurance': 0,
        'uncategorized': 0,
        'duplicate': 0,
        'unsupported': 0
    }
    
    print(f"\n{'='*80}")
    print(f"Scanning {directory} for OCR output...")
    print(f"Dry run: {dry_run}")
    print(f"{'='*80}\n")
    
    files_processed = 0
    for ext in extensions:
        for filepath in directory.rglob(f'*{ext}'):
            # Skip already categorized files (in ocr_output subdirs)
            if 'ocr_output' in str(filepath) and filepath.parent.name != 'ocr_output':
                continue
            
            try:
                doc_type, confidence, preview = process_ocr_file(filepath, conn, dry_run)
                stats[doc_type] += 1
                files_processed += 1
                
                if doc_type != 'duplicate':
                    print(f"\n[{files_processed}] {filepath.name}")
                    print(f"  Type: {doc_type} (confidence: {confidence:.2f})")
                    print(f"  Preview: {preview[:200]}...")
                
                # Move to appropriate category folder (only if not dry run and high confidence)
                if not dry_run and confidence >= 0.80 and doc_type != 'duplicate':
                    target_dir = Path('l:/limo/ocr_output') / doc_type
                    target_path = target_dir / filepath.name
                    
                    # Avoid name collisions
                    counter = 1
                    while target_path.exists():
                        target_path = target_dir / f"{filepath.stem}_{counter}{filepath.suffix}"
                        counter += 1
                    
                    # Copy (don't move - keep originals)
                    import shutil
                    shutil.copy2(filepath, target_path)
                    print(f"  → Copied to {target_path}")
                
            except Exception as e:
                print(f"ERROR processing {filepath}: {e}")
                stats['unsupported'] += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(f"Processing complete - {files_processed} files scanned")
    print(f"{'='*80}")
    for doc_type, count in sorted(stats.items()):
        if count > 0:
            print(f"  {doc_type:15s}: {count:5d} files")
    print()
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Process OCR output from PDF24')
    parser.add_argument('--directory', '-d', default='l:/limo',
                        help='Directory to scan for OCR files (default: l:/limo)')
    parser.add_argument('--write', action='store_true',
                        help='Actually write to database (default is dry-run)')
    parser.add_argument('--extensions', nargs='+', default=['.pdf', '.txt'],
                        help='File extensions to process (default: .pdf .txt)')
    
    args = parser.parse_args()
    
    conn = get_db_connection()
    
    try:
        stats = scan_and_process_directory(
            args.directory, 
            conn, 
            dry_run=not args.write,
            extensions=args.extensions
        )
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
