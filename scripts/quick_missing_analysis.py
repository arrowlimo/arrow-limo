#!/usr/bin/env python3
"""Quick analysis of missing transactions from PDF analysis."""

import json
from pathlib import Path

# Load analysis results
with open('l:/limo/reports/2012_banking_pdf_analysis.json', 'r') as f:
    data = json.load(f)

print("="*80)
print("SAMPLE MISSING TRANSACTIONS ANALYSIS")
print("="*80)

for result in data['file_results']:
    if result['missing_count'] > 0:
        print(f"\n📄 {result['file']}")
        print(f"   Missing: {result['missing_count']} transactions")
        print(f"   Match Rate: {result['match_rate']:.1f}%")
        print(f"\n   Sample Missing (first 10):")
        
        for txn in result['missing'][:10]:
            print(f"   {txn['date']} | ${txn['amount']:>10,.2f} | {txn['description'][:70]}")

print("\n" + "="*80)
