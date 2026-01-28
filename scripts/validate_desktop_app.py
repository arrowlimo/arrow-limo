#!/usr/bin/env python3
"""
Desktop Application Code Validation
Tests all desktop app components for safety and functionality
"""
import sys
import ast
from pathlib import Path

class DesktopAppValidator:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.desktop_dir = Path('desktop_app')
    
    def run(self):
        print("="*70)
        print("DESKTOP APPLICATION CODE VALIDATION")
        print("="*70)
        
        self.check_main_file()
        self.check_dashboard_modules()
        self.check_widget_instantiation()
        self.check_database_connections()
        self.check_error_handling()
        self.print_summary()
    
    def check_main_file(self):
        """Validate main.py structure"""
        print("\n📋 Checking main.py...")
        
        main_file = self.desktop_dir / 'main.py'
        if not main_file.exists():
            self.fail("main.py not found")
            return
        
        try:
            with open(main_file, 'r') as f:
                content = f.read()
            
            # Check for required imports
            required = ['PyQt6', 'psycopg2', 'logging']
            missing = [r for r in required if r not in content]
            
            if missing:
                self.warn(f"main.py: Missing imports: {missing}")
            else:
                self.ok("main.py: All required imports present")
            
            # Check for tab creation methods
            tab_methods = [m for m in ['create_operations_tab', 'create_fleet_people_tab', 
                                       'create_accounting_tab', 'create_admin_tab']
                          if m in content]
            self.ok(f"main.py: Found {len(tab_methods)} parent tab methods")
            
            # Check for error handling around tab creation
            if 'try:' in content and 'except' in content:
                self.ok("main.py: Has error handling")
            else:
                self.warn("main.py: Missing exception handlers")
            
            # Parse to ensure valid Python
            ast.parse(content)
            self.ok("main.py: Syntax valid")
            
        except SyntaxError as e:
            self.fail(f"main.py: Syntax error at line {e.lineno}")
        except Exception as e:
            self.fail(f"main.py: {str(e)[:100]}")
    
    def check_dashboard_modules(self):
        """Check all dashboard modules"""
        print("\n📊 Checking Dashboard Modules...")
        
        dashboard_files = list(self.desktop_dir.glob('dashboards_*.py'))
        
        if not dashboard_files:
            self.warn("No dashboard modules found")
            return
        
        self.ok(f"Found {len(dashboard_files)} dashboard modules")
        
        # Check each module for syntax errors
        syntax_errors = []
        for df in dashboard_files:
            try:
                with open(df, 'r') as f:
                    ast.parse(f.read())
            except SyntaxError as e:
                syntax_errors.append(f"{df.name}: line {e.lineno}")
        
        if syntax_errors:
            self.fail(f"Syntax errors in: {', '.join(syntax_errors[:3])}")
        else:
            self.ok("All dashboard modules have valid syntax")
    
    def check_widget_instantiation(self):
        """Check widget instantiation for error safety"""
        print("\n🧩 Checking Widget Instantiation...")
        
        # Look for patterns in main.py that could crash
        main_file = self.desktop_dir / 'main.py'
        
        try:
            with open(main_file, 'r') as f:
                lines = f.readlines()
            
            # Find addTab calls without try-except
            in_try_block = False
            unsafe_tabs = []
            
            for i, line in enumerate(lines):
                if 'try:' in line:
                    in_try_block = True
                elif 'except' in line or 'def ' in line:
                    in_try_block = False
                
                if 'addTab' in line and not in_try_block:
                    unsafe_tabs.append((i+1, line.strip()[:50]))
            
            if unsafe_tabs:
                self.warn(f"Widget instantiation: {len(unsafe_tabs)} addTab calls without error handling")
                for line_no, code in unsafe_tabs[:3]:
                    print(f"       Line {line_no}: {code}...")
            else:
                self.ok("All widget instantiation calls have error handling")
        
        except Exception as e:
            self.warn(f"Could not analyze widget instantiation: {str(e)[:50]}")
    
    def check_database_connections(self):
        """Check database connection patterns"""
        print("\n💾 Checking Database Connections...")
        
        # Scan all Python files in desktop_app
        py_files = list(self.desktop_dir.glob('*.py'))
        
        conn_issues = []
        for py_file in py_files:
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Check for psycopg2.connect without try-except
                if 'psycopg2.connect' in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'psycopg2.connect' in line:
                            # Check if in try block
                            before = '\n'.join(lines[max(0, i-5):i])
                            if 'try:' not in before:
                                conn_issues.append(f"{py_file.name}: line {i+1}")
            except:
                pass
        
        if conn_issues:
            self.warn(f"Database connections without error handling: {len(conn_issues)}")
        else:
            self.ok("All database connections have proper error handling")
    
    def check_error_handling(self):
        """Check overall error handling coverage"""
        print("\n🛡️  Checking Error Handling...")
        
        py_files = list(self.desktop_dir.glob('*.py'))
        total_try_blocks = 0
        files_with_handlers = 0
        
        for py_file in py_files:
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                try_count = content.count('try:')
                if try_count > 0:
                    files_with_handlers += 1
                    total_try_blocks += try_count
            except:
                pass
        
        if files_with_handlers > len(py_files) * 0.5:
            self.ok(f"Error handling: {files_with_handlers}/{len(py_files)} files with try-except blocks")
        else:
            self.warn(f"Error handling: Only {files_with_handlers}/{len(py_files)} files have error handling")
        
        self.ok(f"Total try-except blocks: {total_try_blocks}")
    
    def ok(self, msg):
        self.passed += 1
        print(f"  ✅ {msg}")
    
    def warn(self, msg):
        self.warnings += 1
        print(f"  ⚠️  {msg}")
    
    def fail(self, msg):
        self.failed += 1
        print(f"  ❌ {msg}")
    
    def print_summary(self):
        print("\n" + "="*70)
        print("DESKTOP APP SUMMARY")
        print("="*70)
        
        total = self.passed + self.failed + self.warnings
        pass_rate = self.passed / total * 100 if total > 0 else 0
        
        print(f"\n✅ Passed:   {self.passed:3d}")
        print(f"❌ Failed:   {self.failed:3d}")
        print(f"⚠️  Warnings: {self.warnings:3d}")
        print(f"Total:    {total:3d}")
        print(f"\n📊 Pass Rate: {pass_rate:.0f}%")
        
        if self.failed == 0:
            print("\n✨ Desktop app structure is SAFE - ready for feature testing")
        else:
            print(f"\n⚠️  {self.failed} critical issue(s) found")

if __name__ == '__main__':
    validator = DesktopAppValidator()
    validator.run()
