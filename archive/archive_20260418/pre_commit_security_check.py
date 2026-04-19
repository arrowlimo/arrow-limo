#!/usr/bin/env python3
"""
Pre-commit security check - Prevents accidental password file commits
Run this before pushing to verify no sensitive files will be committed
"""

import subprocess
import sys
import os
from pathlib import Path

# Sensitive files that should NEVER be committed
SENSITIVE_PATTERNS = [
    '.env',
    'setup_alms_user.py',
    'setup_alms_user.sql',
    'passwords.txt',
    'check_matt_password.py',
]

def check_staged_files():
    """Check if any sensitive files are staged for commit"""
    
    try:
        # Get list of staged files
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        staged_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        print("🔐 PRE-COMMIT SECURITY CHECK")
        print("=" * 60)
        
        if not staged_files or staged_files == ['']:
            print("ℹ️  No files staged for commit")
            return True
        
        print(f"📋 Checking {len(staged_files)} staged files...\n")
        
        risky_files = []
        
        for staged_file in staged_files:
            if not staged_file.strip():
                continue
            
            print(f"   Checking: {staged_file}", end=" ")
            
            # Check if file matches any sensitive pattern
            is_risky = False
            for pattern in SENSITIVE_PATTERNS:
                if pattern in staged_file.lower():
                    is_risky = True
                    risky_files.append(staged_file)
                    print("❌ SENSITIVE FILE DETECTED")
                    break
            
            if not is_risky:
                print("✅ OK")
        
        print("\n" + "=" * 60)
        
        if risky_files:
            print(f"\n🚨 SECURITY WARNING: {len(risky_files)} sensitive file(s) detected!\n")
            for f in risky_files:
                print(f"   ❌ {f}")
            
            print("\n💡 These files contain passwords and should NOT be committed:")
            print("   - Add them to .gitignore")
            print("   - Run: git reset HEAD <filename>")
            print("   - Verify with: git check-ignore -v <filename>\n")
            
            return False
        
        else:
            print("✅ SECURITY CHECK PASSED")
            print("✅ No sensitive files detected in staged changes")
            print("✅ Safe to commit and push to web services\n")
            return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_gitignore():
    """Verify sensitive files are in .gitignore"""
    
    gitignore_path = Path('.gitignore')
    
    if not gitignore_path.exists():
        print("⚠️  .gitignore not found")
        return False
    
    with open(gitignore_path, 'r') as f:
        gitignore_content = f.read().lower()
    
    missing = []
    for pattern in SENSITIVE_PATTERNS:
        if pattern.lower() not in gitignore_content:
            missing.append(pattern)
    
    if missing:
        print(f"\n⚠️  Missing from .gitignore:")
        for f in missing:
            print(f"   ❌ {f}")
        return False
    
    return True

def main():
    """Run all security checks"""
    
    os.chdir(Path(__file__).parent)
    
    print("\n")
    
    # Check .gitignore
    print("1️⃣  Checking .gitignore configuration...")
    gitignore_ok = check_gitignore()
    if gitignore_ok:
        print("   ✅ All sensitive files are in .gitignore\n")
    else:
        print("   ⚠️  Some files missing from .gitignore\n")
    
    # Check staged files
    print("2️⃣  Checking staged files for commit...")
    staged_ok = check_staged_files()
    
    # Final result
    print("\n" + "=" * 60)
    if gitignore_ok and staged_ok:
        print("🎉 ALL SECURITY CHECKS PASSED")
        print("✅ Safe to commit and push!")
        return 0
    else:
        print("⛔ SECURITY CHECK FAILED")
        print("❌ Do not commit until issues are resolved")
        return 1

if __name__ == '__main__':
    sys.exit(main())
