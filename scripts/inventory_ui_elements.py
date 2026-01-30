#!/usr/bin/env python3
"""
Desktop App Interactive Element Inventory
Discovers and catalogs every button, menu, widget, and feature.
Creates a detailed map of all testable elements.
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QMenu,
    QWidget, QCheckBox, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QDialog, QTabWidget, QTableWidget,
    QTreeWidget, QCalendarWidget, QLabel, QDial, QSlider,
    QProgressBar, QDateEdit, QTimeEdit, QDateTimeEdit
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

class ElementInventory:
    def __init__(self, app_module_path='l:\\limo\\desktop_app'):
        self.app = None
        self.window = None
        self.inventory = defaultdict(list)
        self.app_module_path = app_module_path
        
    def start_app(self):
        """Launch the desktop app"""
        try:
            print("🚀 Starting desktop app for inventory scan...")
            sys.path.insert(0, str(Path(self.app_module_path).parent))
            
            from desktop_app.main import MainWindow
            
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
            
            self.window = MainWindow()
            print("✅ App started\n")
            return True
        except Exception as e:
            print(f"❌ Failed to start app: {e}")
            return False
    
    def discover_elements(self, parent=None, depth=0):
        """Recursively discover all interactive elements"""
        if parent is None:
            parent = self.window
        
        try:
            for child in parent.children():
                if not isinstance(child, QWidget):
                    continue
                
                self._catalog_element(child, depth)
                self.discover_elements(child, depth + 1)
        except:
            pass
    
    def _catalog_element(self, widget, depth):
        """Add element to inventory"""
        widget_type = type(widget).__name__
        name = widget.objectName() or 'unnamed'
        text = ''
        enabled = widget.isEnabled()
        visible = widget.isVisible()
        
        # Extract descriptive text based on type
        if isinstance(widget, QPushButton):
            text = widget.text()
            tooltip = widget.toolTip()
            self.inventory['buttons'].append({
                'name': name,
                'text': text,
                'tooltip': tooltip,
                'enabled': enabled,
                'visible': visible,
                'type': 'button'
            })
        
        elif isinstance(widget, QAction):
            text = widget.text()
            self.inventory['actions'].append({
                'text': text,
                'enabled': enabled,
                'shortcut': str(widget.shortcut()),
                'type': 'action'
            })
        
        elif isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText()
            self.inventory['text_inputs'].append({
                'name': name,
                'placeholder': placeholder,
                'enabled': enabled,
                'readonly': widget.isReadOnly(),
                'type': 'text_input'
            })
        
        elif isinstance(widget, QTextEdit):
            self.inventory['text_areas'].append({
                'name': name,
                'enabled': enabled,
                'readonly': widget.isReadOnly(),
                'type': 'text_area'
            })
        
        elif isinstance(widget, QComboBox):
            items = [widget.itemText(i) for i in range(widget.count())]
            self.inventory['dropdowns'].append({
                'name': name,
                'items_count': len(items),
                'items': items[:10],  # First 10 items
                'enabled': enabled,
                'type': 'dropdown'
            })
        
        elif isinstance(widget, QCheckBox):
            text = widget.text()
            self.inventory['checkboxes'].append({
                'name': name,
                'text': text,
                'checked': widget.isChecked(),
                'enabled': enabled,
                'type': 'checkbox'
            })
        
        elif isinstance(widget, QSpinBox):
            self.inventory['spinners_int'].append({
                'name': name,
                'value': widget.value(),
                'min': widget.minimum(),
                'max': widget.maximum(),
                'enabled': enabled,
                'type': 'spinner_int'
            })
        
        elif isinstance(widget, QDoubleSpinBox):
            self.inventory['spinners_float'].append({
                'name': name,
                'value': widget.value(),
                'min': widget.minimum(),
                'max': widget.maximum(),
                'enabled': enabled,
                'type': 'spinner_float'
            })
        
        elif isinstance(widget, QTableWidget):
            self.inventory['tables'].append({
                'name': name,
                'rows': widget.rowCount(),
                'columns': widget.columnCount(),
                'enabled': enabled,
                'type': 'table'
            })
        
        elif isinstance(widget, QTabWidget):
            tabs = [widget.tabText(i) for i in range(widget.count())]
            self.inventory['tab_widgets'].append({
                'name': name,
                'tabs': tabs,
                'count': len(tabs),
                'type': 'tabs'
            })
        
        elif isinstance(widget, QCalendarWidget):
            self.inventory['calendars'].append({
                'name': name,
                'enabled': enabled,
                'type': 'calendar'
            })
        
        elif isinstance(widget, QDateEdit):
            self.inventory['date_inputs'].append({
                'name': name,
                'value': str(widget.date()),
                'enabled': enabled,
                'type': 'date_input'
            })
        
        elif isinstance(widget, QTimeEdit):
            self.inventory['time_inputs'].append({
                'name': name,
                'value': str(widget.time()),
                'enabled': enabled,
                'type': 'time_input'
            })
        
        elif isinstance(widget, QSlider):
            self.inventory['sliders'].append({
                'name': name,
                'value': widget.value(),
                'min': widget.minimum(),
                'max': widget.maximum(),
                'enabled': enabled,
                'type': 'slider'
            })
        
        elif isinstance(widget, QLabel):
            text = widget.text()
            if text and len(text) > 3:  # Only meaningful labels
                self.inventory['labels'].append({
                    'name': name,
                    'text': text[:60],
                    'type': 'label'
                })
    
    def find_all_menu_actions(self, obj=None):
        """Recursively find all menu actions"""
        if obj is None:
            obj = self.window
        
        try:
            if hasattr(obj, 'actions'):
                for action in obj.actions():
                    if isinstance(action, QAction):
                        text = action.text()
                        if text and text.strip():
                            self.inventory['menu_actions'].append({
                                'text': text,
                                'enabled': action.isEnabled(),
                                'shortcut': str(action.shortcut()),
                                'checkable': action.isCheckable(),
                                'type': 'menu_action'
                            })
                        
                        # Check for submenus
                        if hasattr(action, 'menu') and action.menu():
                            self.find_all_menu_actions(action.menu())
        except:
            pass
        
        # Recursively check children
        try:
            for child in obj.children():
                self.find_all_menu_actions(child)
        except:
            pass
    
    def print_inventory(self):
        """Print formatted inventory"""
        print("\n" + "="*80)
        print("📚 INTERACTIVE ELEMENT INVENTORY")
        print("="*80)
        
        categories = [
            ('buttons', '🔘 Buttons'),
            ('menu_actions', '📋 Menu Actions'),
            ('text_inputs', '⌨️  Text Inputs'),
            ('text_areas', '📝 Text Areas'),
            ('dropdowns', '🔽 Dropdowns'),
            ('checkboxes', '☑️  Checkboxes'),
            ('spinners_int', '🔢 Integer Spinners'),
            ('spinners_float', '💯 Float Spinners'),
            ('sliders', '🎚️  Sliders'),
            ('tables', '📊 Tables'),
            ('tab_widgets', '📑 Tabs'),
            ('calendars', '📅 Calendars'),
            ('date_inputs', '📆 Date Inputs'),
            ('time_inputs', '⏰ Time Inputs'),
            ('labels', '🏷️  Labels'),
        ]
        
        total_elements = 0
        
        for key, display_name in categories:
            items = self.inventory[key]
            if items:
                count = len(items)
                total_elements += count
                print(f"\n{display_name}: {count}")
                
                for i, item in enumerate(items[:5], 1):  # Show first 5 of each
                    self._print_item(item, i)
                
                if len(items) > 5:
                    print(f"  ... and {len(items) - 5} more")
        
        print("\n" + "="*80)
        print(f"📊 TOTAL INTERACTIVE ELEMENTS: {total_elements}")
        print("="*80 + "\n")
    
    def _print_item(self, item, index):
        """Print a single inventory item"""
        item_type = item.get('type', 'unknown')
        
        if item_type == 'button':
            text = item.get('text', 'No text')
            status = "✓" if item.get('enabled') else "✗"
            print(f"  {index}. [{status}] {text}")
        
        elif item_type == 'menu_action':
            text = item.get('text', 'No text')
            shortcut = item.get('shortcut', '')
            shortcut_str = f" ({shortcut})" if shortcut else ""
            print(f"  {index}. {text}{shortcut_str}")
        
        elif item_type == 'dropdown':
            name = item.get('name', 'unnamed')
            count = item.get('items_count', 0)
            print(f"  {index}. {name} ({count} items)")
        
        elif item_type == 'table':
            name = item.get('name', 'unnamed')
            rows = item.get('rows', 0)
            cols = item.get('columns', 0)
            print(f"  {index}. {name} ({rows}x{cols})")
        
        elif item_type == 'tabs':
            name = item.get('name', 'unnamed')
            tabs = item.get('tabs', [])
            print(f"  {index}. {name}: {', '.join(tabs[:3])}")
        
        else:
            name = item.get('name', item.get('text', 'unnamed'))
            print(f"  {index}. {name}")
    
    def export_as_json(self, filename='element_inventory.json'):
        """Export inventory as JSON"""
        output_path = Path('l:\\limo') / filename
        
        # Convert to serializable format
        data = {}
        for key, items in self.inventory.items():
            data[key] = items
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Inventory exported to {output_path}")
    
    def run(self):
        """Run the inventory scan"""
        if not self.start_app():
            return False
        
        try:
            print("🔍 Scanning for interactive elements...\n")
            self.discover_elements()
            self.find_all_menu_actions()
            self.print_inventory()
            self.export_as_json()
            return True
        finally:
            if self.app:
                self.app.quit()

def main():
    """Run the inventory scanner"""
    inventory = ElementInventory()
    success = inventory.run()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
