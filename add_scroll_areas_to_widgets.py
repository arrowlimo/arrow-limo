"""
Add scroll areas to all desktop app widgets for better non-fullscreen usability
"""
import os
import re

# List of widget files to update
WIDGET_FILES = [
    'desktop_app/employee_management_widget.py',
    'desktop_app/vehicle_management_widget.py',
    'desktop_app/asset_management_widget.py',
    'desktop_app/admin_management_widget.py',
    'desktop_app/beverage_management_widget.py',
    'desktop_app/billing_management_widget.py',
    'desktop_app/dispatch_management_widget.py',
    'desktop_app/document_management_widget.py',
    'desktop_app/tax_management_widget.py',
    'desktop_app/tax_widget.py',
    'desktop_app/wcb_annual_return_widget.py',
    'desktop_app/wcb_rate_widget.py',
    'desktop_app/roe_form_widget.py',
    'desktop_app/enhanced_charter_widget.py',
    'desktop_app/enhanced_client_widget.py',
    'desktop_app/enhanced_employee_widget.py',
    'desktop_app/enhanced_vehicle_widget.py',
    'desktop_app/manage_banking_widget.py',
    'desktop_app/manage_cash_box_widget.py',
    'desktop_app/manage_personal_expenses_widget.py',
    'desktop_app/manage_receipts_widget.py',
    'desktop_app/vendor_invoice_manager.py',
    'desktop_app/quote_generator_widget.py',
    'desktop_app/custom_report_builder.py',
]

def add_qscrollarea_import(content):
    """Add QScrollArea to imports if not present"""
    # Check if QScrollArea is already imported
    if 'QScrollArea' in content:
        return content
    
    # Find PyQt6.QtWidgets import
    pattern = r'from PyQt6\.QtWidgets import \((.*?)\)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        imports = match.group(1)
        # Add QScrollArea if not present
        if 'QScrollArea' not in imports:
            # Add after QPushButton or QLabel
            if 'QPushButton,' in imports:
                imports = imports.replace('QPushButton,', 'QPushButton,\n    QScrollArea,')
            elif 'QLabel,' in imports:
                imports = imports.replace('QLabel,', 'QLabel,\n    QScrollArea,')
            else:
                # Add at the end before the closing paren
                imports = imports.rstrip() + ',\n    QScrollArea'
            
            content = content.replace(match.group(0), f'from PyQt6.QtWidgets import ({imports})')
    
    return content

def wrap_in_scroll_area(content, widget_name):
    """Wrap widget content in a scroll area"""
    # Look for common patterns in __init__ or init_ui methods
    
    # Pattern 1: def __init__(...): ... layout = QVBoxLayout(self)
    pattern1 = r'(def __init__\(.*?\):.*?)(layout = QVBoxLayout\(self\))(.*?)(\n\s+def )'
   
    # Pattern 2: def init_ui(...): ... layout = QVBoxLayout(self) or self.setLayout
    pattern2 = r'(def init_ui\(.*?\):.*?)((?:layout|main_layout) = QVBoxLayout\((?:self|)\))(.*?)(\n\s+def )'
    
    # Try pattern 1
    match = re.search(pattern1, content, re.DOTALL)
    if match:
        print(f"  Found pattern 1 in {widget_name}")
        before_layout = match.group(1)
        layout_line = match.group(2)
        after_layout = match.group(3)
        next_def = match.group(4)
        
        # Check if scroll area already exists
        if 'QScrollArea' in after_layout and 'scroll' in after_layout.lower():
            print(f"  Scroll area already exists in {widget_name}")
            return content
        
        new_section = f'''{before_layout}# Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Container for all content
        container = QWidget()
        layout = QVBoxLayout(container)
{after_layout}
        # Set scroll area widget
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area){next_def}'''
        
        content = content.replace(match.group(0), new_section)
        return content
    
    # Try pattern 2
    match = re.search(pattern2, content, re.DOTALL)
    if match:
        print(f"  Found pattern 2 in {widget_name}")
        # Similar logic for init_ui
        
    return content

def process_widget_file(filepath):
    """Process a single widget file"""
    full_path = os.path.join('L:\\limo', filepath)
    if not os.path.exists(full_path):
        print(f"Skipping {filepath} - file not found")
        return False
    
    print(f"Processing {filepath}...")
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add QScrollArea import
    new_content = add_qscrollarea_import(content)
    
    # Wrap in scroll area (may need custom logic per widget)
    # For now, just add the import
    
    if new_content != content:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  ✓ Updated {filepath}")
        return True
    else:
        print(f"  - No changes needed for {filepath}")
        return False

if __name__ == '__main__':
    print("Adding scroll areas to desktop app widgets...\n")
    
    updated_count = 0
    for widget_file in WIDGET_FILES:
        if process_widget_file(widget_file):
            updated_count += 1
    
    print(f"\n✓ Updated {updated_count} widget files")
    print("\nNote: Some widgets may require manual adjustment.")
    print("Review each widget to ensure the scroll area is properly integrated.")
