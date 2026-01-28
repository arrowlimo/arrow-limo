"""
Analyze 2012 payroll PDF files for duplicates
"""
import os
import hashlib
from pathlib import Path
from collections import defaultdict

files = [
    r'L:\limo\pdf\2012\pay\pdfOctober 2012 Payroll Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfOctober 2012 - Payroll Summary_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfNovember 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfNovember 2012 PDA Report_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfNovember 2012 PDA Report_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\pdfNovember 2012 Pay Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfNovember 2012 - Payroll Summary_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfMichael Richard  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfjune2012driverpaysummary_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfjune2012driverpaysummary_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\pdfJul.2012 PD7A_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfJul.2012 PD7A_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfJesse Gordon  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfJeannie Shillington  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfDoug Redmond  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pdfDecember 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\pdfDecember 2012 PDTA Report_ocred (1).pdf',
    r'L:\limo\pdf\2012\pdfDecember 2012 PDTA Report - Total_ocred.pdf',
    r'L:\limo\pdf\2012\pdfDecember 2012 Pay Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\pdfDecember 2012 Pay Cheques_ocred (1).pdf',
    r'L:\limo\pdf\2012\pdfDec.2012 PDTA Report - Accrued Vacation Payout_ocred.pdf',
    r'L:\limo\pdf\2012\pdfDec.2012 Accrued Vacation Pay Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\pdfdec 2012_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfDale Menard  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfChantal Thomas  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pdfAugust 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\pdfAugust 2012 PDTA Report_ocred (1).pdf',
    r'L:\limo\pdf\2012\pdfAugust 2012 - Payroll Summary_ocred.pdf',
    r'L:\limo\pdf\2012\pdfAugust 2012 - Payroll Summary_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfAngel Escobar  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pdf2012 CRA Copy of T4\'s_ocred.pdf',
    r'L:\limo\pdf\2012\pdf2012 - 31 T4\'s - Employer Copy_ocred.pdf',
    r'L:\limo\pdf\2012\Doug Redmond-ROE_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Jeannie Shillington  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\Jul.2012 PD7A_ocred (1).pdf',
    r'L:\limo\pdf\2012\August 2012 PDTA Report_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Doug Redmond  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Dale Menard  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Paul Mansell  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\August 2012 - Payroll Summary_ocred (1).pdf',
    r'L:\limo\pdf\2012\Arrow 2014 T4 Summary_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Angel Escobar  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\2012 YTD Hourly Payroll Remittance_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Chantal Thomas  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\December 2012 PDTA Report_ocred (1).pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Michael Richard  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\Jesse Gordon  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\November 2012 PDA Report_ocred (1).pdf',
    r'L:\limo\pdf\2012\Feb 2012 Heather Gullison Paid Invoice_ocred.pdf',
    r'L:\limo\pdf\2012\Doug Redmond-ROE_ocred.pdf',
    r'L:\limo\pdf\2012\Dec.2012 PDTA Report - Accrued Vacation Payout_ocred.pdf',
    r'L:\limo\pdf\2012\August 2012 - Payroll Summary_ocred.pdf',
    r'L:\limo\pdf\2012\August 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\pay\2012 - 31 T4\'s - Employer Copy_ocred.pdf',
    r'L:\limo\pdf\2012\pay\2012 CRA Copy of T4\'s_ocred.pdf',
    r'L:\limo\pdf\2012\November 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\November 2012 PDA Report_ocred.pdf',
    r'L:\limo\pdf\2012\November 2012 Pay Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\june2012driverpaysummary_ocred.pdf',
    r'L:\limo\pdf\2012\December 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\December 2012 PDTA Report - Total_ocred.pdf',
    r'L:\limo\pdf\2012\December 2012 Pay Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\October 2012 PDTA Report_ocred.pdf',
    r'L:\limo\pdf\2012\October 2012 Payroll Cheques_ocred.pdf',
    r'L:\limo\pdf\2012\October 2012 - Payroll Summary_ocred.pdf',
    r'L:\limo\pdf\2012\Jul.2012 PD7A_ocred.pdf',
    r'L:\limo\pdf\2012\pay\PDOC\pdfPaul Mansell  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf',
    r'L:\limo\pdf\2012\pay\pdfOctober 2012 PDTA Report_ocred.pdf',
]


