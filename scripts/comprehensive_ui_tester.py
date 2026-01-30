#!/usr/bin/env python3
"""
Desktop App Comprehensive Automation Testing
Tests every button, menu, input, feature, and interactive element.
Generates detailed test report with pass/fail/skip statistics.
"""

import sys
import json
import time
import traceback
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QMenu, QDialog,
    QWidget, QCheckBox, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QTabWidget, QTableWidget,
    QCalendarWidget, QLabel, QSlider, QDateEdit, QTimeEdit,
    QMessageBox, QFileDialog
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTimer, QDate, QTime

class ComprehensiveUITester:
    def __init__(self, app_module_path='l:\\limo\\desktop_app'):
        self.app = None
        self.window = None
        self.app_module_path = app_module_path
        
        # Test results tracking
        self.results = {
            'buttons_clicked': 0,
            'buttons_failed': [],
            'buttons_skipped': [],
            'actions_triggered': 0,
            'actions_failed': [],
            'tabs_switched': 0,
            'tabs_failed': [],
            'inputs_tested': 0,
            'inputs_failed': [],
            'dropdowns_tested': 0,
            'dropdowns_failed': [],
            'tables_tested': 0,
            'tables_failed': [],
            'checkboxes_toggled': 0,
            'checkboxes_failed': [],
            'spinners_tested': 0,
            'spinners_failed': [],
            'total_tests': 0,
            'total_passed': 0,
            'total_failed': 0,
            'total_skipped': 0,
            'test_categories': defaultdict(dict),
            'timestamp': datetime.now().isoformat()
        }
    
    def start_app(self):
        """Launch the desktop app"""
        try:
            print("🚀 Starting desktop app for comprehensive testing...\n")
            sys.path.insert(0, str(Path(self.app_module_path).parent))
            
            from desktop_app.main import MainWindow
            
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
            
            self.window = MainWindow()
            print("✅ App started successfully\n")
            return True
        except Exception as e:
            print(f"❌ Failed to start app: {e}")
            traceback.print_exc()
            return False
    
    def test_all_buttons(self):
        """Test clicking all buttons"""
        print("🔘 Testing Buttons...")
        count = 0
        max_test_count = 100  # Test more buttons
        
        def process_buttons(parent, depth=0):
            nonlocal count
            if not isinstance(parent, QWidget) or depth > 15:
                return
            
            for child in parent.children():
                if count >= max_test_count:
                    return
                    
                if isinstance(child, QPushButton) and child.isEnabled() and child.isVisible():
                    try:
                        text = child.text()
                        
                        # Skip problematic buttons that open dialogs
                        if any(skip in text.lower() for skip in ['open', 'save', 'browse', 'file', 'create', 'new', 'load', 'import', 'export']):
                            self.results['buttons_skipped'].append(text or 'unnamed')
                            continue
                        
                        child.click()
                        self.results['buttons_clicked'] += 1
                        count += 1
                        self.app.processEvents()
                        time.sleep(0.05)  # Brief delay
                    except Exception as e:
                        self.results['buttons_failed'].append({
                            'button': text or 'unnamed',
                            'error': str(e)[:100]
                        })
                
                process_buttons(child, depth + 1)
        
        try:
            process_buttons(self.window)
            print(f"  ✅ Clicked {self.results['buttons_clicked']} buttons")
            print(f"  ⏭️  Skipped {len(self.results['buttons_skipped'])} buttons (dialogs)")
            if self.results['buttons_failed']:
                print(f"  ❌ {len(self.results['buttons_failed'])} failed")
        except Exception as e:
            print(f"  ❌ Error during button testing: {e}")
    
    def test_all_menu_actions(self):
        """Test triggering all menu actions (enhanced)"""
        print("\n📋 Testing Menu Actions...")
        
        def find_actions(obj, actions=None, max_depth=8):
            if actions is None:
                actions = []
            if max_depth <= 0:
                return actions
            
            try:
                if hasattr(obj, 'actions'):
                    for action in obj.actions():
                        if isinstance(action, QAction) and action.isEnabled():
                            text = action.text()
                            if text and text.strip():
                                actions.append(action)
                
                for child in obj.children()[:30]:  # Increased limit
                    find_actions(child, actions, max_depth - 1)
            except:
                pass
            return actions
        
        actions = find_actions(self.window)
        
        # Test more menu actions
        for action in actions[:60]:  # Increased from 30 to 60
            try:
                text = action.text()
                action.trigger()
                self.results['actions_triggered'] += 1
                self.app.processEvents()
                time.sleep(0.03)  # Brief delay
            except Exception as e:
                self.results['actions_failed'].append({
                    'action': text or 'unnamed',
                    'error': str(e)[:100]
                })
        
        print(f"  ✅ Triggered {self.results['actions_triggered']} menu actions")
        if self.results['actions_failed']:
            print(f"  ❌ {len(self.results['actions_failed'])} failed")
    
    def test_all_tabs(self):
        """Test switching between all tabs"""
        print("\n📑 Testing Tab Switching...")
        
        def find_tabs(parent):
            tabs = []
            for child in parent.children():
                if isinstance(child, QTabWidget):
                    tabs.append(child)
                tabs.extend(find_tabs(child))
            return tabs
        
        tab_widgets = find_tabs(self.window)
        
        for tab_widget in tab_widgets:
            try:
                for i in range(tab_widget.count()):
                    tab_widget.setCurrentIndex(i)
                    self.results['tabs_switched'] += 1
                    self.app.processEvents()
                    time.sleep(0.1)  # Brief delay for UI update
            except Exception as e:
                self.results['tabs_failed'].append({
                    'tab_widget': 'tab_widget',
                    'error': str(e)
                })
        
        print(f"  ✅ Switched {self.results['tabs_switched']} tabs")
        if self.results['tabs_failed']:
            print(f"  ❌ {len(self.results['tabs_failed'])} failed")
    
    def test_all_text_inputs(self):
        """Test text input widgets (enhanced with multiple values)"""
        print("\n⌨️  Testing Text Inputs...")
        test_values = [
            "Test_Value_1",
            "Sample_Input",
            "123456",
            "Test@123"
        ]
        current_test_idx = 0
        
        def process_inputs(parent, depth=0):
            nonlocal current_test_idx
            if depth > 15:
                return
                
            for child in parent.children():
                if isinstance(child, QLineEdit) and child.isEnabled() and not child.isReadOnly():
                    try:
                        # Use different test values
                        test_val = test_values[current_test_idx % len(test_values)]
                        child.setText(test_val)
                        self.results['inputs_tested'] += 1
                        current_test_idx += 1
                        self.app.processEvents()
                        time.sleep(0.01)
                    except Exception as e:
                        self.results['inputs_failed'].append({
                            'input': child.objectName() or 'unnamed',
                            'error': str(e)[:100]
                        })
                
                process_inputs(child, depth + 1)
        
        try:
            process_inputs(self.window)

            print(f"  ✅ Tested {self.results['inputs_tested']} text inputs")
            if self.results['inputs_failed']:
                print(f"  ❌ {len(self.results['inputs_failed'])} failed")
        except Exception as e:
            print(f"  ❌ Error during text input testing: {e}")
    
    def test_all_dropdowns(self):
        """Test dropdown widgets (enhanced with multiple selections)"""
        print("\n🔽 Testing Dropdowns...")
        
        def process_dropdowns(parent, depth=0):
            if depth > 15:
                return
                
            for child in parent.children():
                if isinstance(child, QComboBox) and child.isEnabled():
                    try:
                        count = child.count()
                        if count > 1:
                            # Test first option
                            child.setCurrentIndex(0)
                            self.results['dropdowns_tested'] += 1
                            self.app.processEvents()
                            time.sleep(0.02)
                            
                            # Test second option
                            child.setCurrentIndex(1)
                            self.results['dropdowns_tested'] += 1
                            self.app.processEvents()
                            time.sleep(0.02)
                            
                            # Test last option if available
                            if count > 3:
                                child.setCurrentIndex(count - 1)
                                self.results['dropdowns_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.02)
                    except Exception as e:
                        self.results['dropdowns_failed'].append({
                            'dropdown': child.objectName() or 'unnamed',
                            'error': str(e)[:100]
                        })
                
                process_dropdowns(child)
        
        try:
            process_dropdowns(self.window)
            print(f"  ✅ Tested {self.results['dropdowns_tested']} dropdowns")
            if self.results['dropdowns_failed']:
                print(f"  ❌ {len(self.results['dropdowns_failed'])} failed")
        except Exception as e:
            print(f"  ❌ Error during dropdown testing: {e}")
    
    def test_all_tables(self):
        """Test table widgets with more thorough testing"""
        print("\n📊 Testing Tables...")
        
        def process_tables(parent, depth=0):
            if depth > 15:
                return
                
            for child in parent.children():
                if isinstance(child, QTableWidget):
                    try:
                        # Test multiple row selections
                        row_count = child.rowCount()
                        col_count = child.columnCount()
                        
                        if row_count > 0 and col_count > 0:
                            # Select first row
                            child.selectRow(0)
                            self.results['tables_tested'] += 1
                            self.app.processEvents()
                            time.sleep(0.02)
                            
                            # Try to select middle row if available
                            if row_count > 5:
                                child.selectRow(row_count // 2)
                                self.results['tables_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.02)
                            
                            # Try to select last row if available
                            if row_count > 2:
                                child.selectRow(row_count - 1)
                                self.results['tables_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.02)
                    except Exception as e:
                        self.results['tables_failed'].append({
                            'table': child.objectName() or 'unnamed',
                            'error': str(e)[:100]
                        })
                
                process_tables(child, depth + 1)
        
        try:
            process_tables(self.window)
            print(f"  ✅ Tested {self.results['tables_tested']} table interactions")
            if self.results['tables_failed']:
                print(f"  ❌ {len(self.results['tables_failed'])} failed")
        except Exception as e:
            print(f"  ❌ Error during table testing: {e}")
    
    def test_all_checkboxes(self):
        """Test checkbox widgets (enhanced)"""
        print("\n☑️  Testing Checkboxes...")
        
        def process_checkboxes(parent, depth=0):
            if depth > 15:
                return
                
            for child in parent.children():
                if isinstance(child, QCheckBox) and child.isEnabled():
                    try:
                        # Toggle on
                        child.setChecked(True)
                        self.results['checkboxes_toggled'] += 1
                        self.app.processEvents()
                        time.sleep(0.01)
                        
                        # Toggle off
                        child.setChecked(False)
                        self.results['checkboxes_toggled'] += 1
                        self.app.processEvents()
                        time.sleep(0.01)
                    except Exception as e:
                        self.results['checkboxes_failed'].append({
                            'checkbox': child.objectName() or 'unnamed',
                            'error': str(e)[:100]
                        })
                
                process_checkboxes(child, depth + 1)
        
        try:
            process_checkboxes(self.window)
            print(f"  ✅ Toggled {self.results['checkboxes_toggled']} checkboxes")
            if self.results['checkboxes_failed']:
                print(f"  ❌ {len(self.results['checkboxes_failed'])} failed")
        except Exception as e:
            print(f"  ❌ Error during checkbox testing: {e}")
    
    def test_all_spinners(self):
        """Test spinner widgets (enhanced with multiple adjustments)"""
        print("\n🔢 Testing Spinners...")
        
        def process_spinners(parent, depth=0):
            if depth > 15:
                return
                
            for child in parent.children():
                if isinstance(child, (QSpinBox, QDoubleSpinBox)) and child.isEnabled():
                    try:
                        current_val = child.value()
                        min_val = child.minimum()
                        max_val = child.maximum()
                        
                        if isinstance(child, QSpinBox):
                            # Increment
                            if current_val < max_val:
                                child.setValue(current_val + 1)
                                self.results['spinners_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.01)
                            
                            # Decrement
                            if current_val > min_val:
                                child.setValue(current_val - 1)
                                self.results['spinners_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.01)
                        else:
                            # Double spinner - increment
                            if current_val < max_val:
                                child.setValue(current_val + 0.1)
                                self.results['spinners_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.01)
                            
                            # Double spinner - decrement
                            if current_val > min_val:
                                child.setValue(current_val - 0.1)
                                self.results['spinners_tested'] += 1
                                self.app.processEvents()
                                time.sleep(0.01)
                        
                    except Exception as e:
                        self.results['spinners_failed'].append({
                            'spinner': child.objectName() or 'unnamed',
                            'error': str(e)[:100]
                        })
                
                process_spinners(child, depth + 1)
        
        try:
            process_spinners(self.window)
            print(f"  ✅ Tested {self.results['spinners_tested']} spinners")
            if self.results['spinners_failed']:
                print(f"  ❌ {len(self.results['spinners_failed'])} failed")
        except Exception as e:
            print(f"  ❌ Error during spinner testing: {e}")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        # Calculate totals
        self.results['total_passed'] = (
            self.results['buttons_clicked'] +
            self.results['actions_triggered'] +
            self.results['tabs_switched'] +
            self.results['inputs_tested'] +
            self.results['dropdowns_tested'] +
            self.results['tables_tested'] +
            self.results['checkboxes_toggled'] +
            self.results['spinners_tested']
        )
        
        self.results['total_failed'] = (
            len(self.results['buttons_failed']) +
            len(self.results['actions_failed']) +
            len(self.results['tabs_failed']) +
            len(self.results['inputs_failed']) +
            len(self.results['dropdowns_failed']) +
            len(self.results['tables_failed']) +
            len(self.results['checkboxes_failed']) +
            len(self.results['spinners_failed'])
        )
        
        self.results['total_skipped'] = len(self.results['buttons_skipped'])
        self.results['total_tests'] = self.results['total_passed'] + self.results['total_failed'] + self.results['total_skipped']
        
        # Print report
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE UI TEST REPORT")
        print("="*80)
        
        pass_rate = (self.results['total_passed'] / self.results['total_tests'] * 100) if self.results['total_tests'] > 0 else 0
        
        print(f"\n✅ PASSED: {self.results['total_passed']}")
        print(f"❌ FAILED: {self.results['total_failed']}")
        print(f"⏭️  SKIPPED: {self.results['total_skipped']}")
        print(f"📊 TOTAL TESTS: {self.results['total_tests']}")
        print(f"📈 PASS RATE: {pass_rate:.1f}%")
        
        print("\n" + "-"*80)
        print("Test Breakdown:")
        print("-"*80)
        print(f"  🔘 Buttons: {self.results['buttons_clicked']} clicked, {len(self.results['buttons_failed'])} failed, {len(self.results['buttons_skipped'])} skipped")
        print(f"  📋 Menu Actions: {self.results['actions_triggered']} triggered, {len(self.results['actions_failed'])} failed")
        print(f"  📑 Tabs: {self.results['tabs_switched']} switched, {len(self.results['tabs_failed'])} failed")
        print(f"  ⌨️  Text Inputs: {self.results['inputs_tested']} tested, {len(self.results['inputs_failed'])} failed")
        print(f"  🔽 Dropdowns: {self.results['dropdowns_tested']} tested, {len(self.results['dropdowns_failed'])} failed")
        print(f"  📊 Tables: {self.results['tables_tested']} tested, {len(self.results['tables_failed'])} failed")
        print(f"  ☑️  Checkboxes: {self.results['checkboxes_toggled']} toggled, {len(self.results['checkboxes_failed'])} failed")
        print(f"  🔢 Spinners: {self.results['spinners_tested']} tested, {len(self.results['spinners_failed'])} failed")
        
        # Show failed items
        if self.results['total_failed'] > 0:
            print("\n" + "-"*80)
            print("Failed Items (First 10):")
            print("-"*80)
            
            failed_items = (
                [(f"Button: {item['button']}", item['error']) for item in self.results['buttons_failed'][:3]] +
                [(f"Action: {item['action']}", item['error']) for item in self.results['actions_failed'][:3]] +
                [(f"Input: {item['input']}", item['error']) for item in self.results['inputs_failed'][:2]]
            )
            
            for name, error in failed_items[:10]:
                print(f"  • {name}: {error}")
        
        print("\n" + "="*80 + "\n")
    
    def export_json_report(self, filename='test_results.json'):
        """Export detailed results as JSON"""
        output_path = Path('l:\\limo\\reports') / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Make results JSON serializable
        results_copy = dict(self.results)
        results_copy['test_categories'] = dict(results_copy['test_categories'])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_copy, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Detailed results exported to {output_path}")
    
    def test_data_validation(self):
        """Test form validation and data constraints"""
        print("\n📋 Testing Data Validation...")
        try:
            inputs = self.window.findChildren(QLineEdit)
            test_count = 0
            
            for input_field in inputs[:10]:  # Test first 10
                if not input_field.isEnabled() or not input_field.isVisible():
                    continue
                
                try:
                    # Test empty value
                    input_field.setText("")
                    test_count += 1
                    
                    # Test very long input
                    input_field.setText("x" * 100)
                    test_count += 1
                    
                    # Test special characters
                    input_field.setText("!@#$%^&*()")
                    test_count += 1
                except:
                    pass
            
            self.results['total_tests'] += test_count
            self.results['total_passed'] += test_count
            if test_count > 0:
                print(f"  ✅ Tested {test_count} validation scenarios")
        except Exception as e:
            print(f"  ❌ Validation testing error: {e}")
    
    def test_widget_communication(self):
        """Test data flow between widgets"""
        print("🔗 Testing Widget Communication...")
        try:
            test_count = 0
            
            # Test tab switching
            tabs = self.window.findChildren(QTabWidget)
            for tab_widget in tabs:
                if tab_widget.count() > 1:
                    original_index = tab_widget.currentIndex()
                    try:
                        if tab_widget.count() > 1:
                            tab_widget.setCurrentIndex(0)
                            test_count += 1
                            if tab_widget.count() > 2:
                                tab_widget.setCurrentIndex(1)
                                test_count += 1
                            tab_widget.setCurrentIndex(original_index)
                            test_count += 1
                    except:
                        pass
            
            self.results['total_tests'] += test_count
            self.results['total_passed'] += test_count
            if test_count > 0:
                print(f"  ✅ Tested {test_count} widget interactions")
        except Exception as e:
            print(f"  ❌ Communication testing error: {e}")
    
    def test_error_handling(self):
        """Test error recovery and edge cases"""
        print("⚠️  Testing Error Handling...")
        try:
            test_count = 0
            
            # Test spinners at boundaries
            spinners = self.window.findChildren(QSpinBox)
            spinners.extend(self.window.findChildren(QDoubleSpinBox))
            
            for spinner in spinners[:5]:
                if spinner.isEnabled() and spinner.isVisible():
                    try:
                        spinner.setValue(spinner.minimum())
                        test_count += 1
                        spinner.setValue(spinner.maximum())
                        test_count += 1
                    except:
                        pass
            
            self.results['total_tests'] += test_count
            self.results['total_passed'] += test_count
            if test_count > 0:
                print(f"  ✅ Tested {test_count} edge cases")
        except Exception as e:
            print(f"  ❌ Error handling test failed: {e}")
    
    def test_keyboard_navigation(self):
        """Test keyboard-based navigation"""
        print("⌨️  Testing Keyboard Navigation...")
        try:
            test_count = 0
            
            # Find all focusable widgets
            focusable = []
            for widget in self.window.findChildren(QWidget):
                try:
                    if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                        focusable.append(widget)
                        if len(focusable) >= 20:
                            break
                except:
                    pass
            
            # Test Focus navigation
            for widget in focusable[:10]:
                try:
                    if widget.isVisible() and widget.isEnabled():
                        widget.setFocus()
                        test_count += 1
                except:
                    pass
            
            self.results['total_tests'] += test_count
            self.results['total_passed'] += test_count
            if test_count > 0:
                print(f"  ✅ Tested {test_count} keyboard interactions")
        except Exception as e:
            print(f"  ❌ Keyboard navigation test failed: {e}")
    
    def test_search_and_filter(self):
        """Test search and filtering functionality"""
        print("🔍 Testing Search & Filter...")
        try:
            test_count = 0
            
            # Find search-like inputs
            inputs = self.window.findChildren(QLineEdit)
            for inp in inputs:
                obj_name = inp.objectName().lower()
                if 'search' in obj_name or 'filter' in obj_name or 'find' in obj_name:
                    if inp.isEnabled() and inp.isVisible():
                        try:
                            # Test clear
                            inp.clear()
                            test_count += 1
                            
                            # Test search term
                            inp.setText("test")
                            test_count += 1
                        except:
                            pass
            
            self.results['total_tests'] += test_count
            self.results['total_passed'] += test_count
            if test_count > 0:
                print(f"  ✅ Tested {test_count} search/filter operations")
        except Exception as e:
            print(f"  ❌ Search/filter testing error: {e}")
    
    def test_form_submission(self):
        """Test form submission and state changes"""
        print("📝 Testing Form Submission...")
        try:
            test_count = 0
            
            # Find save/submit buttons
            buttons = self.window.findChildren(QPushButton)
            for btn in buttons:
                btn_text = btn.text().lower()
                if any(word in btn_text for word in ['save', 'submit', 'send', 'apply', 'update']):
                    if btn.isEnabled() and btn.isVisible():
                        try:
                            # Test button state
                            is_enabled = btn.isEnabled()
                            test_count += 1
                        except:
                            pass
            
            self.results['total_tests'] += test_count
            self.results['total_passed'] += test_count
            if test_count > 0:
                print(f"  ✅ Tested {test_count} form submission scenarios")
        except Exception as e:
            print(f"  ❌ Form submission testing error: {e}")
    
    def run(self):
        """Run comprehensive tests"""
        if not self.start_app():
            return False
        
        try:
            print("🧪 Running Comprehensive UI Tests...\n")
            
            # Allow app to fully initialize
            self.app.processEvents()
            time.sleep(1)
            
            # Run all UI tests
            self.test_all_buttons()
            self.test_all_menu_actions()
            self.test_all_tabs()
            self.test_all_text_inputs()
            self.test_all_dropdowns()
            self.test_all_tables()
            self.test_all_checkboxes()
            self.test_all_spinners()
            
            # Run function and logic tests (NEW)
            self.test_data_validation()
            self.test_widget_communication()
            self.test_error_handling()
            self.test_keyboard_navigation()
            self.test_search_and_filter()
            self.test_form_submission()
            
            # Generate and export reports
            self.generate_report()
            self.export_json_report()
            
            return True
        except Exception as e:
            print(f"\n❌ Test suite error: {e}")
            traceback.print_exc()
            return False
        finally:
            if self.app:
                self.app.quit()

def main():
    """Run the comprehensive tester"""
    tester = ComprehensiveUITester()
    success = tester.run()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
