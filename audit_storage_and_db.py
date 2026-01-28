#!/usr/bin/env python3
"""
Storage and Document System Audit
Check vehicle records, document storage, and local/Neon DB selection
"""

import os
import sys
from pathlib import Path
import json
from datetime import datetime


class StorageAudit:
    def __init__(self):
        self.codebase_path = Path("L:/limo")
        self.results = {
            'document_storage': {},
            'vehicle_storage': {},
            'db_selection': {},
            'issues': []
        }
    
    def check_document_storage(self):
        """Check if document storage system exists"""
        print("\n" + "="*80)
        print("DOCUMENT STORAGE AUDIT")
        print("="*80)
        
        # Check for local storage paths
        local_paths = [
            Path("L:/limo/documents"),
            Path("L:/limo/uploads"),
            Path("L:/limo/files"),
            Path("L:/limo/data"),
        ]
        
        print("\nChecking local storage paths:")
        for path in local_paths:
            exists = path.exists()
            status = "✅ EXISTS" if exists else "❌ NOT FOUND"
            print(f"  {path}: {status}")
            
            if exists:
                try:
                    files = len(list(path.glob("*")))
                    print(f"    └─ Contains {files} items")
                except:
                    print(f"    └─ (unreadable)")
            
            self.results['document_storage'][str(path)] = {
                'exists': exists,
                'is_writable': path.exists() and os.access(path, os.W_OK)
            }
        
        # Check for S3/cloud storage in code
        print("\nChecking for cloud storage integration:")
        cloud_services = {
            's3': ['boto3', 'S3', 'aws'],
            'azure': ['azure', 'blob_service'],
            'gcp': ['google.cloud', 'gcs'],
            'dropbox': ['dropbox'],
            'sharepoint': ['sharepoint', 'office365']
        }
        
        found_services = []
        for service, keywords in cloud_services.items():
            for py_file in self.codebase_path.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    if any(kw in content for kw in keywords):
                        found_services.append(service)
                        break
                except:
                    pass
        
        if found_services:
            print(f"  ✅ Found cloud integration: {', '.join(set(found_services))}")
        else:
            print(f"  ❌ No cloud storage integration found")
            self.results['issues'].append("No cloud storage integration (S3, Azure, etc.)")
        
        # Check database blob storage
        print("\nChecking for database blob storage:")
        blob_check = self._check_database_blobs()
        if blob_check['has_blob_tables']:
            print(f"  ✅ Database has blob/file storage tables: {blob_check['tables']}")
        else:
            print(f"  ❌ No blob storage tables found in database")
            self.results['issues'].append("No database blob storage tables")
        
        self.results['document_storage']['blob_tables'] = blob_check
    
    def _check_database_blobs(self):
        """Check for blob storage in database"""
        try:
            import psycopg2
            
            DB_HOST = os.environ.get("DB_HOST", "localhost")
            DB_NAME = os.environ.get("DB_NAME", "almsdata")
            DB_USER = os.environ.get("DB_USER", "postgres")
            DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
            
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND (table_name LIKE '%document%' 
                     OR table_name LIKE '%file%' 
                     OR table_name LIKE '%attachment%'
                     OR table_name LIKE '%blob%')
                ORDER BY table_name
            """)
            
            tables = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            
            return {
                'has_blob_tables': len(tables) > 0,
                'tables': tables
            }
        except Exception as e:
            print(f"  ⚠️  Could not check database: {e}")
            return {'has_blob_tables': False, 'tables': []}
    
    def check_vehicle_storage(self):
        """Check if vehicle records/documents are stored"""
        print("\n" + "="*80)
        print("VEHICLE RECORDS STORAGE AUDIT")
        print("="*80)
        
        # Check for vehicle-related tables
        print("\nChecking for vehicle storage tables:")
        vehicle_keywords = ['vehicle', 'fleet', 'car', 'transportation']
        
        vehicle_files = []
        for py_file in self.codebase_path.rglob("*.py"):
            try:
                filename = py_file.name.lower()
                if any(kw in filename for kw in vehicle_keywords):
                    vehicle_files.append(str(py_file.relative_to(self.codebase_path)))
            except:
                pass
        
        if vehicle_files:
            print(f"  ✅ Found vehicle-related code: {len(vehicle_files)} files")
            for f in vehicle_files[:5]:
                print(f"     - {f}")
        else:
            print(f"  ❌ No vehicle-related code files found")
        
        # Check for registration/insurance documents
        print("\nChecking for vehicle document storage:")
        doc_keywords = ['registration', 'insurance', 'maintenance', 'inspection']
        has_doc_code = False
        
        for py_file in self.codebase_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                if any(kw in content.lower() for kw in doc_keywords):
                    has_doc_code = True
                    break
            except:
                pass
        
        if has_doc_code:
            print(f"  ✅ Found vehicle document handling code")
        else:
            print(f"  ❌ No vehicle document handling found")
            self.results['issues'].append("No vehicle document storage implementation")
        
        self.results['vehicle_storage'] = {
            'has_code': len(vehicle_files) > 0,
            'code_files': vehicle_files,
            'has_doc_handling': has_doc_code
        }
    
    def check_db_selection(self):
        """Check if user can select local vs Neon before login"""
        print("\n" + "="*80)
        print("DATABASE SELECTION AUDIT (Local vs Neon)")
        print("="*80)
        
        # Check login dialog
        print("\nChecking LoginDialog for DB selection:")
        login_files = list(self.codebase_path.rglob("*login*"))
        
        has_db_selection = False
        login_code = None
        
        for file in login_files:
            if file.suffix == '.py':
                try:
                    content = file.read_text(encoding='utf-8', errors='ignore')
                    if 'neon' in content.lower() or 'local' in content.lower():
                        has_db_selection = True
                        login_code = str(file.relative_to(self.codebase_path))
                except:
                    pass
        
        if has_db_selection:
            print(f"  ✅ Found DB selection code: {login_code}")
        else:
            print(f"  ❌ No DB selection in login")
            self.results['issues'].append("Database selection not in login screen (user must select before login)")
        
        # Check environment variables
        print("\nChecking environment variable configuration:")
        env_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        for var in env_vars:
            value = os.environ.get(var, 'NOT SET')
            print(f"  {var}: {value if len(str(value)) < 30 else value[:30] + '...'}")
        
        # Check for .env files
        print("\nChecking for .env configuration files:")
        env_files = list(self.codebase_path.glob("**/.env*"))
        if env_files:
            print(f"  ✅ Found {len(env_files)} .env files")
            for env in env_files:
                print(f"     - {env.relative_to(self.codebase_path)}")
        else:
            print(f"  ❌ No .env files found")
        
        # Check for config.py/config.json
        print("\nChecking for config files:")
        config_files = []
        for pattern in ['config.py', 'config.json', 'settings.py', 'settings.json']:
            config_files.extend(self.codebase_path.glob(f"**/{pattern}"))
        
        if config_files:
            print(f"  ✅ Found {len(config_files)} config files")
            for cfg in config_files:
                print(f"     - {cfg.relative_to(self.codebase_path)}")
        else:
            print(f"  ❌ No config files found")
        
        self.results['db_selection'] = {
            'has_login_selection': has_db_selection,
            'login_code': login_code,
            'has_env_files': len(env_files) > 0,
            'has_config_files': len(config_files) > 0,
            'env_vars_set': {var: os.environ.get(var) is not None for var in env_vars}
        }
    
    def generate_report(self):
        """Generate storage audit report"""
        print("\n" + "="*80)
        print("STORAGE AUDIT SUMMARY")
        print("="*80)
        
        print("\n📋 ISSUES FOUND:")
        if self.results['issues']:
            for issue in self.results['issues']:
                print(f"  ⚠️  {issue}")
        else:
            print(f"  ✅ No critical issues found")
        
        print("\n📊 RECOMMENDATIONS:")
        print("  1. Implement document storage system (local + cloud)")
        print("  2. Add DB selection to login screen (before entering credentials)")
        print("  3. Create vehicle document storage tables")
        print("  4. Add storage system documentation")
        
        # Save report
        reports_dir = Path("L:/limo/reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"storage_audit_{timestamp}.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n✅ Report saved: {report_path}")


def main():
    audit = StorageAudit()
    audit.check_document_storage()
    audit.check_vehicle_storage()
    audit.check_db_selection()
    audit.generate_report()


if __name__ == '__main__':
    main()