def get_file_hash(filepath):
    """Get SHA256 hash of file"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).digest()


def normalize_name(path):
    """Normalize filename for comparison"""
    name = Path(path).name
    # Remove pdf prefix
    if name.startswith('pdf'):
        name = name[3:]
    # Remove (1), (2) etc
    name = name.replace(' (1)', '').replace(' (2)', '')
    return name.lower()


def main():
    # Group files by hash and normalized name
    hash_groups = defaultdict(list)
    name_groups = defaultdict(list)

    print('=== SCANNING 69 PAYROLL FILES ===')
    print()

    existing = []
    missing = []

    for f in files:
        if os.path.exists(f):
            existing.append(f)
            file_hash = get_file_hash(f)
            norm_name = normalize_name(f)
            hash_groups[file_hash].append(f)
            name_groups[norm_name].append(f)
        else:
            missing.append(f)

    print(f'Files found: {len(existing)}')
    print(f'Files missing: {len(missing)}')
    if missing:
        print('\nMissing files:')
        for m in missing:
            print(f'  - {m}')
    print()

    # Find true duplicates (same hash)
    print('=== EXACT DUPLICATES (SAME CONTENT) ===')
    duplicates_by_hash = {h: fs for h, fs in hash_groups.items() if len(fs) > 1}
    dup_count = sum(len(fs) - 1 for fs in duplicates_by_hash.values())

    for file_hash, group in sorted(duplicates_by_hash.items(), key=lambda x: len(x[1]), reverse=True):
        print(f'\n{len(group)} identical copies (Hash: {file_hash.hex()[:16]}...):')
        for f in sorted(group):
            size = os.path.getsize(f)
            rel = str(Path(f).relative_to(r'L:\limo\pdf\2012'))
            print(f'  - {rel} ({size:,} bytes)')

    print(f'\n✅ Total exact duplicate files to remove: {dup_count}')
    print()
    
    # Compare files with similar names but different content
    print('=== FILES WITH SIMILAR NAMES (DIFFERENT CONTENT) ===')
    similar_not_dupe = []
    for norm_name, group in sorted(name_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(group) > 1:
            hashes = [get_file_hash(f) for f in group]
            if len(set(hashes)) > 1:  # Different content
                print(f'\n"{norm_name}" - {len(group)} files with DIFFERENT content:')
                for f in sorted(group):
                    size = os.path.getsize(f)
                    rel = str(Path(f).relative_to(r'L:\limo\pdf\2012'))
                    print(f'  - {rel:60s} {size:,} bytes')
                similar_not_dupe.extend(group)
    
    if similar_not_dupe:
        print(f'\n⚠️  {len(set(similar_not_dupe))} files have similar names but DIFFERENT content')
        print('    These may be: different OCR passes, different report versions, or naming errors')
    print()

    # Categorize duplicates
    print('=== DUPLICATION CATEGORIES ===')
    
    roe_dups = []
    payroll_dups = []
    t4_dups = []
    other_dups = []
    
    for file_hash, group in duplicates_by_hash.items():
        if any('PDOC' in f for f in group):
            roe_dups.extend(group[1:])  # Keep first, mark rest for deletion
        elif any('T4' in f for f in group):
            t4_dups.extend(group[1:])
        elif any('Pay' in f or 'PDTA' in f or 'PDA' in f for f in group):
            payroll_dups.extend(group[1:])
        else:
            other_dups.extend(group[1:])
    
    print(f'ROE duplicates (PDOC folder): {len(roe_dups)}')
    print(f'T4 duplicates: {len(t4_dups)}')
    print(f'Payroll report duplicates: {len(payroll_dups)}')
    print(f'Other duplicates: {len(other_dups)}')
    
    # Generate deletion script
    print()
    print('=== DELETION RECOMMENDATIONS ===')
    print()
    print('# Delete files with "pdf" prefix (keep clean names):')
    pdf_prefix = [f for f in roe_dups + payroll_dups + t4_dups + other_dups 
                  if Path(f).name.startswith('pdf')]
    for f in sorted(pdf_prefix):
        print(f'Remove-Item -Path "{f}" -Force')
    
    print()
    print(f'# Delete files with (1) suffix (browser duplicates):')
    numbered = [f for f in roe_dups + payroll_dups + t4_dups + other_dups 
                if ' (1)' in Path(f).name or ' (2)' in Path(f).name]
    for f in sorted(numbered):
        print(f'Remove-Item -Path "{f}" -Force')
    
    # Summary stats
    print()
    print('=== SUMMARY ===')
    print(f'Total files scanned: {len(files)}')
    print(f'Files found: {len(existing)}')
    print(f'Files missing: {len(missing)}')
    print(f'Unique files: {len(hash_groups)}')
    print(f'Duplicate sets: {len(duplicates_by_hash)}')
    print(f'Total duplicates to remove: {dup_count}')
    print(f'Space to reclaim: ~{sum(os.path.getsize(f) for f in roe_dups + payroll_dups + t4_dups + other_dups):,} bytes')


if __name__ == '__main__':
    main()
