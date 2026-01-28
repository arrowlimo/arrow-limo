#!/usr/bin/env python3
"""
Backup and Rollback Management System

Ensures automatic backups before all major database changes.
Provides point-in-time recovery for complete rollback capability.

Usage:
    python backup_and_rollback.py --backup                    # Full backup
    python backup_and_rollback.py --list                      # List available backups
    python backup_and_rollback.py --restore <timestamp>       # Restore specific backup
    python backup_and_rollback.py --verify                    # Verify latest backup integrity
"""

import os
import sys
import subprocess
import json
import hashlib
from datetime import datetime
from pathlib import Path
import psycopg2
import argparse

# Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

BACKUP_DIR = Path(r"l:\limo\backups")
BACKUP_MANIFEST = BACKUP_DIR / "backup_manifest.json"

class BackupManager:
    def __init__(self):
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self.load_manifest()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def load_manifest(self):
        """Load backup manifest or create new one."""
        if BACKUP_MANIFEST.exists():
            with open(BACKUP_MANIFEST, 'r') as f:
                return json.load(f)
        return {"backups": [], "current": None}
    
    def save_manifest(self):
        """Save backup manifest."""
        with open(BACKUP_MANIFEST, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def calculate_hash(self, filepath):
        """Calculate SHA256 hash of backup file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def create_backup(self, description="Backup before major change", incremental=False):
        """
        Create full database backup with manifest entry.
        
        Args:
            description: Human-readable reason for backup
            incremental: Not yet implemented, reserved for future use
        
        Returns:
            Tuple of (success: bool, backup_path: Path, info: dict)
        """
        print("\n" + "="*80)
        print(f"CREATING DATABASE BACKUP - {self.timestamp}")
        print("="*80)
        print(f"Description: {description}")
        
        backup_file = self.backup_dir / f"almsdata_{self.timestamp}.dump"
        
        try:
            # 1. Verify database connection
            print("\n1️⃣  Verifying database connection...")
            try:
                conn = psycopg2.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME
                )
                cur = conn.cursor()
                
                # Get row counts for verification
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                table_count = len(cur.fetchall())
                print(f"   ✅ Connected successfully ({table_count} tables)")
                
                cur.close()
                conn.close()
            except Exception as e:
                print(f"   ❌ Connection failed: {e}")
                return False, None, {"error": str(e)}
            
            # 2. Create database dump
            print("\n2️⃣  Creating database dump...")
            
            # Find pg_dump in PostgreSQL installation
            pg_dump_path = None
            common_paths = [
                r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
                r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
                r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
                r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
                r"C:\Program Files (x86)\PostgreSQL\18\bin\pg_dump.exe",
                r"C:\Program Files (x86)\PostgreSQL\17\bin\pg_dump.exe",
                r"C:\Program Files (x86)\PostgreSQL\16\bin\pg_dump.exe",
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    pg_dump_path = path
                    break
            
            if not pg_dump_path:
                return False, None, {"error": "pg_dump not found. Install PostgreSQL or add to PATH"}
            
            dump_cmd = [
                pg_dump_path,
                "-h", DB_HOST,
                "-U", DB_USER,
                "-d", DB_NAME,
                "-F", "custom",  # Use custom format for faster restore
                "-f", str(backup_file)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = DB_PASSWORD
            
            result = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"   ❌ Dump failed: {result.stderr}")
                return False, None, {"error": result.stderr}
            
            # 3. Verify backup file
            print("\n3️⃣  Verifying backup integrity...")
            if not backup_file.exists():
                print(f"   ❌ Backup file not created")
                return False, None, {"error": "Backup file not created"}
            
            file_size = backup_file.stat().st_size / (1024*1024)
            print(f"   ✅ Backup created: {file_size:.2f} MB")
            
            # 4. Calculate hash
            print("\n4️⃣  Calculating file hash...")
            file_hash = self.calculate_hash(backup_file)
            print(f"   ✅ SHA256: {file_hash[:16]}...")
            
            # 5. Update manifest
            print("\n5️⃣  Updating manifest...")
            backup_info = {
                "timestamp": self.timestamp,
                "datetime": datetime.now().isoformat(),
                "description": description,
                "file": str(backup_file),
                "size_mb": round(file_size, 2),
                "hash": file_hash,
                "table_count": table_count,
                "backup_type": "full"
            }
            
            self.manifest["backups"].append(backup_info)
            self.manifest["current"] = self.timestamp
            self.save_manifest()
            print(f"   ✅ Manifest updated (total backups: {len(self.manifest['backups'])})")
            
            # 6. Display summary
            print("\n" + "="*80)
            print("✅ BACKUP COMPLETE")
            print("="*80)
            print(f"Timestamp:    {self.timestamp}")
            print(f"File:         {backup_file.name}")
            print(f"Size:         {file_size:.2f} MB")
            print(f"Description:  {description}")
            print(f"Status:       ✅ Ready for rollback")
            print("\nTo restore this backup:")
            print(f"  python backup_and_rollback.py --restore {self.timestamp}")
            
            return True, backup_file, backup_info
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False, None, {"error": str(e)}
    
    def list_backups(self):
        """List all available backups."""
        if not self.manifest["backups"]:
            print("No backups found.")
            return
        
        print("\n" + "="*80)
        print("AVAILABLE BACKUPS")
        print("="*80)
        print(f"{'Timestamp':<20} {'Size (MB)':<12} {'Type':<10} {'Description':<30}")
        print("-"*80)
        
        for backup in sorted(self.manifest["backups"], key=lambda x: x["timestamp"], reverse=True):
            current = "✅ LATEST" if backup["timestamp"] == self.manifest["current"] else ""
            timestamp = backup["timestamp"]
            size = f"{backup.get('size_mb', 0):.2f}"
            btype = backup.get("backup_type", "unknown")
            desc = backup.get("description", "")[:28]
            print(f"{timestamp:<20} {size:<12} {btype:<10} {desc:<30} {current}")
    
    def verify_backup(self, timestamp=None):
        """Verify backup integrity."""
        if not timestamp:
            timestamp = self.manifest["current"]
        
        if not timestamp:
            print("No backup specified and no current backup in manifest.")
            return False
        
        # Find backup
        backup_info = None
        for b in self.manifest["backups"]:
            if b["timestamp"] == timestamp:
                backup_info = b
                break
        
        if not backup_info:
            print(f"❌ Backup not found: {timestamp}")
            return False
        
        print("\n" + "="*80)
        print(f"VERIFYING BACKUP - {timestamp}")
        print("="*80)
        
        backup_file = Path(backup_info["file"])
        
        # 1. Check file exists
        print("\n1️⃣  Checking file...")
        if not backup_file.exists():
            print(f"   ❌ Backup file not found: {backup_file}")
            return False
        print(f"   ✅ File exists: {backup_file.name}")
        
        # 2. Verify hash
        print("\n2️⃣  Verifying file integrity...")
        current_hash = self.calculate_hash(backup_file)
        expected_hash = backup_info["hash"]
        
        if current_hash == expected_hash:
            print(f"   ✅ Hash verified: {current_hash[:16]}...")
        else:
            print(f"   ❌ Hash mismatch!")
            print(f"      Expected: {expected_hash[:16]}...")
            print(f"      Got:      {current_hash[:16]}...")
            return False
        
        # 3. Display backup info
        print("\n3️⃣  Backup information...")
        print(f"   Timestamp:    {backup_info['timestamp']}")
        print(f"   DateTime:     {backup_info['datetime']}")
        print(f"   Size:         {backup_info['size_mb']} MB")
        print(f"   Description:  {backup_info['description']}")
        print(f"   Tables:       {backup_info.get('table_count', 'unknown')}")
        
        print("\n" + "="*80)
        print("✅ BACKUP INTEGRITY VERIFIED")
        print("="*80)
        return True
    
    def restore_backup(self, timestamp):
        """
        Restore database from backup.
        
        Args:
            timestamp: Backup timestamp to restore
        
        Returns:
            success: bool
        """
        # Find backup
        backup_info = None
        for b in self.manifest["backups"]:
            if b["timestamp"] == timestamp:
                backup_info = b
                break
        
        if not backup_info:
            print(f"❌ Backup not found: {timestamp}")
            return False
        
        backup_file = Path(backup_info["file"])
        
        if not backup_file.exists():
            print(f"❌ Backup file not found: {backup_file}")
            return False
        
        print("\n" + "="*80)
        print(f"RESTORING FROM BACKUP - {timestamp}")
        print("="*80)
        print(f"File:         {backup_file.name}")
        print(f"Description:  {backup_info['description']}")
        print(f"Size:         {backup_info['size_mb']} MB")
        
        # Confirm
        response = input("\n⚠️  WARNING: This will overwrite the current database.\n   Proceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("   ❌ Restore cancelled")
            return False
        
        try:
            # 1. Drop and recreate database
            print("\n1️⃣  Dropping current database...")
            conn = psycopg2.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database="postgres"  # Connect to default database
            )
            conn.autocommit = True
            cur = conn.cursor()
            
            cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
            print(f"   ✅ Database dropped")
            
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"   ✅ Database recreated")
            
            cur.close()
            conn.close()
            
            # 2. Restore from dump
            print("\n2️⃣  Restoring from backup...")
            
            # Find pg_restore in PostgreSQL installation
            pg_restore_path = None
            common_paths = [
                r"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe",
                r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe",
                r"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
                r"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe",
                r"C:\Program Files (x86)\PostgreSQL\18\bin\pg_restore.exe",
                r"C:\Program Files (x86)\PostgreSQL\17\bin\pg_restore.exe",
                r"C:\Program Files (x86)\PostgreSQL\16\bin\pg_restore.exe",
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    pg_restore_path = path
                    print(f"   Found pg_restore: {path}")
                    break
            
            if not pg_restore_path:
                print(f"   ❌ pg_restore not found")
                return False
            
            restore_cmd = [
                pg_restore_path,
                "-h", DB_HOST,
                "-U", DB_USER,
                "-d", DB_NAME,
                "-v",  # Verbose
                str(backup_file)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = DB_PASSWORD
            
            result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                print(f"   ❌ Restore failed: {result.stderr}")
                return False
            
            print(f"   ✅ Database restored")
            
            # 3. Verify
            print("\n3️⃣  Verifying restored database...")
            conn = psycopg2.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            cur = conn.cursor()
            
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = len(cur.fetchall())
            print(f"   ✅ Database verified ({table_count} tables)")
            
            cur.close()
            conn.close()
            
            print("\n" + "="*80)
            print("✅ RESTORE COMPLETE")
            print("="*80)
            return True
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Database backup and rollback management"
    )
    parser.add_argument("--backup", action="store_true", help="Create full backup")
    parser.add_argument("--description", default="Backup before major change", 
                       help="Backup description")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--verify", action="store_true", help="Verify backup integrity")
    parser.add_argument("--restore", help="Restore from backup (timestamp)")
    
    args = parser.parse_args()
    
    manager = BackupManager()
    
    if args.backup:
        success, backup_path, info = manager.create_backup(description=args.description)
        sys.exit(0 if success else 1)
    
    elif args.list:
        manager.list_backups()
    
    elif args.verify:
        success = manager.verify_backup()
        sys.exit(0 if success else 1)
    
    elif args.restore:
        success = manager.restore_backup(args.restore)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
