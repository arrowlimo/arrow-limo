#!/usr/bin/env python3
"""
Quick Render Deployment Status & Health Check
Verifies everything is ready for production
"""

import os
import sys
from pathlib import Path
import psycopg2

def check_deployment():
    print("\n" + "=" * 80)
    print("RENDER DEPLOYMENT HEALTH CHECK")
    print("=" * 80 + "\n")
    
    checks_passed = 0
    checks_total = 0
    
    # 1. Check .env configuration
    checks_total += 1
    print("[1] Environment Configuration")
    env_file = Path('l:/limo/.env')
    if env_file.exists():
        with open(env_file) as f:
            content = f.read()
        if 'ep-curly-dream-afnuyxfx-pooler' in content and 'sslmode=require' in content.lower():
            print("  ✅ .env configured for Neon production")
            checks_passed += 1
        else:
            print("  ❌ .env NOT pointing to Neon")
    else:
        print("  ❌ .env file missing")
    
    # 2. Check Neon connectivity
    checks_total += 1
    print("\n[2] Neon Database Connection")
    try:
        conn = psycopg2.connect(
            host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
            dbname='neondb',
            user='neondb_owner',
            password='***REMOVED***',
            sslmode='require'
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM clients")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"  ✅ Connected to Neon | {count:,} clients in database")
        checks_passed += 1
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
    
    # 3. Check required files
    checks_total += 1
    print("\n[3] Required Deployment Files")
    required = {
        'modern_backend': 'FastAPI Backend',
        'frontend': 'React Frontend',
        'render.yaml': 'Render Configuration',
        'requirements.txt': 'Python Dependencies',
        '.github': 'GitHub Workflows',
    }
    
    all_exist = True
    for name, desc in required.items():
        path = Path(f'l:/limo/{name}')
        if path.exists():
            print(f"  ✅ {desc} ({name})")
        else:
            print(f"  ❌ {name} MISSING")
            all_exist = False
    
    if all_exist:
        checks_passed += 1
    
    # 4. Check git status
    checks_total += 1
    print("\n[4] Git Repository Status")
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'log', '--oneline', '-1'],
            cwd='l:/limo',
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            commit = result.stdout.strip().split()[0]
            print(f"  ✅ Latest commit: {commit}")
            checks_passed += 1
        else:
            print(f"  ❌ Git error: {result.stderr}")
    except Exception as e:
        print(f"  ⚠️  Could not check git: {e}")
    
    # 5. Check for unwanted files
    checks_total += 1
    print("\n[5] Root Directory Cleanup")
    unwanted_patterns = ['*.dump', '*.sql', 'test_*.py', '*_test.py']
    root = Path('l:/limo')
    unwanted = []
    for pattern in unwanted_patterns:
        unwanted.extend(root.glob(pattern))
    
    if len(unwanted) == 0:
        print("  ✅ No test/backup files in root")
        checks_passed += 1
    else:
        print(f"  ⚠️  Found {len(unwanted)} unwanted files:")
        for f in unwanted[:5]:
            print(f"     - {f.name}")
    
    # Summary
    print("\n" + "=" * 80)
    print(f"HEALTH CHECK: {checks_passed}/{checks_total} checks passed")
    
    if checks_passed == checks_total:
        print("\n✅ APP IS READY FOR RENDER DEPLOYMENT")
        print("\nNext steps:")
        print("1. Go to https://render.com/dashboard")
        print("2. Click 'New +' → 'Web Service'")
        print("3. Connect GitHub repo (arrow-limousine)")
        print("4. Set environment variables from .env file")
        print("5. Deploy!")
    else:
        print(f"\n⚠️  {checks_total - checks_passed} issue(s) need to be fixed")
        return 1
    
    print("=" * 80 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(check_deployment())
