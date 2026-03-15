"""
2013 Document Processing Master Script
Comprehensive analysis of all 2013 PDF documents with categorization,
OCR extraction, validation, and staging for import.

Similar to 2012 processing but with enhanced validation and manual verification points.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Document categories and patterns
DOCUMENT_CATEGORIES = {
    'banking': [
        r'cibc.*statement',
        r'bank.*statement',
        r'checking.*account',
        r'saving.*account'
    ],
    'payroll_stubs': [
        r'payroll.*cheque.*stub',
        r'payroll.*stub',
        r'cheque.*stub'
    ],
    'payroll_reports': [
        r'pd[7t]a.*report',
        r'pda.*report',
        r'payroll.*summary'
    ],
    't4_slips': [
        r't4.*slip',
        r't4.*employee'
    ],
    't4_summary': [
        r't4.*summary',
        r'year.*end.*total'
    ],
    'roe': [
        r'roe',
        r'record.*employment'
    ],
    'vacation': [
        r'vacation.*payout'
    ],
    'cra_filing': [
        r'cra.*efiled',
        r'efiled.*confirmation'
    ],
    'other': []
}

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}

def catalog_2013_documents():
    """Scan and categorize all 2013 PDF documents."""
    
    pdf_dir = Path(r"L:\limo\pdf\2013")
    
    if not pdf_dir.exists():
        print(f"Error: Directory {pdf_dir} not found")
        return None
    
    catalog = {
        'scan_date': datetime.now().isoformat(),
        'year': 2013,
        'total_files': 0,
        'by_category': defaultdict(list),
        'by_month': defaultdict(list),
        'duplicates_detected': [],
        'files': []
    }
    
    print("="*80)
    print("2013 DOCUMENT CATALOGING")
    print("="*80)
    print(f"\nScanning directory: {pdf_dir}\n")
    
    # Get all PDF files
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    catalog['total_files'] = len(pdf_files)
    
    print(f"Found {len(pdf_files)} PDF files\n")
    
    # Track for duplicate detection
    base_names = defaultdict(list)
    
    for pdf_file in pdf_files:
        file_info = {
            'filename': pdf_file.name,
            'filepath': str(pdf_file),
            'size_bytes': pdf_file.stat().st_size,
            'size_mb': round(pdf_file.stat().st_size / (1024*1024), 2),
            'modified': pdf_file.stat().st_mtime,
            'category': 'other',
            'month': None,
            'is_duplicate': False,
            'ocr_ready': '_ocred' in pdf_file.name.lower()
        }
        
        # Normalize filename for analysis
        normalized = pdf_file.name.lower()
        
        # Detect month
        for month_name, month_num in MONTHS.items():
            if month_name in normalized:
                file_info['month'] = month_num
                file_info['month_name'] = month_name.capitalize()
                catalog['by_month'][month_num].append(pdf_file.name)
                break
        
        # Detect category
        for category, patterns in DOCUMENT_CATEGORIES.items():
            if category == 'other':
                continue
            for pattern in patterns:
                if re.search(pattern, normalized):
                    file_info['category'] = category
                    catalog['by_category'][category].append(pdf_file.name)
                    break
            if file_info['category'] != 'other':
                break
        
        if file_info['category'] == 'other':
            catalog['by_category']['other'].append(pdf_file.name)
        
        # Detect duplicates (files with " (1)" suffix)
        if ' (1)' in pdf_file.name:
            base_name = pdf_file.name.replace(' (1)', '')
            base_names[base_name].append(pdf_file.name)
            file_info['is_duplicate'] = True
            file_info['base_name'] = base_name
        else:
            base_names[pdf_file.name].append(pdf_file.name)
        
        catalog['files'].append(file_info)
    
    # Identify duplicate groups
    for base_name, files in base_names.items():
        if len(files) > 1:
            catalog['duplicates_detected'].append({
                'base_name': base_name,
                'count': len(files),
                'files': files
            })
    
    # Print summary
    print(f"DOCUMENT SUMMARY:")
    print("-" * 60)
    print(f"Total files: {catalog['total_files']}")
    print(f"OCR-ready files: {sum(1 for f in catalog['files'] if f['ocr_ready'])}")
    print(f"Duplicate groups detected: {len(catalog['duplicates_detected'])}")
    
    print(f"\nBY CATEGORY:")
    print("-" * 60)
    for category in sorted(catalog['by_category'].keys()):
        count = len(catalog['by_category'][category])
        print(f"  {category:20s}: {count:3d} files")
    
    print(f"\nBY MONTH:")
    print("-" * 60)
    for month_num in sorted(catalog['by_month'].keys()):
        count = len(catalog['by_month'][month_num])
        month_name = next(k.capitalize() for k, v in MONTHS.items() if v == month_num)
        print(f"  {month_name:15s}: {count:3d} files")
    
    if catalog['duplicates_detected']:
        print(f"\nDUPLICATE GROUPS:")
        print("-" * 60)
        for dup in catalog['duplicates_detected'][:10]:
            print(f"  {dup['base_name']}")
            for f in dup['files']:
                print(f"    - {f}")
    
    return catalog

def identify_priority_documents(catalog):
    """Identify which documents to process first for maximum value."""
    
    priority = {
        'critical': [],  # Banking statements, T4 Summary, Year-end PD7A
        'high': [],      # Monthly payroll reports, T4 slips
        'medium': [],    # Payroll stubs
        'low': []        # ROEs, duplicates
    }
    
    for file_info in catalog['files']:
        filename = file_info['filename'].lower()
        category = file_info['category']
        
        # Critical priority
        if 'year end' in filename or 't4 summary' in filename:
            priority['critical'].append(file_info)
        elif category == 'banking':
            priority['critical'].append(file_info)
        
        # High priority
        elif category == 't4_slips' and not file_info['is_duplicate']:
            priority['high'].append(file_info)
        elif category == 'payroll_reports' and not file_info['is_duplicate']:
            priority['high'].append(file_info)
        
        # Medium priority
        elif category == 'payroll_stubs' and not file_info['is_duplicate']:
            priority['medium'].append(file_info)
        
        # Low priority
        else:
            priority['low'].append(file_info)
    
    print(f"\n{'='*80}")
    print("PRIORITY ASSESSMENT")
    print("="*80)
    print(f"\nCRITICAL (process first): {len(priority['critical'])} files")
    for f in priority['critical']:
        print(f"  - {f['filename']}")
    
    print(f"\nHIGH (process second): {len(priority['high'])} files")
    for f in priority['high'][:10]:
        print(f"  - {f['filename']}")
    if len(priority['high']) > 10:
        print(f"  ... and {len(priority['high']) - 10} more")
    
    print(f"\nMEDIUM (process third): {len(priority['medium'])} files")
    print(f"LOW (process last): {len(priority['low'])} files")
    
    return priority

def save_catalog(catalog, output_file):
    """Save catalog to JSON file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Catalog saved to: {output_path}")
    print(f"   Size: {output_path.stat().st_size:,} bytes")

def main():
    """Main execution."""
    print("Starting 2013 document processing...")
    print("This will scan all PDFs and create a processing plan.\n")
    
    # Step 1: Catalog all documents
    catalog = catalog_2013_documents()
    
    if not catalog:
        return 1
    
    # Step 2: Prioritize documents
    priority = identify_priority_documents(catalog)
    catalog['priority'] = {k: [f['filename'] for f in v] for k, v in priority.items()}
    
    # Step 3: Save catalog
    output_file = r"L:\limo\data\2013_document_catalog.json"
    save_catalog(catalog, output_file)
    
    print(f"\n{'='*80}")
    print("NEXT STEPS")
    print("="*80)
    print("""
1. MANUAL REVIEW: Check catalog JSON for any miscategorized files
2. BANKING EXTRACTION: Process critical banking statements first
3. PAYROLL EXTRACTION: Extract PD7A and T4 data
4. VALIDATION: Cross-reference T4 vs PD7A totals
5. STAGING: Generate import JSON with duplicate detection
6. IMPORT: Load verified data into almsdata

Use slowest/most accurate OCR for critical documents.
Request manual verification/screenshots for any ambiguous values.
""")
    
    return 0

if __name__ == '__main__':
    exit(main())
