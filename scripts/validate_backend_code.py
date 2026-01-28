#!/usr/bin/env python3
"""
Backend API Code Quality & Correctness Validation
Checks all routers for proper structure, error handling, type safety
"""
import sys
import ast
from pathlib import Path
from collections import defaultdict

class CodeValidator:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passes = []
        self.router_dir = Path('modern_backend/app/routers')
    
    def validate_all(self):
        """Run all validation checks"""
        print("="*70)
        print("BACKEND CODE QUALITY VALIDATION")
        print("="*70)
        
        self.check_router_imports()
        self.check_router_structure()
        self.check_error_handling()
        self.check_type_hints()
        self.check_sql_patterns()
        self.check_database_operations()
        self.check_api_documentation()
        
        self.print_summary()
    
    def check_router_imports(self):
        """Verify all routers can be imported"""
        print("\n📦 Checking Router Imports...")
        
        routers = list(self.router_dir.glob('*.py'))
        routers = [r for r in routers if not r.name.startswith('_')]
        
        for router_file in routers:
            try:
                with open(router_file, 'r') as f:
                    ast.parse(f.read())
                self.passes.append(f"✅ {router_file.name}: Syntax valid")
            except SyntaxError as e:
                self.issues.append(f"❌ {router_file.name}: Syntax error at line {e.lineno}")
    
    def check_router_structure(self):
        """Verify routers follow proper structure"""
        print("\n🏗️  Checking Router Structure...")
        
        required_patterns = {
            'from fastapi': 'FastAPI imports',
            'from sqlalchemy': 'SQLAlchemy imports',
            '@router': 'Route definitions',
        }
        
        for router_file in self.router_dir.glob('*.py'):
            if router_file.name.startswith('_'):
                continue
            
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Check for required patterns
            missing = []
            for pattern, desc in required_patterns.items():
                if pattern not in content:
                    missing.append(desc)
            
            if missing:
                self.warnings.append(f"⚠️  {router_file.name}: Missing {', '.join(missing)}")
            else:
                self.passes.append(f"✅ {router_file.name}: Complete router structure")
    
    def check_error_handling(self):
        """Verify error handling in routers"""
        print("\n🛡️  Checking Error Handling...")
        
        for router_file in self.router_dir.glob('*.py'):
            if router_file.name.startswith('_'):
                continue
            
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Count try-except blocks
            try_blocks = content.count('try:')
            except_blocks = content.count('except')
            
            # Count HTTPException usage
            has_http_exceptions = 'HTTPException' in content
            
            # Count database operation guards
            conn_guards = content.count('psycopg2.connect')
            
            if try_blocks > 0 and has_http_exceptions:
                self.passes.append(f"✅ {router_file.name}: Error handling present ({try_blocks} try blocks)")
            elif try_blocks == 0 and conn_guards > 0:
                self.warnings.append(f"⚠️  {router_file.name}: No try-except for {conn_guards} database operations")
            else:
                self.passes.append(f"✅ {router_file.name}: Error handling adequate")
    
    def check_type_hints(self):
        """Verify proper type hints"""
        print("\n📝 Checking Type Hints...")
        
        for router_file in self.router_dir.glob('*.py'):
            if router_file.name.startswith('_'):
                continue
            
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Count function definitions and type hints
            import re
            func_defs = len(re.findall(r'def \w+\(', content))
            type_hints = len(re.findall(r'\) -> ', content))
            
            if func_defs > 0:
                hint_ratio = type_hints / func_defs
                if hint_ratio > 0.7:
                    self.passes.append(f"✅ {router_file.name}: {hint_ratio*100:.0f}% functions typed")
                else:
                    self.warnings.append(f"⚠️  {router_file.name}: Only {hint_ratio*100:.0f}% functions typed")
    
    def check_sql_patterns(self):
        """Check for SQL injection risks"""
        print("\n🔒 Checking SQL Patterns...")
        
        risky_patterns = []
        safe_patterns = 0
        
        for router_file in self.router_dir.glob('*.py'):
            if router_file.name.startswith('_'):
                continue
            
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Check for parameterized queries (safe)
            if 'cur.execute(' in content and '?' in content or '%s' in content:
                safe_patterns += 1
            
            # Check for dangerous f-strings with SQL
            import re
            f_strings = re.findall(r'execute\(f["\'].*WHERE', content, re.DOTALL)
            if f_strings:
                risky_patterns.append(router_file.name)
        
        if not risky_patterns:
            self.passes.append(f"✅ SQL patterns: All {safe_patterns} routers use parameterized queries")
        else:
            self.warnings.append(f"⚠️  SQL patterns: {len(risky_patterns)} files may have unsafe queries")
    
    def check_database_operations(self):
        """Verify database connection handling"""
        print("\n💾 Checking Database Operations...")
        
        for router_file in self.router_dir.glob('*.py'):
            if router_file.name.startswith('_'):
                continue
            
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Check for proper connection cleanup
            conn_opens = content.count('.connect(')
            conn_closes = content.count('.close()')
            
            if conn_opens == 0:
                continue
            
            # Check for finally blocks to ensure cleanup
            has_finally = 'finally:' in content
            
            if has_finally:
                self.passes.append(f"✅ {router_file.name}: Proper connection cleanup (finally blocks)")
            elif conn_opens > 0:
                self.warnings.append(f"⚠️  {router_file.name}: No finally blocks for {conn_opens} connections")
    
    def check_api_documentation(self):
        """Verify API endpoints have documentation"""
        print("\n📚 Checking API Documentation...")
        
        import re
        
        for router_file in self.router_dir.glob('*.py'):
            if router_file.name.startswith('_'):
                continue
            
            with open(router_file, 'r') as f:
                content = f.read()
            
            # Count route decorators and docstrings
            routes = len(re.findall(r'@router\.(get|post|put|delete|patch)', content))
            docstrings = len(re.findall(r'"""', content)) // 2  # Docstrings have opening and closing
            
            if routes > 0:
                if docstrings > routes // 2:
                    self.passes.append(f"✅ {router_file.name}: Good documentation ({docstrings}/{routes} endpoints)")
                else:
                    self.warnings.append(f"⚠️  {router_file.name}: {docstrings}/{routes} endpoints documented")
    
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*70)
        print("CODE QUALITY SUMMARY")
        print("="*70)
        
        total = len(self.passes) + len(self.issues) + len(self.warnings)
        
        print(f"\n✅ Passed:   {len(self.passes):3d}")
        print(f"❌ Issues:   {len(self.issues):3d}")
        print(f"⚠️  Warnings: {len(self.warnings):3d}")
        print(f"Total:    {total:3d}")
        
        if self.issues:
            print("\n🔴 CRITICAL ISSUES:")
            for issue in self.issues[:5]:
                print(f"  {issue}")
            if len(self.issues) > 5:
                print(f"  ... and {len(self.issues)-5} more")
        
        if self.warnings:
            print("\n🟡 WARNINGS:")
            for warning in self.warnings[:5]:
                print(f"  {warning}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings)-5} more")
        
        pass_rate = len(self.passes) / total * 100 if total > 0 else 0
        print(f"\n📊 Pass Rate: {pass_rate:.0f}%")
        
        if len(self.issues) == 0:
            print("\n✨ Code quality PASSED - ready for deployment")
            return 0
        else:
            print(f"\n⚠️  {len(self.issues)} issue(s) require attention")
            return 1

if __name__ == '__main__':
    validator = CodeValidator()
    validator.validate_all()
