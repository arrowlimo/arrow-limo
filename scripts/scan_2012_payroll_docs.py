#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Scan for 2012 payroll documents to identify what monthly data we have available.
"""
import os
from pathlib import Path

base_paths = [
    r'l:\limo\uploaded_pay',
    r'l:\limo\pdf',
    r'l:\limo\quickbooks',
    r'l:\limo\docs'
]

# Patterns to look for
patterns = {
    'PD7A': ['pd7a', 'PD7A'],
    'PDTA': ['pdta', 'PDTA'],  
    'T4': ['t4', 'T4'],
    'Payroll': ['payroll', 'Payroll'],
    'Remittance': ['remittance', 'Remittance']
}

print("2012 Payroll Document Scan")
print("=" * 80)

for base in base_paths:
    if not os.path.exists(base):
        continue
    
    for root, dirs, files in os.walk(base):
        for f in files:
            if '2012' in f and f.lower().endswith('.pdf'):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, r'l:\limo')
                
                # Categorize
                category = 'Other'
                for cat, keywords in patterns.items():
                    if any(kw in f for kw in keywords):
                        category = cat
                        break
                
                # Skip duplicates folder
                if '.duplicates' in rel_path:
                    continue
                    
                print(f"\n[{category}] {f}")
                print(f"  Path: {rel_path}")

print("\n" + "=" * 80)
print("Recommendation: Extract monthly PD7A/PDTA data for complete 2012 breakdown")
