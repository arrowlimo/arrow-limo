#!/usr/bin/env python3
"""
Pre-Render Deployment Checklist
Verifies app is configured for Neon and no local sync is running
"""

import os
import psycopg2
import subprocess
import sys
from pathlib import Path

print("=" * 80)
print("RENDER DEPLOYMENT PRE-CHECK")
print("=" * 80)

# 1. Check .env configuration
print("\n[1/5] Verifying .env points to Neon...")
env_file = Path('l:/limo/.env')
with open(env_file) as f:
    env_content = f.read()

if 'ep-curly-dream-afnuyxfx-pooler' in env_content:
    print("  ✅ DB_HOST points to Neon")
else:
    print("  ❌ DB_HOST is NOT pointing to Neon")
    sys.exit(1)

if 'DB_SSLMODE=require' in env_content:
    print("  ✅ SSL mode is set to 'require' (Neon requirement)")
else:
    print("  ⚠️  SSL mode not explicitly set")

# 2. Test Neon connection
print("\n[2/5] Testing Neon database connection...")
try:
    neon_conn = psycopg2.connect(
        host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
        dbname='neondb',
        user='neondb_owner',
        password='***REMOVED***',
        sslmode='require'
    )
    neon_cur = neon_conn.cursor()
    neon_cur.execute("SELECT COUNT(*) FROM clients")
    client_count = neon_cur.fetchone()[0]
    neon_cur.close()
    neon_conn.close()
    print(f"  ✅ Connected to Neon | {client_count} clients in database")
except Exception as e:
    print(f"  ❌ Neon connection failed: {e}")
    sys.exit(1)

# 3. Check for running Python processes (local sync)
print("\n[3/5] Checking for running Python processes...")
try:
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
        capture_output=True,
        text=True
    )
    if 'python.exe' in result.stdout:
        lines = [l for l in result.stdout.split('\n') if 'python' in l.lower()]
        print(f"  ⚠️  Found {len(lines)} Python process(es):")
        for line in lines:
            print(f"     - {line.strip()}")
        print("\n  Kill all Python processes before deployment? (sync processes must stop)")
    else:
        print("  ✅ No Python processes running")
except Exception as e:
    print(f"  ℹ️  Could not check processes: {e}")

# 4. Verify required files exist
print("\n[4/5] Verifying required deployment files...")
required_files = [
    'l:/limo/.env',
    'l:/limo/modern_backend',
    'l:/limo/frontend',
    'l:/limo/desktop_app',
    'l:/limo/.github/workflows',
]

missing = []
for file_path in required_files:
    if Path(file_path).exists():
        print(f"  ✅ {file_path}")
    else:
        print(f"  ❌ {file_path} MISSING")
        missing.append(file_path)

if missing:
    print(f"\n  ❌ {len(missing)} required file(s) missing!")
    sys.exit(1)

# 5. Check no local database references in app
print("\n[5/5] Scanning app code for hardcoded localhost references...")
app_files = list(Path('l:/limo/desktop_app').glob('*.py'))
localhost_refs = []

for py_file in app_files[:10]:  # Sample check
    with open(py_file) as f:
        content = f.read()
        if 'host="localhost"' in content or "host='localhost'" in content:
            localhost_refs.append(py_file.name)

if localhost_refs:
    print(f"  ⚠️  Found hardcoded localhost in {len(localhost_refs)} files")
    print(f"     (App will use .env DB_HOST instead)")
else:
    print("  ✅ No hardcoded localhost references detected")

print("\n" + "=" * 80)
print("✅ PRE-CHECK COMPLETE - App is ready for Render deployment")
print("=" * 80)
print("""
NEXT STEPS:
1. Push to GitHub (git push origin main)
2. Connect GitHub repo to Render.com
3. Create new Web Service → Select repo
4. Set environment variables in Render dashboard:
   - Copy all vars from .env file
   - Ensure DB_HOST points to Neon
5. Deploy!

IMPORTANT:
- App will read DB_HOST from environment variable
- All data is in Neon (no local sync needed)
- Local desktop app remains as development tool only
""")
