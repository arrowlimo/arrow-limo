"""
Analyze CRA audit export files from QuickBooks
"""
import zipfile
import os
from pathlib import Path

def analyze_cra_exports():
    qb_dir = Path(r"L:\limo\quickbooks")
    
    # Find all CRA audit export files
    cra_files = sorted(qb_dir.glob("CRAauditexport__*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    print("=" * 140)
    print("CRA AUDIT EXPORT FILES ANALYSIS")
    print("=" * 140)
    
    print(f"\nFound {len(cra_files)} CRA audit export files:")
    for i, file in enumerate(cra_files, 1):
        size_kb = file.stat().st_size / 1024
        mtime = file.stat().st_mtime
        print(f"\n{i}. {file.name}")
        print(f"   Size: {size_kb:.1f} KB")
        print(f"   Modified: {file.stat().st_mtime}")
    
    print("\n" + "=" * 140)
    print("ANALYZING FILE CONTENTS")
    print("=" * 140)
    
    for i, zip_path in enumerate(cra_files, 1):
        print(f"\n{'='*140}")
        print(f"FILE {i}: {zip_path.name}")
        print(f"{'='*140}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                print(f"\nContains {len(file_list)} files:")
                
                for file_name in sorted(file_list):
                    file_info = zip_ref.getinfo(file_name)
                    size = file_info.file_size
                    compressed_size = file_info.compress_size
                    
                    # Determine file type
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in ['.txt', '.csv', '.xml', '.iif']:
                        print(f"\n  📄 {file_name}")
                        print(f"     Size: {size:,} bytes (compressed: {compressed_size:,})")
                        
                        # Read first few lines for preview
                        try:
                            content = zip_ref.read(file_name).decode('utf-8', errors='ignore')
                            lines = content.split('\n')[:10]
                            print(f"     Preview (first 10 lines):")
                            for line in lines:
                                if line.strip():
                                    print(f"       {line[:100]}")
                        except Exception as e:
                            print(f"     Could not read content: {e}")
                    else:
                        print(f"  📦 {file_name} ({size:,} bytes)")
                
        except Exception as e:
            print(f"Error reading {zip_path.name}: {e}")
    
    print("\n" + "=" * 140)
    print("RECOMMENDATIONS FOR CRA AUDIT PREPARATION")
    print("=" * 140)
    print("""
    CRA audit exports typically contain:
    
    1. General Ledger (complete transaction history)
    2. Chart of Accounts (account structure)
    3. Trial Balance (account summaries by period)
    4. Vendor/Customer Lists (name and address information)
    5. Banking transactions
    6. Sales/Purchase summaries
    7. Payroll records
    
    To check if we need additional data from these exports:
    - Compare general ledger in exports vs our database
    - Check for any missing accounts or transactions
    - Verify payroll data completeness
    - Ensure all vendor/supplier information is captured
    - Review GST/HST calculations
    
    Next steps:
    1. Extract all files from the ZIP archives
    2. Compare against existing database data
    3. Identify any missing information
    4. Import any additional required data
    """)

if __name__ == "__main__":
    analyze_cra_exports()
