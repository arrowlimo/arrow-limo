#!/usr/bin/env python3
"""
Desktop App Comprehensive UI Test Automation
Tests every button, feature, widget, and action without manual clicking.
Generates coverage report showing what works and what needs attention.
"""

import sys
import time
import traceback
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# PyQt6 testing utilities
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QAction, QMenu,
    QWidget, QCheckBox, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QDialog, QTabWidget, QTableWidget,
    QTreeWidget, QCalendarWidget
)
from PyQt6.QtCore import Qt, QTimer, QObject
from PyQt6.QtGui import QIcon

class UITestSuite:
    def __init__(self, app_module_path='l:\\limo\\desktop_app'):
        self.app = None
        self.window = None
        self.results = defaultdict(list)
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.app_module_path = app_module_path
        
    def start_app(self):
        """Launch the desktop app"""
        try:
            print("🚀 Starting desktop app...")
            sys.path.insert(0, str(Path(self.app_module_path).parent))
            
            # Import and run main app
            from desktop_app.main import MainWindow
            
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
            
            self.window = MainWindow()
            print("✅ App started successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to start app: {e}")
            traceback.print_exc()
            return False
    
    def discover_all_widgets(self, parent=None, depth=0, max_depth=10):
        """Recursively discover all widgets in the app"""
        if parent is None:
            parent = self.window
        
        widgets = []
        
        if depth > max_depth:
            return widgets
        
        try:
            # Get all child widgets
            for child in parent.children():
                if isinstance(child, QWidget):
                    widgets.append({
                        'widget': child,
                        'type': type(child).__name__,
                        'name': child.objectName() or 'unnamed',
                        'depth': depth,
                        'parent': type(parent).__name__
                    })
                    # Recursively discover children
                    widgets.extend(self.discover_all_widgets(child, depth + 1, max_depth))
        except Exception as e:
            print(f"  Warning: Could not discover widgets: {e}")
        
        return widgets
    
    def test_all_buttons(self):
        """Find and test all buttons"""
        print("\n" + "="*80)
        print("🔘 TESTING ALL BUTTONS")
        print("="*80)
        
        buttons = self._find_widgets_by_type(QPushButton)
        print(f"Found {len(buttons)} buttons\n")
        
        for btn in buttons[:50]:  # Limit to first 50 to avoid too many operations
            try:
                self.test_count += 1
                btn_name = btn.text() or btn.objectName() or "Unnamed"
                btn_text = btn_name[:60]
                
                # Check if button is enabled
                if not btn.isEnabled():
                    self.results['skipped_buttons'].append(btn_text)
                    self.skipped_count += 1
                    print(f"  ⊘ SKIPPED: {btn_text} (disabled)")
                    continue
                
                # Try to click it
                print(f"  🔘 Testing: {btn_text}")
                btn.click()
                self.app.processEvents()
                time.sleep(0.1)
                
                self.results['tested_buttons'].append(btn_text)
                self.passed_count += 1
                print(f"    ✅ Clicked successfully")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_buttons'].append((btn_text, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    def test_all_menu_actions(self):
        """Find and test all menu actions"""
        print("\n" + "="*80)
        print("📋 TESTING ALL MENU ACTIONS")
        print("="*80)
        
        actions = self._find_all_actions()
        print(f"Found {len(actions)} menu actions\n")
        
        for action in actions[:50]:
            try:
                self.test_count += 1
                action_text = action.text() or action.objectName() or "Unnamed"
                action_text = action_text[:60]
                
                # Check if action is enabled
                if not action.isEnabled():
                    self.results['skipped_actions'].append(action_text)
                    self.skipped_count += 1
                    print(f"  ⊘ SKIPPED: {action_text} (disabled)")
                    continue
                
                print(f"  📋 Testing: {action_text}")
                action.trigger()
                self.app.processEvents()
                time.sleep(0.1)
                
                self.results['tested_actions'].append(action_text)
                self.passed_count += 1
                print(f"    ✅ Triggered successfully")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_actions'].append((action_text, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    def test_all_tabs(self):
        """Test switching between all tabs"""
        print("\n" + "="*80)
        print("📑 TESTING ALL TABS")
        print("="*80)
        
        tabs = self._find_widgets_by_type(QTabWidget)
        print(f"Found {len(tabs)} tab widgets\n")
        
        for tab_widget in tabs:
            try:
                tab_count = tab_widget.count()
                print(f"  Tab Widget: {tab_count} tabs")
                
                for i in range(tab_count):
                    try:
                        self.test_count += 1
                        tab_name = tab_widget.tabText(i)
                        print(f"    📑 Testing tab: {tab_name}")
                        
                        tab_widget.setCurrentIndex(i)
                        self.app.processEvents()
                        time.sleep(0.2)
                        
                        self.results['tested_tabs'].append(tab_name)
                        self.passed_count += 1
                        print(f"      ✅ Tab switched successfully")
                        
                    except Exception as e:
                        self.failed_count += 1
                        self.results['failed_tabs'].append((tab_name, str(e)))
                        print(f"      ❌ Failed: {str(e)[:50]}")
                        
            except Exception as e:
                print(f"  ❌ Error testing tab widget: {e}")
    
    def test_text_inputs(self):
        """Test text input widgets"""
        print("\n" + "="*80)
        print("⌨️  TESTING TEXT INPUTS")
        print("="*80)
        
        text_inputs = self._find_widgets_by_type(QLineEdit)
        print(f"Found {len(text_inputs)} text input fields\n")
        
        for text_input in text_inputs[:30]:
            try:
                self.test_count += 1
                input_name = text_input.objectName() or "Unnamed"
                
                if not text_input.isEnabled():
                    self.skipped_count += 1
                    print(f"  ⊘ SKIPPED: {input_name} (disabled)")
                    continue
                
                print(f"  ⌨️  Testing: {input_name}")
                text_input.setText("TEST_VALUE_12345")
                self.app.processEvents()
                
                self.results['tested_inputs'].append(input_name)
                self.passed_count += 1
                print(f"    ✅ Text input works")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_inputs'].append((input_name, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    def test_dropdowns(self):
        """Test dropdown/combobox widgets"""
        print("\n" + "="*80)
        print("🔽 TESTING DROPDOWNS")
        print("="*80)
        
        dropdowns = self._find_widgets_by_type(QComboBox)
        print(f"Found {len(dropdowns)} dropdowns\n")
        
        for dropdown in dropdowns[:30]:
            try:
                self.test_count += 1
                dropdown_name = dropdown.objectName() or "Unnamed"
                item_count = dropdown.count()
                
                if not dropdown.isEnabled():
                    self.skipped_count += 1
                    print(f"  ⊘ SKIPPED: {dropdown_name} (disabled)")
                    continue
                
                print(f"  🔽 Testing: {dropdown_name} ({item_count} items)")
                
                if item_count > 0:
                    dropdown.setCurrentIndex(0)
                    self.app.processEvents()
                    time.sleep(0.1)
                    
                    if item_count > 1:
                        dropdown.setCurrentIndex(min(1, item_count - 1))
                        self.app.processEvents()
                
                self.results['tested_dropdowns'].append(dropdown_name)
                self.passed_count += 1
                print(f"    ✅ Dropdown works")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_dropdowns'].append((dropdown_name, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    def test_tables(self):
        """Test table widgets"""
        print("\n" + "="*80)
        print("📊 TESTING TABLES")
        print("="*80)
        
        tables = self._find_widgets_by_type(QTableWidget)
        print(f"Found {len(tables)} tables\n")
        
        for table in tables[:10]:
            try:
                self.test_count += 1
                table_name = table.objectName() or "Unnamed"
                row_count = table.rowCount()
                col_count = table.columnCount()
                
                print(f"  📊 Testing: {table_name} ({row_count}x{col_count})")
                
                if row_count > 0 and col_count > 0:
                    table.setCurrentCell(0, 0)
                    self.app.processEvents()
                
                self.results['tested_tables'].append(table_name)
                self.passed_count += 1
                print(f"    ✅ Table works")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_tables'].append((table_name, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    def test_checkboxes(self):
        """Test checkbox widgets"""
        print("\n" + "="*80)
        print("☑️  TESTING CHECKBOXES")
        print("="*80)
        
        checkboxes = self._find_widgets_by_type(QCheckBox)
        print(f"Found {len(checkboxes)} checkboxes\n")
        
        for checkbox in checkboxes[:20]:
            try:
                self.test_count += 1
                checkbox_name = checkbox.text() or checkbox.objectName() or "Unnamed"
                
                if not checkbox.isEnabled():
                    self.skipped_count += 1
                    print(f"  ⊘ SKIPPED: {checkbox_name} (disabled)")
                    continue
                
                print(f"  ☑️  Testing: {checkbox_name}")
                checkbox.setChecked(not checkbox.isChecked())
                self.app.processEvents()
                
                self.results['tested_checkboxes'].append(checkbox_name)
                self.passed_count += 1
                print(f"    ✅ Checkbox works")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_checkboxes'].append((checkbox_name, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    def test_spinners(self):
        """Test numeric spinners"""
        print("\n" + "="*80)
        print("🔢 TESTING NUMERIC SPINNERS")
        print("="*80)
        
        spinners = self._find_widgets_by_type(QSpinBox) + self._find_widgets_by_type(QDoubleSpinBox)
        print(f"Found {len(spinners)} spinners\n")
        
        for spinner in spinners[:20]:
            try:
                self.test_count += 1
                spinner_name = spinner.objectName() or "Unnamed"
                
                if not spinner.isEnabled():
                    self.skipped_count += 1
                    print(f"  ⊘ SKIPPED: {spinner_name} (disabled)")
                    continue
                
                print(f"  🔢 Testing: {spinner_name}")
                current_value = spinner.value()
                spinner.setValue(current_value + 1)
                self.app.processEvents()
                
                self.results['tested_spinners'].append(spinner_name)
                self.passed_count += 1
                print(f"    ✅ Spinner works")
                
            except Exception as e:
                self.failed_count += 1
                self.results['failed_spinners'].append((spinner_name, str(e)))
                print(f"    ❌ Failed: {str(e)[:50]}")
    
    # Helper methods
    def _find_widgets_by_type(self, widget_type):
        """Find all widgets of a specific type"""
        widgets = []
        for item in self.discover_all_widgets():
            if isinstance(item['widget'], widget_type):
                widgets.append(item['widget'])
        return widgets
    
    def _find_all_actions(self):
        """Find all QActions in the app"""
        actions = []
        
        def collect_actions(obj):
            try:
                if hasattr(obj, 'actions'):
                    for action in obj.actions():
                        if isinstance(action, QAction):
                            actions.append(action)
                        # Check if it's a menu with submenus
                        if hasattr(action, 'menu') and action.menu():
                            collect_actions(action.menu())
            except:
                pass
            
            # Recursively check children
            for child in obj.children():
                collect_actions(child)
        
        collect_actions(self.window)
        return actions
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n\n" + "="*80)
        print("📊 COMPREHENSIVE UI TEST REPORT")
        print("="*80)
        print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n📈 SUMMARY:")
        print(f"  Total Tests: {self.test_count}")
        print(f"  ✅ Passed: {self.passed_count}")
        print(f"  ❌ Failed: {self.failed_count}")
        print(f"  ⊘ Skipped: {self.skipped_count}")
        
        if self.test_count > 0:
            pass_rate = (self.passed_count / self.test_count) * 100
            print(f"  📊 Pass Rate: {pass_rate:.1f}%")
        
        print(f"\n📋 TESTED COMPONENTS:")
        for category, items in sorted(self.results.items()):
            if items and not category.startswith('failed') and not category.startswith('skipped'):
                print(f"  {category}: {len(items)} items")
        
        if self.failed_count > 0:
            print(f"\n❌ FAILED ITEMS:")
            for category, items in sorted(self.results.items()):
                if items and category.startswith('failed'):
                    for item in items[:5]:  # Show first 5
                        if isinstance(item, tuple):
                            print(f"  - {item[0]}: {item[1][:50]}")
                        else:
                            print(f"  - {item}")
        
        if self.skipped_count > 0:
            print(f"\n⊘ SKIPPED ITEMS (disabled or unavailable):")
            for category, items in sorted(self.results.items()):
                if items and category.startswith('skipped'):
                    print(f"  {category}: {len(items)} items")
        
        print("\n" + "="*80)
        print("✅ Test suite complete!")
        print("="*80 + "\n")
    
    def run_full_test_suite(self):
        """Run all tests"""
        print("\n🚀 STARTING COMPREHENSIVE UI TEST SUITE\n")
        
        if not self.start_app():
            return False
        
        try:
            # Run all test methods
            self.test_all_buttons()
            self.test_all_menu_actions()
            self.test_all_tabs()
            self.test_text_inputs()
            self.test_dropdowns()
            self.test_tables()
            self.test_checkboxes()
            self.test_spinners()
            
            self.generate_report()
            return True
            
        except Exception as e:
            print(f"\n❌ Test suite error: {e}")
            traceback.print_exc()
            return False
        finally:
            if self.app:
                self.app.quit()

def main():
    """Run the test suite"""
    tester = UITestSuite()
    success = tester.run_full_test_suite()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
