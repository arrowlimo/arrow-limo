"""
Widget Launcher Test Script - Smoke test all 136 widgets
Launches widgets one by one to check for errors
"""

import sys
import os
import importlib.util
import json


# Add parent directory to path so we can import desktop_app modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Now we're in L:\limo, so we can import normally
os.chdir(parent_dir)  # Change to L:\limo directory

# Load main.py directly without requiring package import (works even if desktop_app is not a package)
main_path = os.path.join(parent_dir, 'desktop_app', 'main.py')
spec = importlib.util.spec_from_file_location('desktop_app_main', main_path)
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)

# Pull required symbols
DatabaseConnection = main_module.DatabaseConnection
QApplication = main_module.QApplication

# Load mega menu structure from JSON (source of truth)
menu_path = os.path.join(parent_dir, 'desktop_app', 'mega_menu_structure.json')
with open(menu_path, 'r', encoding='utf-8') as f:
    MEGA_MENU_STRUCTURE = json.load(f)

def get_all_widgets():
    """Extract all widgets from mega menu structure"""
    widgets = []
    domains = MEGA_MENU_STRUCTURE.get("domains", []) if isinstance(MEGA_MENU_STRUCTURE, dict) else MEGA_MENU_STRUCTURE
    for domain in domains:
        domain_name = domain.get('domain_name') or domain.get('name') or "Unknown Domain"
        for category in domain.get('categories', []):
            category_name = category.get('category_name') or category.get('name') or "Unknown Category"
            for widget in category.get('widgets', []):
                widgets.append({
                    'domain': domain_name,
                    'category': category_name,
                    'name': widget.get('widget_name') or widget.get('label') or widget.get('widget_name') or "Unnamed Widget",
                    'class_name': widget.get('class_name') or widget.get('widget_class')
                })
    return widgets

def test_widget(widget_info, db):
    """Test launching a single widget"""
    try:
        # Get the class from main module
        widget_class = getattr(main_module, widget_info['class_name'], None)
        if not widget_class:
            return False, f"Class {widget_info['class_name']} not found"
        
        # Try to instantiate
        widget = widget_class(db)
        
        # Try to load data
        if hasattr(widget, 'load_data'):
            widget.load_data()
        
        widget.close()
        return True, "OK"
    
    except Exception as e:
        return False, str(e)

def main():
    """Test all widgets"""
    print("=" * 80)
    print("Widget Smoke Test - Testing all 136 widgets")
    print("=" * 80)
    
    app = QApplication(sys.argv)
    db = DatabaseConnection()
    print("✅ Database connected")
    print()
    
    widgets = get_all_widgets()
    print(f"Found {len(widgets)} widgets to test")
    print()
    
    passed = 0
    failed = 0
    errors = []
    
    for i, widget_info in enumerate(widgets, 1):
        widget_name = f"{widget_info['domain']} > {widget_info['category']} > {widget_info['name']}"
        print(f"[{i}/{len(widgets)}] Testing: {widget_name[:60]}...", end=" ")
        
        success, message = test_widget(widget_info, db)
        
        if success:
            print("✅")
            passed += 1
        else:
            print(f"❌")
            failed += 1
            errors.append({
                'widget': widget_name,
                'class': widget_info['class_name'],
                'error': message
            })
    
    print()
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if errors:
        print()
        print("FAILURES:")
        print("-" * 80)
        for err in errors:
            print(f"\n❌ {err['widget']}")
            print(f"   Class: {err['class']}")
            print(f"   Error: {err['error']}")
    
    db.close()
    app.quit()

if __name__ == '__main__':
    main()
