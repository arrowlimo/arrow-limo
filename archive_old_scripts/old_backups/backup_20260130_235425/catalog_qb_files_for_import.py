"""
Catalog all QuickBooks export files to identify importable data by year and type.
Scans Excel, CSV, IIF files and categorizes by content (banking, receipts, GL, etc.)
"""
import os
import csv
import re
from collections import defaultdict
from datetime import datetime


def scan_directory_for_exports(base_dirs):
    """Scan multiple directories for QuickBooks export files."""
    files_by_type = defaultdict(list)
    
    for base_dir in base_dirs:
        if not os.path.exists(base_dir):
            print(f"[WARN]  Directory not found: {base_dir}")
            continue
        
        print(f"Scanning {base_dir}...")
        
        for root, dirs, files in os.walk(base_dir):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                
                if ext not in ['.xlsx', '.csv', '.iif', '.txt', '.xls', '.xlsm']:
                    continue
                
                path = os.path.join(root, fn)
                file_info = {
                    'path': path,
                    'filename': fn,
                    'ext': ext,
                    'size': os.path.getsize(path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(path)),
                }
                
                # Categorize by filename patterns
                fn_lower = fn.lower()
                
                if any(kw in fn_lower for kw in ['bank', 'checking', 'cibc', 'rbc', 'capital', 'transaction', 'statement']):
                    file_info['category'] = 'banking'
                elif any(kw in fn_lower for kw in ['receipt', 'expense', 'vendor']):
                    file_info['category'] = 'receipts'
                elif any(kw in fn_lower for kw in ['journal', 'general_ledger', 'gl', 'ledger']):
                    file_info['category'] = 'general_ledger'
                elif any(kw in fn_lower for kw in ['invoice', 'ar', 'sales']):
                    file_info['category'] = 'invoices'
                elif any(kw in fn_lower for kw in ['payment', 'deposit']):
                    file_info['category'] = 'payments'
                elif any(kw in fn_lower for kw in ['customer', 'client']):
                    file_info['category'] = 'customers'
                elif any(kw in fn_lower for kw in ['employee', 'payroll']):
                    file_info['category'] = 'employees'
                elif any(kw in fn_lower for kw in ['vehicle', 'asset']):
                    file_info['category'] = 'vehicles'
                elif any(kw in fn_lower for kw in ['chart', 'account']):
                    file_info['category'] = 'chart_of_accounts'
                else:
                    file_info['category'] = 'unknown'
                
                # Extract years from filename
                years = set()
                for m in re.finditer(r'\b(20\d{2}|19\d{2})\b', fn):
                    y = int(m.group(1))
                    if 2000 <= y <= 2030:
                        years.add(y)
                file_info['years'] = sorted(list(years))
                
                files_by_type[file_info['category']].append(file_info)
    
    return files_by_type


