#!/usr/bin/env python3
"""
Automated Code Violation Fixer for Arrow Limousine Management System

Fixes:
1. charter_id used for business logic → use reserve_number instead
2. Currency stored as strings → use DECIMAL in queries (display code unchanged)

Usage:
    python fix_code_violations_automated.py --dry-run
    python fix_code_violations_automated.py --write
    python fix_code_violations_automated.py --write --target scripts/
"""

import os
import re
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Configuration
CRITICAL_DIRS = ['scripts/', 'desktop_app/', 'modern_backend/']
EXCLUDE_DIRS = ['backups/', 'network_share_deployment/', '.venv/', '__pycache__']
EXCLUDE_PATTERNS = ['.dump', '.bak', '.pyc', '__pycache__']

# Violation patterns and fixes
VIOLATIONS = {
    'charter_id_business_logic': {
        'patterns': [
            # Pattern: WHERE charter_id IS NULL/NOT NULL (business logic check)
            (r'WHERE\s+(\w+\.)?charter_id\s+IS\s+(NULL|NOT NULL)', 
             'charter_id IS NULL/NOT NULL in WHERE clause - should use reserve_number for business key matching'),
            
            # Pattern: charter_id = %s or charter_id IS NOT NULL in payment/charge context
            (r'WHERE\s+(\w+\.)?charter_id\s*=\s*%s',
             'charter_id = %s in WHERE clause - use reserve_number for business matching'),
            
            # Pattern: p.reserve_number IS NULL (unmatched payments)
            (r'WHERE\s+p\.charter_id\s+IS\s+NULL',
             'Unmatched payments check using charter_id - should use reserve_number'),
        ],
        'context_safe': [
            # These ARE safe - internal relationships
            'LEFT JOIN', 'INNER JOIN', 'ON',  # Join conditions
            'SELECT',  # Reading from database
        ],
        'unsafe_contexts': [
            'INSERT', 'UPDATE', 'DELETE',  # Modification operations (check more carefully)
        ]
    },
    'currency_as_string': {
        'patterns': [
            (r"f\"\${[^}]+:\,.2f}\"", 'Currency formatting with $ sign'),
            (r'\$\{[^}]+\}', 'String interpolation with currency'),
            (r"text\(\)\.replace\('\$', ''\)", 'Stripping $ from text input'),
        ],
        'context_safe': [
            'setPrefix', 'setText', 'format', 'QLabel', 'f-string',  # Display code
        ],
        'action': 'Review - most are display formatting and safe'
    }
}

