#!/usr/bin/env python3
"""
Master plan for TRUE data recovery - focus on 2013-2016 gaps.

Based on database analysis showing 2012 is complete but 2013-2016 have massive gaps.
"""

import os
import sys
from pathlib import Path

def create_master_recovery_plan():
    """Create master plan for true data gaps."""
    
    print("MASTER RECOVERY PLAN - TRUE DATA GAPS (2013-2016)")
    print("=" * 70)
    
    # Database gap analysis
    gaps = {
        2013: {"existing": 55, "amount": 270653, "missing_estimate": 1445, "value_estimate": 230000},
        2014: {"existing": 2, "amount": 168194, "missing_estimate": 1498, "value_estimate": 500000}, 
        2015: {"existing": 0, "amount": 0, "missing_estimate": 1500, "value_estimate": 750000},
        2016: {"existing": 2, "amount": 70, "missing_estimate": 1498, "value_estimate": 600000}
    }
    
    print("📊 DATABASE GAP ANALYSIS:")
    print("-" * 50)
    print(f"{'Year':<6} {'Exist':<8} {'Amount':<12} {'Missing':<10} {'Potential'}")
    print("-" * 50)
    
    total_potential = 0
    for year, data in gaps.items():
        potential = data['value_estimate']
        total_potential += potential
        print(f"{year:<6} {data['existing']:<8} ${data['amount']:<11,.0f} {data['missing_estimate']:<10} ${potential:,.0f}")
    
    print("-" * 50)
    print(f"{'TOTAL':<6} {'':<8} {'':<12} {'':<10} ${total_potential:,.0f}")
    
    # Excel files in priority order
    excel_dir = Path("L:/limo/docs/2012-2013 excel")
    
    priority_files = [
        # Already processed
        {"file": "2014 Leasing Summary.xlsx", "year": 2014, "status": "[OK] COMPLETED", "value": 168023, "priority": "DONE"},
        
        # CRITICAL - Missing year data
        {"file": "chargesummary2013.xls", "year": 2013, "status": "🎯 HIGH PRIORITY", "value": 150000, "priority": "CRITICAL"},
        {"file": "chargesummary2015.xls", "year": 2015, "status": "🎯 HIGH PRIORITY", "value": 300000, "priority": "CRITICAL"},
        {"file": "chargesummary2016.xls", "year": 2016, "status": "🎯 HIGH PRIORITY", "value": 250000, "priority": "CRITICAL"},
        
        # HIGH VALUE - Specific data types
        {"file": "2013 Revenue & Receipts queries.xlsx", "year": 2013, "status": "📋 PROCESS NEXT", "value": 100000, "priority": "HIGH"},
        {"file": "Arrow 2013 JE.xlsx", "year": 2013, "status": "📋 PROCESS NEXT", "value": 75000, "priority": "HIGH"},
        {"file": "Data Entry Sheet November 2013.xls", "year": 2013, "status": "📋 ANALYZE", "value": 50000, "priority": "MEDIUM"},
        
        # Additional opportunities
        {"file": "Gratuities - 2013.xlsx", "year": 2013, "status": "📋 REVIEW", "value": 25000, "priority": "MEDIUM"},
        {"file": "driverpaymay2014.xls", "year": 2014, "status": "📋 REVIEW", "value": 15000, "priority": "LOW"},
    ]
    
    print(f"\n🎯 PRIORITY FILE PROCESSING PLAN:")
    print("-" * 70)
    print(f"{'Priority':<10} {'File':<35} {'Year':<6} {'Value':<12} {'Status'}")
    print("-" * 70)
    
    for file_info in priority_files:
        file_path = excel_dir / file_info['file']
        exists = "✓" if file_path.exists() else "✗"
        
        print(f"{file_info['priority']:<10} {file_info['file'][:35]:<35} {file_info['year']:<6} ${file_info['value']:<11,.0f} {file_info['status']} {exists}")
    
    # Create execution timeline
    print(f"\n⏰ EXECUTION TIMELINE:")
    print("-" * 40)
    
    print("🚀 PHASE 1 (This week): Critical missing years")
    critical_files = [f for f in priority_files if f['priority'] == 'CRITICAL']
    for file_info in critical_files:
        print(f"   - {file_info['file']} (${file_info['value']:,.0f} potential)")
    
    print(f"\n📈 PHASE 2 (Next week): High-value specific data")  
    high_files = [f for f in priority_files if f['priority'] == 'HIGH']
    for file_info in high_files:
        print(f"   - {file_info['file']} (${file_info['value']:,.0f} potential)")
    
    print(f"\n🔍 PHASE 3 (Later): Medium-value and specialized files")
    medium_files = [f for f in priority_files if f['priority'] in ['MEDIUM', 'LOW']]
    for file_info in medium_files:
        print(f"   - {file_info['file']} (${file_info['value']:,.0f} potential)")
    
    # Success metrics
    print(f"\n📊 SUCCESS METRICS:")
    print("-" * 40)
    
    phase1_value = sum(f['value'] for f in critical_files)
    phase2_value = sum(f['value'] for f in high_files)
    phase3_value = sum(f['value'] for f in medium_files)
    
    print(f"Phase 1 target: ${phase1_value:,.0f} (Fill 2015-2016 gaps)")
    print(f"Phase 2 target: ${phase2_value:,.0f} (Complete 2013 data)")
    print(f"Phase 3 target: ${phase3_value:,.0f} (Specialized records)")
    print(f"TOTAL RECOVERY: ${phase1_value + phase2_value + phase3_value:,.0f}")
    
    return priority_files