def write_catalog_report(files_by_type, out_path):
    """Write a detailed catalog report."""
    lines = []
    lines.append("# QuickBooks Export Files Catalog")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    total_files = sum(len(files) for files in files_by_type.values())
    lines.append(f"**Total files found**: {total_files}")
    lines.append("")
    
    for category in sorted(files_by_type.keys()):
        files = files_by_type[category]
        lines.append(f"## {category.replace('_', ' ').title()} ({len(files)} files)")
        lines.append("")
        
        if not files:
            continue
        
        # Sort by year, then filename
        files_sorted = sorted(files, key=lambda f: (f.get('years', [9999])[0] if f.get('years') else 9999, f['filename']))
        
        lines.append("File | Years | Size | Modified | Path")
        lines.append("---|---|---:|---|---")
        
        for f in files_sorted:
            years_str = ", ".join(str(y) for y in f['years']) if f['years'] else "-"
            size_kb = f['size'] / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            mod_str = f['modified'].strftime('%Y-%m-%d')
            
            lines.append(f"`{f['filename']}` | {years_str} | {size_str} | {mod_str} | `{f['path']}`")
        
        lines.append("")
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def write_import_priorities(files_by_type, out_path):
    """Write import priority list for missing data."""
    lines = []
    lines.append("# Import Priority List")
    lines.append("")
    lines.append("Based on gap analysis, prioritize these imports:")
    lines.append("")
    
    # Priority 1: Banking 2013-2016
    lines.append("## Priority 1: Banking 2013-2016 ❗")
    lines.append("")
    banking_files = files_by_type.get('banking', [])
    target_years = {2013, 2014, 2015, 2016}
    priority_banking = [f for f in banking_files if any(y in target_years for y in f.get('years', []))]
    
    if priority_banking:
        lines.append("**Files to import:**")
        for f in sorted(priority_banking, key=lambda x: (x.get('years', [9999])[0] if x.get('years') else 9999, x['filename'])):
            years_str = ", ".join(str(y) for y in f['years']) if f['years'] else "unknown"
            lines.append(f"- `{f['filename']}` (years: {years_str}) → `{f['path']}`")
    else:
        lines.append("[WARN] No banking files found for 2013-2016. Check other directories or request exports.")
    lines.append("")
    
    # Priority 2: Receipts 2013, 2015
    lines.append("## Priority 2: Receipts 2013 & 2015")
    lines.append("")
    receipt_files = files_by_type.get('receipts', [])
    target_receipt_years = {2013, 2015}
    priority_receipts = [f for f in receipt_files if any(y in target_receipt_years for y in f.get('years', []))]
    
    if priority_receipts:
        lines.append("**Files to import:**")
        for f in sorted(priority_receipts, key=lambda x: (x.get('years', [9999])[0] if x.get('years') else 9999, x['filename'])):
            years_str = ", ".join(str(y) for y in f['years']) if f['years'] else "unknown"
            lines.append(f"- `{f['filename']}` (years: {years_str}) → `{f['path']}`")
    else:
        lines.append("[WARN] No receipt files found for 2013/2015. May need to extract from banking or create from GL.")
    lines.append("")
    
    # Priority 3: General Ledger (all years)
    lines.append("## Priority 3: General Ledger (All Years)")
    lines.append("")
    gl_files = files_by_type.get('general_ledger', [])
    
    if gl_files:
        lines.append("**Files to import:**")
        for f in sorted(gl_files, key=lambda x: (x.get('years', [9999])[0] if x.get('years') else 9999, x['filename'])):
            years_str = ", ".join(str(y) for y in f['years']) if f['years'] else "all time"
            lines.append(f"- `{f['filename']}` (years: {years_str}) → `{f['path']}`")
    else:
        lines.append("[WARN] No GL files found. Check QuickBooks exports or generate from journal entries.")
    lines.append("")
    
    # Priority 4: Master data (clients, employees, vehicles)
    lines.append("## Priority 4: Master Data Updates")
    lines.append("")
    lines.append("**Customers/Clients:**")
    customer_files = files_by_type.get('customers', [])
    if customer_files:
        lines.append(f"- Found {len(customer_files)} customer files")
        for f in customer_files[:3]:  # Show first 3
            lines.append(f"  - `{f['filename']}`")
    else:
        lines.append("- [WARN] No customer list files found")
    lines.append("")
    
    lines.append("**Employees:**")
    employee_files = files_by_type.get('employees', [])
    if employee_files:
        lines.append(f"- Found {len(employee_files)} employee files")
        for f in employee_files[:3]:
            lines.append(f"  - `{f['filename']}`")
    else:
        lines.append("- [WARN] No employee list files found")
    lines.append("")
    
    lines.append("**Vehicles:**")
    vehicle_files = files_by_type.get('vehicles', [])
    if vehicle_files:
        lines.append(f"- Found {len(vehicle_files)} vehicle files")
        for f in vehicle_files[:3]:
            lines.append(f"  - `{f['filename']}`")
    else:
        lines.append("- [WARN] No vehicle list files found")
    lines.append("")
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def main():
    base_dirs = [
        "L:\\limo\\quickbooks",
        "L:\\limo\\quickbooks_exports",
        "L:\\limo\\qbb",
    ]
    
    print("Cataloging QuickBooks export files...")
    files_by_type = scan_directory_for_exports(base_dirs)
    
    out_dir = "exports/audit"
    
    catalog_path = os.path.join(out_dir, "qb_files_catalog.md")
    write_catalog_report(files_by_type, catalog_path)
    print(f"\n[OK] Catalog report: {catalog_path}")
    
    priority_path = os.path.join(out_dir, "import_priority_list.md")
    write_import_priorities(files_by_type, priority_path)
    print(f"[OK] Import priority list: {priority_path}")
    
    print("\nSummary by category:")
    for cat in sorted(files_by_type.keys()):
        count = len(files_by_type[cat])
        print(f"  {cat}: {count} files")


if __name__ == "__main__":
    main()