class ViolationFixer:
    def __init__(self, root_path='L:\\limo', dry_run=True):
        self.root_path = Path(root_path)
        self.dry_run = dry_run
        self.fixes_applied = defaultdict(list)
        self.violations_found = defaultdict(list)
        self.backups_created = []
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def should_process_file(self, file_path):
        """Check if file should be processed"""
        rel_path = str(file_path.relative_to(self.root_path))
        
        # Skip excluded directories
        for exclude_dir in EXCLUDE_DIRS:
            if exclude_dir in rel_path:
                return False
        
        # Skip excluded patterns
        for pattern in EXCLUDE_PATTERNS:
            if pattern in rel_path:
                return False
        
        # Only process Python files
        if not rel_path.endswith('.py'):
            return False
        
        return True
    
    def is_critical_file(self, file_path):
        """Check if file is in critical directories"""
        rel_path = str(file_path.relative_to(self.root_path))
        return any(rel_path.startswith(critical_dir) for critical_dir in CRITICAL_DIRS)
    
    def fix_charter_id_business_logic(self, content, file_path):
        """
        Fix charter_id used for business logic.
        
        Key rules:
        - charter_id in JOINs = OK (relationship)
        - charter_id in WHERE for matching = WRONG (use reserve_number)
        - charter_id in SELECT for reading ID = OK (it's the primary key)
        """
        original = content
        fixes = []
        
        # Pattern 1: WHERE charter_id IS NULL (most common - unmatched records)
        # Must do unaliased first, then aliased
        
        # Unaliased: WHERE charter_id IS NULL
        if re.search(r'WHERE\s+charter_id\s+IS\s+NULL', content, re.IGNORECASE):
            content = re.sub(
                r'WHERE\s+charter_id\s+IS\s+NULL',
                'WHERE reserve_number IS NULL',
                content,
                flags=re.IGNORECASE
            )
            fixes.append('Fixed: WHERE charter_id IS NULL → WHERE reserve_number IS NULL')
        
        # Aliased: WHERE p.charter_id IS NULL  
        if re.search(r'WHERE\s+\w+\.charter_id\s+IS\s+NULL', content, re.IGNORECASE):
            content = re.sub(
                r'WHERE\s+(\w+)\.charter_id\s+IS\s+NULL',
                r'WHERE \1.reserve_number IS NULL',
                content,
                flags=re.IGNORECASE
            )
            fixes.append('Fixed: aliased WHERE x.charter_id IS NULL → WHERE x.reserve_number IS NULL')
        
        # Pattern 2: WHERE charter_id IS NOT NULL
        if re.search(r'WHERE\s+charter_id\s+IS\s+NOT\s+NULL', content, re.IGNORECASE):
            content = re.sub(
                r'WHERE\s+charter_id\s+IS\s+NOT\s+NULL',
                'WHERE reserve_number IS NOT NULL',
                content,
                flags=re.IGNORECASE
            )
            fixes.append('Fixed: WHERE charter_id IS NOT NULL → WHERE reserve_number IS NOT NULL')
        
        # Aliased: WHERE p.charter_id IS NOT NULL
        if re.search(r'WHERE\s+\w+\.charter_id\s+IS\s+NOT\s+NULL', content, re.IGNORECASE):
            content = re.sub(
                r'WHERE\s+(\w+)\.charter_id\s+IS\s+NOT\s+NULL',
                r'WHERE \1.reserve_number IS NOT NULL',
                content,
                flags=re.IGNORECASE
            )
            fixes.append('Fixed: WHERE x.charter_id IS NOT NULL → WHERE x.reserve_number IS NOT NULL')
        
        return content, fixes
    
    def fix_payment_matching_via_reserve(self, content, file_path):
        """
        Fix payment-charter matching to use reserve_number.
        
        Pattern: SELECT ... FROM payments p LEFT JOIN charters c ON p.charter_id = c.charter_id
        Fix: Use p.reserve_number = c.reserve_number instead
        """
        fixes = []
        original = content
        
        # Only fix if this is a data processing/analysis script (not UI code)
        if 'desktop_app' in str(file_path):
            return content, []  # Skip UI code - it's reading data, not matching
        
        # Pattern: JOIN charters c ON p.charter_id = c.charter_id
        # This is a relationship (OK), but business matching should use reserve_number
        pattern = r'ON\s+(\w+)\.charter_id\s*=\s*(\w+)\.charter_id'
        if re.search(pattern, content):
            # Check if we're in a matching/analysis context
            # If looking for unmatched payments, use reserve_number
            if 'charter_id IS NULL' in content or 'charter_id IS NOT NULL' in content:
                content = re.sub(
                    r'p\.charter_id\s+IS\s+NULL',
                    'p.reserve_number IS NULL',
                    content
                )
                fixes.append('Fixed: Payment matching to use reserve_number for business key')
        
        return content, fixes
    
    def process_file(self, file_path):
        """Process a single file for violations"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return False
        
        original_content = content
        all_fixes = []
        file_violations = []
        rel_path = file_path.relative_to(self.root_path)
        
        # Check for charter_id violations
        charter_id_pattern = r'WHERE\s+\w*\.?charter_id\s+IS\s+(NULL|NOT NULL)'
        if re.search(charter_id_pattern, content):
            file_violations.append('charter_id business logic violation detected')
            content, fixes = self.fix_charter_id_business_logic(content, file_path)
            all_fixes.extend(fixes)
        
        # Check for payment matching via charter_id
        if 'payments' in content.lower() and re.search(r'charter_id\s+IS\s+NULL', content):
            file_violations.append('Unmatched payment check via charter_id')
            content, fixes = self.fix_payment_matching_via_reserve(content, file_path)
            all_fixes.extend(fixes)
        
        # If changes made, save or report
        if content != original_content:
            if self.dry_run:
                print(f"✏️  Would fix: {rel_path}")
                for fix in all_fixes:
                    print(f"   └─ {fix}")
                self.fixes_applied[str(rel_path)] = all_fixes
            else:
                # Create backup
                backup_path = file_path.with_suffix(f'.bak_{self.timestamp}.py')
                shutil.copy2(file_path, backup_path)
                self.backups_created.append(str(backup_path))
                
                # Write fixed content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"✅ Fixed: {rel_path}")
                for fix in all_fixes:
                    print(f"   └─ {fix}")
                self.fixes_applied[str(rel_path)] = all_fixes
        
        if file_violations:
            self.violations_found[str(rel_path)] = file_violations
        
        return True
    
    def run_scan(self, target_dir=None):
        """Scan and fix violations"""
        if target_dir:
            scan_root = self.root_path / target_dir
        else:
            scan_root = self.root_path
        
        print(f"\n{'🔍 SCANNING' if self.dry_run else '🔧 FIXING'} Code Violations")
        print(f"Root: {scan_root}")
        print(f"Mode: {'DRY-RUN' if self.dry_run else 'WRITE'}")
        print(f"Timestamp: {self.timestamp}\n")
        
        py_files = list(scan_root.rglob('*.py'))
        processed = 0
        
        for file_path in py_files:
            if self.should_process_file(file_path):
                self.process_file(file_path)
                processed += 1
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Processed: {processed} files")
        print(f"Violations Found: {len(self.violations_found)}")
        print(f"Fixes Applied: {len(self.fixes_applied)}")
        
        if self.fixes_applied:
            print(f"\n{'='*60}")
            print("FIXES TO APPLY:")
            for file_path, fixes in sorted(self.fixes_applied.items()):
                print(f"\n{file_path}:")
                for fix in fixes:
                    print(f"  • {fix}")
        
        if self.backups_created:
            print(f"\n{'='*60}")
            print(f"Backups created: {len(self.backups_created)}")
            for backup in self.backups_created[:5]:
                print(f"  • {backup}")
            if len(self.backups_created) > 5:
                print(f"  ... and {len(self.backups_created) - 5} more")
        
        # Save report
        self.save_report()
    
    def save_report(self):
        """Save detailed report of violations and fixes"""
        report_path = self.root_path / f'reports/code_fixes_report_{self.timestamp}.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            'timestamp': self.timestamp,
            'mode': 'dry-run' if self.dry_run else 'write',
            'violations_found': dict(self.violations_found),
            'fixes_applied': dict(self.fixes_applied),
            'backups_created': self.backups_created,
            'stats': {
                'total_violations': len(self.violations_found),
                'total_fixes': len(self.fixes_applied),
                'total_backups': len(self.backups_created),
            }
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📋 Report saved: {report_path}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix code violations automatically')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be fixed without making changes')
    parser.add_argument('--write', action='store_true',
                       help='Actually apply the fixes')
    parser.add_argument('--target', default=None,
                       help='Target specific directory (e.g., scripts/)')
    
    args = parser.parse_args()
    
    if args.write:
        response = input("\n⚠️  WARNING: This will modify Python files. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        dry_run = False
    else:
        dry_run = True
    
    fixer = ViolationFixer(dry_run=dry_run)
    fixer.run_scan(target_dir=args.target)

if __name__ == '__main__':
    main()
