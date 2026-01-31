import subprocess
import os

print("=== EXTRACTING PAYMENT DATA FROM OCTOBER BACKUPS ===\n")

# Try the October 17 backup (almsdata_backup.dump)
backup_files = [
    (r'L:\limo\almsdata_backup.dump', 'October 17, 2025'),
    (r'L:\limo\almsdata_backup_20251012.pg_dump', 'October 12, 2025')
]

for backup_file, backup_date in backup_files:
    if not os.path.exists(backup_file):
        print(f"❌ {backup_date} backup not found: {backup_file}")
        continue
    
    print(f"\n{'='*60}")
    print(f"Checking {backup_date} backup")
    print(f"{'='*60}")
    
    # Extract just the payments table schema to see structure
    output_file = f"L:\\limo\\temp_payments_extract_{backup_date.replace(' ', '_').replace(',', '')}.sql"
    
    try:
        # Use pg_restore to extract payments table data
        cmd = [
            'pg_restore',
            '--data-only',
            '--table=payments',
            '--file=' + output_file,
            backup_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Extracted payments data to: {output_file}")
            
            # Count lines with banking_transaction_id
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                copy_lines = [l for l in lines if 'COPY' in l and 'payments' in l]
                if copy_lines:
                    print(f"Found COPY statement: {copy_lines[0][:200]}")
        else:
            print(f"⚠️ pg_restore failed: {result.stderr[:500]}")
            print(f"ℹ️ Trying alternative extraction method...")
            
            # Try pg_dump format
            cmd_alt = [
                'pg_restore',
                '--list',
                backup_file
            ]
            result_alt = subprocess.run(cmd_alt, capture_output=True, text=True)
            if 'payments' in result_alt.stdout:
                print("✅ Backup contains payments table")
            else:
                print("❌ Cannot access backup (may need different tool)")
    
    except FileNotFoundError:
        print("❌ pg_restore not found in PATH")
        print("ℹ️ Need to use psql or custom extraction")
        break
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n=== ALTERNATIVE: Search for SQL backups with INSERT statements ===")
