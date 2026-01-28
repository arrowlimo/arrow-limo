#!/usr/bin/env python3
"""
Check if invoice data exists in recent backups
"""
import subprocess
import os
import tempfile

# List of recent backup files to check (in order of recency)
backups = [
    'L:\\limo\\almsdata_sync_to_neon_20260121_142047.dump',
    'L:\\limo\\almsdata_AFTER_LMS_BACKFILL_20260121_141552.dump',
    'L:\\limo\\almsdata_FROM_NEON_20260121_012851.dump',
]

print("Checking backups for invoices table data...")
print("="*70)

for backup_file in backups:
    if not os.path.exists(backup_file):
        print(f"⚠️  File not found: {backup_file}")
        continue
    
    backup_name = os.path.basename(backup_file)
    file_size_mb = os.path.getsize(backup_file) / (1024*1024)
    print(f"\n📦 {backup_name} ({file_size_mb:.1f} MB)")
    
    # Try to extract invoices table using pg_restore
    # Use a temp file to capture output
    try:
        # Use pg_restore to list tables in the dump
        result = subprocess.run(
            ['pg_restore', '--list', backup_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Search for invoices-related entries
            lines = result.stdout.split('\n')
            invoices_lines = [l for l in lines if 'invoices' in l.lower()]
            
            if invoices_lines:
                print(f"   ✅ Found {len(invoices_lines)} invoices-related objects:")
                for line in invoices_lines[:10]:  # Show first 10
                    print(f"      - {line.strip()}")
            else:
                print(f"   ❌ No invoices table found")
        else:
            print(f"   ⚠️  pg_restore failed: {result.stderr[:100]}")
    except FileNotFoundError:
        print(f"   ⚠️  pg_restore not found in PATH")
        break
    except subprocess.TimeoutExpired:
        print(f"   ⚠️  Timeout reading backup")

print("\n" + "="*70)
print("\nTo restore a backup if needed:")
print("  pg_restore -h localhost -U postgres -d almsdata -F c 'L:\\limo\\<backup_name>.dump'")
