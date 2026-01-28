#!/usr/bin/env python3
"""
Dump local almsdata to Neon via subprocess (no pg_dump PATH required).
Falls back to pure SQL export if subprocess fails.
"""

import subprocess
import sys
import os

def dump_via_subprocess():
    """Try pg_dump via full path search."""
    pg_paths = [
        r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
    ]
    
    for pg_path in pg_paths:
        if os.path.exists(pg_path):
            print(f"✅ Found pg_dump at: {pg_path}")
            cmd = [
                pg_path,
                "-h", "localhost",
                "-U", "postgres",
                "-d", "almsdata",
                "-F", "c",
                "-f", "almsdata_pg17.dump"
            ]
            try:
                print(f"⏳ Dumping almsdata...")
                result = subprocess.run(cmd, cwd="L:\\limo", capture_output=True, text=True, timeout=600)
                if result.returncode == 0:
                    dump_file = "L:\\limo\\almsdata_pg17.dump"
                    size_mb = os.path.getsize(dump_file) / (1024 * 1024)
                    print(f"✅ Dump complete: {size_mb:.2f} MB")
                    return True
                else:
                    print(f"❌ pg_dump failed: {result.stderr}")
                    return False
            except Exception as e:
                print(f"❌ Subprocess error: {e}")
                return False
    
    print("❌ No pg_dump found in standard paths")
    return False

if __name__ == "__main__":
    success = dump_via_subprocess()
    sys.exit(0 if success else 1)
