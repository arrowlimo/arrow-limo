"""
Comprehensive payroll document scanner for 2012-2016
Catalogs all T4s, ROEs, pay cheques, deduction reports, payroll summaries
Identifies duplicates, missing documents, and data quality issues
"""
import os
import hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json

# Document type patterns
DOCUMENT_PATTERNS = {
    'T4': ['t4', 'T4'],
    'T4_SUMMARY': ['t4 summary', 't4summary', 'T4 Summary'],
    'ROE': ['roe', 'ROE', 'PDOC', 'record of employment'],
    'PAY_CHEQUE': ['pay cheque', 'paycheque', 'pay check', 'paycheck'],
    'PD7A': ['pd7a', 'PD7A', 'pdta', 'PDTA'],  # Statement of Account for CPP/EI
    'PAYROLL_SUMMARY': ['payroll summary', 'driver pay summary'],
    'REMITTANCE': ['remittance', 'payroll remittance'],
    'VACATION_PAY': ['vacation pay', 'vacation payout'],
    'WCB': ['wcb', 'WCB', 'workers comp'],
}

def get_file_hash(filepath):
    """Get SHA256 hash of file"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except:
        return None

def categorize_document(filename):
    """Categorize document by filename patterns"""
    filename_lower = filename.lower()
    
    categories = []
    for doc_type, patterns in DOCUMENT_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in filename_lower:
                categories.append(doc_type)
                break
    
    return categories if categories else ['UNKNOWN']

def extract_year_from_path(filepath):
    """Extract year from file path or filename"""
    path_str = str(filepath)
    
    # Check path components
    for part in Path(filepath).parts:
        if part.isdigit() and len(part) == 4 and 2012 <= int(part) <= 2016:
            return int(part)
    
    # Check filename
    filename = Path(filepath).name
    import re
    year_match = re.search(r'\b(201[2-6])\b', filename)
    if year_match:
        return int(year_match.group(1))
    
    return None

def scan_payroll_documents(base_path, years):
    """Scan for all payroll documents"""
    base = Path(base_path)
    
    all_documents = []
    hash_groups = defaultdict(list)
    
    print(f'Scanning: {base_path}')
    print(f'Years: {years}')
    print()
    
    for year in years:
        year_path = base / str(year)
        if not year_path.exists():
            print(f'⚠️  Year {year} folder not found: {year_path}')
            continue
        
        print(f'📁 Scanning {year}...')
        
        # Recursively find all PDFs
        pdf_files = list(year_path.rglob('*.pdf'))
        
        print(f'   Found {len(pdf_files)} PDF files')
        
        for pdf_file in pdf_files:
            if not pdf_file.is_file():
                continue
            
            file_info = {
                'path': str(pdf_file),
                'relative_path': str(pdf_file.relative_to(base)),
                'filename': pdf_file.name,
                'year': extract_year_from_path(pdf_file) or year,
                'size': pdf_file.stat().st_size,
                'modified': datetime.fromtimestamp(pdf_file.stat().st_mtime).isoformat(),
                'hash': get_file_hash(pdf_file),
                'categories': categorize_document(pdf_file.name),
            }
            
            all_documents.append(file_info)
            
            if file_info['hash']:
                hash_groups[file_info['hash']].append(file_info)
    
    return all_documents, hash_groups

def analyze_documents(documents, hash_groups):
    """Analyze document collection"""
    print('\n' + '=' * 80)
    print('DOCUMENT ANALYSIS')
    print('=' * 80)
    
    # Group by year and category
    by_year_category = defaultdict(lambda: defaultdict(list))
    
    for doc in documents:
        year = doc['year']
        for category in doc['categories']:
            by_year_category[year][category].append(doc)
    
    # Print summary
    for year in sorted(by_year_category.keys()):
        print(f'\n📅 YEAR {year}')
        print('-' * 80)
        
        categories = by_year_category[year]
        total_files = sum(len(files) for files in categories.values())
        total_size = sum(doc['size'] for cat_files in categories.values() for doc in cat_files)
        
        print(f'Total files: {total_files}')
        print(f'Total size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)')
        print()
        
        for category in sorted(categories.keys()):
            files = categories[category]
            cat_size = sum(f['size'] for f in files)
            print(f'  {category:20s}: {len(files):3d} files ({cat_size:,} bytes)')
    
    # Find duplicates
    print('\n' + '=' * 80)
    print('DUPLICATE ANALYSIS')
    print('=' * 80)
    
    duplicates = {h: files for h, files in hash_groups.items() if len(files) > 1}
    
    if duplicates:
        print(f'\nFound {len(duplicates)} sets of duplicate files:')
        
        for file_hash, dup_files in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
            if len(dup_files) > 1:
                print(f'\n{len(dup_files)} identical copies ({dup_files[0]["size"]:,} bytes):')
                for f in dup_files:
                    print(f'  - {f["relative_path"]}')
        
        total_dup_size = sum(
            (len(files) - 1) * files[0]['size']
            for files in duplicates.values()
        )
        print(f'\nTotal duplicate storage waste: {total_dup_size:,} bytes ({total_dup_size/1024/1024:.1f} MB)')
    else:
        print('\n✅ No exact duplicates found')
    
    return by_year_category

def identify_missing_documents(by_year_category, years):
    """Identify missing or incomplete payroll documents"""
    print('\n' + '=' * 80)
    print('MISSING DOCUMENTS ANALYSIS')
    print('=' * 80)
    
    issues = []
    
    for year in years:
        print(f'\n📅 YEAR {year}')
        print('-' * 80)
        
        categories = by_year_category.get(year, {})
        
        # Check for required documents
        required_docs = {
            'T4': 'Employee T4 slips',
            'T4_SUMMARY': 'T4 Summary for CRA',
            'PD7A': 'CPP/EI remittance statements',
            'PAYROLL_SUMMARY': 'Monthly payroll summaries',
        }
        
        for doc_type, description in required_docs.items():
            if doc_type not in categories or len(categories[doc_type]) == 0:
                issue = f'{year}: MISSING {doc_type} - {description}'
                issues.append(issue)
                print(f'  ❌ {issue}')
            else:
                count = len(categories[doc_type])
                print(f'  ✅ {doc_type}: {count} files found')
        
        # Check for ROEs (seasonal business should have some)
        if 'ROE' not in categories or len(categories['ROE']) == 0:
            print(f'  ⚠️  No ROEs found (expected for seasonal layoffs)')
        else:
            print(f'  ✅ ROE: {len(categories["ROE"])} files found')
    
    return issues

def generate_recommendations(documents, by_year_category, issues):
    """Generate action items and recommendations"""
    print('\n' + '=' * 80)
    print('RECOMMENDATIONS & ACTION ITEMS')
    print('=' * 80)
    
    recommendations = []
    
    # Priority 1: Missing critical documents
    if issues:
        print('\n🔴 PRIORITY 1: Critical Missing Documents')
        for issue in issues:
            print(f'  - {issue}')
            recommendations.append({
                'priority': 1,
                'type': 'MISSING_DOCUMENT',
                'description': issue,
                'action': 'Locate and scan missing document, or confirm not applicable'
            })
    
    # Priority 2: Data extraction needed
    print('\n🟡 PRIORITY 2: Data Extraction Required')
    for year in sorted(by_year_category.keys()):
        categories = by_year_category[year]
        
        if 'T4' in categories:
            t4_count = len(categories['T4'])
            print(f'  - Extract data from {t4_count} T4 documents ({year}) into employee_t4_records')
            recommendations.append({
                'priority': 2,
                'type': 'DATA_EXTRACTION',
                'year': year,
                'document_type': 'T4',
                'count': t4_count,
                'action': f'Parse {t4_count} T4 PDFs and populate employee_t4_records table'
            })
        
        if 'ROE' in categories:
            roe_count = len(categories['ROE'])
            print(f'  - Extract data from {roe_count} ROE documents ({year}) into employee_roe_records')
            recommendations.append({
                'priority': 2,
                'type': 'DATA_EXTRACTION',
                'year': year,
                'document_type': 'ROE',
                'count': roe_count,
                'action': f'Parse {roe_count} ROE PDFs and populate employee_roe_records table'
            })
        
        if 'PAYROLL_SUMMARY' in categories:
            summary_count = len(categories['PAYROLL_SUMMARY'])
            print(f'  - Extract payroll data from {summary_count} summaries ({year}) into employee_pay_entries')
            recommendations.append({
                'priority': 2,
                'type': 'DATA_EXTRACTION',
                'year': year,
                'document_type': 'PAYROLL_SUMMARY',
                'count': summary_count,
                'action': f'Parse {summary_count} payroll summaries and populate pay records'
            })
    
    # Priority 3: Reconciliation needed
    print('\n🟢 PRIORITY 3: Data Reconciliation')
    print('  - Cross-verify T4 employment income vs sum of payroll entries')
    print('  - Verify CPP/EI deductions match PD7A remittance statements')
    print('  - Confirm ROE insurable earnings match T4 Box 24')
    print('  - Validate monthly payroll summaries sum to annual totals')
    
    recommendations.extend([
        {
            'priority': 3,
            'type': 'RECONCILIATION',
            'action': 'Cross-verify T4 totals against payroll entries for each employee'
        },
        {
            'priority': 3,
            'type': 'RECONCILIATION',
            'action': 'Verify deductions (CPP/EI/Tax) match remittance statements'
        },
        {
            'priority': 3,
            'type': 'RECONCILIATION',
            'action': 'Reconcile ROE earnings with T4 insurable earnings'
        },
    ])
    
    return recommendations

def main():
    base_path = r'L:\limo\pdf'
    years = [2012, 2013, 2014, 2015, 2016]
    
    print('=' * 80)
    print('COMPREHENSIVE PAYROLL DOCUMENT SCANNER (2012-2016)')
    print('=' * 80)
    print()
    
    # Scan documents
    documents, hash_groups = scan_payroll_documents(base_path, years)
    
    print(f'\n✅ Scanned {len(documents)} total documents')
    
    # Analyze
    by_year_category = analyze_documents(documents, hash_groups)
    
    # Identify missing
    issues = identify_missing_documents(by_year_category, years)
    
    # Generate recommendations
    recommendations = generate_recommendations(documents, by_year_category, issues)
    
    # Save results
    output = {
        'scan_date': datetime.now().isoformat(),
        'years_scanned': years,
        'total_documents': len(documents),
        'documents': documents,
        'duplicates': {h: [f['relative_path'] for f in files] 
                      for h, files in hash_groups.items() if len(files) > 1},
        'issues': issues,
        'recommendations': recommendations,
    }
    
    output_file = Path(r'L:\limo\reports\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f'\n✅ Full inventory saved to: {output_file}')
    
    # Generate markdown summary
    summary_file = Path(r'L:\limo\reports\PAYROLL_RECONCILIATION_TODO_LIST.md')
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write('# Payroll Reconciliation TODO List (2012-2016)\n\n')
        f.write(f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write(f'**Documents Scanned:** {len(documents)} files across 5 years\n\n')
        
        f.write('## Priority 1: Critical Missing Documents\n\n')
        priority1 = [r for r in recommendations if r['priority'] == 1]
        if priority1:
            for r in priority1:
                f.write(f'- [ ] {r["description"]}\n')
                f.write(f'      Action: {r["action"]}\n\n')
        else:
            f.write('✅ No critical documents missing\n\n')
        
        f.write('## Priority 2: Data Extraction Required\n\n')
        priority2 = [r for r in recommendations if r['priority'] == 2]
        for r in priority2:
            f.write(f'- [ ] **{r["year"]} {r["document_type"]}**: {r["action"]}\n')
        
        f.write('\n## Priority 3: Data Reconciliation\n\n')
        priority3 = [r for r in recommendations if r['priority'] == 3]
        for r in priority3:
            f.write(f'- [ ] {r["action"]}\n')
        
        f.write('\n## Document Inventory Summary\n\n')
        for year in sorted(by_year_category.keys()):
            f.write(f'### {year}\n\n')
            categories = by_year_category[year]
            for cat in sorted(categories.keys()):
                f.write(f'- **{cat}**: {len(categories[cat])} files\n')
            f.write('\n')
    
    print(f'✅ TODO list saved to: {summary_file}')
    print()
    print('=' * 80)
    print('SCAN COMPLETE')
    print('=' * 80)

if __name__ == '__main__':
    main()
