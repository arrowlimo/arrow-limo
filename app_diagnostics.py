#!/usr/bin/env python3
"""
Quick diagnostic check for desktop app status
"""

import os
import sys
import time
import psycopg2

# Check database connection
print("="*80)
print("DIAGNOSTIC CHECK - Desktop App & Database")
print("="*80)

print("\n1️⃣  DATABASE CONNECTION")
try:
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM charters")
    charter_count = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema='public'
    """)
    table_count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"   ✅ Connected to almsdata")
    print(f"   ✅ Tables: {table_count}")
    print(f"   ✅ Charters: {charter_count}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

print("\n2️⃣  MEGA MENU WIDGET")
try:
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_app'))
    
    from mega_menu_widget import MegaMenuWidget
    print(f"   ✅ MegaMenuWidget imported successfully")
    
    # Check menu structure JSON
    menu_file = Path(__file__).parent / 'desktop_app' / 'mega_menu_structure.json'
    if menu_file.exists():
        import json
        with open(menu_file) as f:
            menu_data = json.load(f)
        domain_count = len(menu_data.get('domains', []))
        widget_count = sum(len(d.get('categories', [])) for d in menu_data.get('domains', []))
        print(f"   ✅ Menu structure: {domain_count} domains, {widget_count} categories")
    else:
        print(f"   ⚠️  Menu structure file not found")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n3️⃣  KEY DASHBOARD WIDGETS")
widget_tests = [
    ('FleetManagementWidget', 'from dashboards_core import FleetManagementWidget'),
    ('FinancialDashboardWidget', 'from dashboards_core import FinancialDashboardWidget'),
    ('CharterManagementDashboardWidget', 'from dashboards_operations import CharterManagementDashboardWidget'),
]

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_app'))
    
    for widget_name, import_stmt in widget_tests:
        try:
            exec(import_stmt)
            print(f"   ✅ {widget_name}: Importable")
        except Exception as e:
            print(f"   ❌ {widget_name}: {str(e)[:60]}...")
            
except Exception as e:
    print(f"   ⚠️  Widget import testing error: {e}")

print("\n4️⃣  APPLICATION WINDOW")
try:
    # Check if desktop app main.py has syntax errors
    main_file = Path(__file__).parent / 'desktop_app' / 'main.py'
    if main_file.exists():
        with open(main_file) as f:
            code = f.read()
        compile(code, 'main.py', 'exec')
        print(f"   ✅ main.py: Syntax OK ({len(code)} bytes)")
        
        # Count classes and functions
        import ast
        tree = ast.parse(code)
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        print(f"   ✅ Classes: {len(classes)}, Functions: {len(functions)}")
    else:
        print(f"   ❌ main.py not found")
        
except Exception as e:
    print(f"   ❌ Syntax check failed: {e}")

print("\n" + "="*80)
print("✅ DIAGNOSTIC CHECK COMPLETE")
print("="*80)
print("\nTo launch desktop app:")
print("  python -X utf8 desktop_app/main.py")
print("\nApp should be running in background terminal:")
print("  Terminal ID: 880d84e4-35d9-492c-9eab-0b63f813192c")
