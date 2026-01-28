#!/usr/bin/env python3
"""
Display audit results summary
"""

import json
from pathlib import Path

def show_naming_audit():
    """Display naming audit results"""
    report_file = Path("L:/limo/reports/naming_audit_20260123_011158.json")
    
    if not report_file.exists():
        print("❌ Naming audit report not found")
        return
    
    with open(report_file) as f:
        data = json.load(f)
    
    print("="*80)
    print("NAMING AUDIT RESULTS")
    print("="*80)
    
    summary = data['summary']
    print(f"\n📊 SUMMARY:")
    print(f"   Total Naming Mismatches: {summary['total_mismatches']}")
    print(f"   HIGH Severity: {summary['high_severity']}")
    print(f"   Rename Recommendations: {summary['recommendations']}")
    
    print(f"\n⚠️  HIGH SEVERITY MISMATCHES:")
    high_severity = [m for m in data['naming_mismatches'] if m['severity'] == 'HIGH']
    for m in high_severity[:15]:
        print(f"   Table: {m['table']}")
        print(f"     Code expects: {m['code_expects']}")
        print(f"     Database has: {m['database_has']}")
        print()
    
    print(f"\n💡 RECOMMENDED RENAMES:")
    for rec in data['naming_recommendations'][:10]:
        print(f"   {rec['table']}: {rec['rename']}")
        print(f"     → {rec['reason']}")
        print()


def show_storage_audit():
    """Display storage audit results"""
    report_file = Path("L:/limo/reports/storage_audit_20260123_011129.json")
    
    if not report_file.exists():
        print("❌ Storage audit report not found")
        return
    
    with open(report_file) as f:
        data = json.load(f)
    
    print("="*80)
    print("STORAGE & DATABASE AUDIT RESULTS")
    print("="*80)
    
    print(f"\n📁 DOCUMENT STORAGE:")
    for path, status in data['document_storage'].items():
        if isinstance(status, dict):
            exists = "✅" if status.get('exists') else "❌"
            print(f"   {exists} {path}")
    
    if data['document_storage'].get('blob_tables'):
        print(f"\n   ✅ Database tables for documents:")
        tables = data['document_storage']['blob_tables'].get('tables', [])
        for table in tables[:5]:
            print(f"      - {table}")
    
    print(f"\n🚗 VEHICLE STORAGE:")
    vs = data['vehicle_storage']
    print(f"   Vehicle code files: {'✅' if vs.get('has_code') else '❌'} {len(vs.get('code_files', []))}")
    print(f"   Document handling: {'✅' if vs.get('has_doc_handling') else '❌'}")
    
    print(f"\n🔐 DATABASE SELECTION (Local vs Neon):")
    db = data['db_selection']
    print(f"   Login screen selection: {'✅' if db.get('has_login_selection') else '❌'}")
    print(f"   Environment files: {'✅' if db.get('has_env_files') else '❌'}")
    print(f"   Config files: {'✅' if db.get('has_config_files') else '❌'}")
    
    print(f"\n⚠️  ISSUES TO FIX:")
    if data['issues']:
        for issue in data['issues']:
            print(f"   - {issue}")
    else:
        print(f"   ✅ No critical issues")


def main():
    print("\n")
    show_naming_audit()
    print("\n")
    show_storage_audit()
    print("\n")


if __name__ == '__main__':
    main()