def generate_next_action_script():
    """Generate script to process next priority file."""
    
    next_file = "chargesummary2013.xls"
    
    script_content = f"""#!/usr/bin/env python3
\"\"\"
Import {next_file} - Critical 2013 charge data.

This file should contain comprehensive 2013 charge/expense data
to fill the massive gap (only 55 records currently).
\"\"\"

import os
import sys
import pandas as pd
import psycopg2
from datetime import datetime
from decimal import Decimal

def import_2013_charges():
    \"\"\"Import 2013 charge summary data.\"\"\"
    
    file_path = "L:/limo/docs/2012-2013 excel/{next_file}"
    
    print("IMPORTING 2013 CHARGE SUMMARY - CRITICAL GAP FILLER")
    print("=" * 60)
    print(f"File: {{file_path}}")
    print("Current 2013 records: 55 (massive gap)")
    print("Expected recovery: $150,000+")
    
    if not os.path.exists(file_path):
        print(f"[FAIL] File not found: {{file_path}}")
        return
    
    try:
        # Read Excel file (handle .xls format)
        df = pd.read_excel(file_path, sheet_name=None, engine='xlrd')
        
        print(f"\\n📋 FILE STRUCTURE:")
        print("-" * 40)
        
        for sheet_name, sheet_df in df.items():
            print(f"Sheet: {{sheet_name}}")
            print(f"Rows: {{len(sheet_df)}}")
            print(f"Columns: {{list(sheet_df.columns)[:5]}}...")  # First 5 columns
            
            # Look for amount/charge data
            amount_cols = []
            for col in sheet_df.columns:
                if any(term in str(col).lower() for term in ['amount', 'total', 'charge', 'expense', 'cost']):
                    amount_cols.append(col)
            
            if amount_cols:
                print(f"Amount columns: {{amount_cols}}")
        
        # TODO: Add actual import logic here
        print(f"\\n[WARN]  IMPORT LOGIC NEEDED:")
        print("1. Identify main data sheet")
        print("2. Map columns to receipts table")  
        print("3. Handle 2013 date validation")
        print("4. Import with unique source_hash")
        
    except Exception as e:
        print(f"[FAIL] Error: {{e}}")

if __name__ == "__main__":
    import_2013_charges()
"""

    script_path = f"L:/limo/scripts/import_2013_charges_next.py"
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    print(f"\n📝 NEXT ACTION SCRIPT CREATED:")
    print(f"File: {script_path}")
    print(f"Target: {next_file}")
    print(f"Run with: python -X utf8 {script_path}")

def main():
    """Execute master recovery plan."""
    
    priority_files = create_master_recovery_plan()
    
    print(f"\n" + "=" * 70)
    print("🎯 IMMEDIATE NEXT STEPS:")
    print("=" * 70)
    
    print("1. [OK] 2014 Leasing imported successfully ($168K)")
    print("2. 🎯 Process chargesummary2013.xls next (critical 2013 gap)")
    print("3. 📋 Convert .xls files to .xlsx if needed")
    print("4. 🔄 Repeat for 2015-2016 charge summaries")
    
    print(f"\n💡 KEY INSIGHT:")
    print("Database validation revealed 2012 was complete (2,349 records)")
    print("Focus on 2013-2016 where we have <100 records per year")
    print("Each charge summary file could add 1,000+ missing records")
    
    # Generate next action
    generate_next_action_script()

if __name__ == "__main__":
    main()