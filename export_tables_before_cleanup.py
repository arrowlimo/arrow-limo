#!/usr/bin/env python3
"""
Export Duplicate/Backup Tables Before Deletion
Creates individual backups of all 17 tables identified for cleanup
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
import psycopg2

# Database connection
DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

# Tables to export (17 total)
TABLES_TO_EXPORT = {
    'banking_transactions_backups': [
        'banking_transactions_decimal_fix_20251206_231911',
        'banking_transactions_liquor_consolidation_20251206_231228',
        'banking_transactions_typo_fix_20251206_230713',
        'banking_transactions_vendor_standardization_20251206_234542',
        'banking_transactions_vendor_standardization_20251206_234601',
        'banking_transactions_vendor_standardization_20251206_234629',
        'banking_transactions_vendor_standardization_20251206_234648',
    ],
    'receipts_duplicates': [
        'receipts_missing_creation_20251206_235121',
        'receipts_missing_creation_20251206_235143',
    ],
    'charters_backups': [
        'charters_backup_cancelled_20260120_174741',
        'charters_backup_closed_nopay_20260120_175447',
        'charters_retainer_cancel_fix_20251204',
        'charters_zero_balance_fix_20251111_191705',
    ],
    'scotia_staging': [
        'staging_scotia_2012_verified',
        'staging_scotia_2012_verified_archived_20251109',
    ],
    'lms_staging': [
        'lms_staging_payment_archived_20251109',
        'lms_staging_reserve_archived_20251109',
    ]
}

class TableExporter:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_dir = Path(r'L:\limo\backups\table_exports_before_cleanup')
        self.export_dir = self.base_dir / f"export_{self.timestamp}"
        self.conn = None
        self.manifest = []
        
    def setup_export_directory(self):
        """Create organized export directory structure"""
        print("=" * 80)
        print("SETTING UP EXPORT DIRECTORY")
        print("=" * 80)
        
        # Create main directory
        self.export_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {self.export_dir}")
        
        # Create subdirectories for each category
        for category in TABLES_TO_EXPORT.keys():
            category_dir = self.export_dir / category
            category_dir.mkdir(exist_ok=True)
            print(f"✅ Created: {category_dir}")
        
        print()
    
    def connect_db(self):
        """Connect to database to get table info"""
        self.conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
    
    def get_table_info(self, table_name):
        """Get row count and size for table"""
        try:
            cur = self.conn.cursor()
            
            # Get row count
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cur.fetchone()[0]
            
            # Get table size
            cur.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
            """)
            size = cur.fetchone()[0]
            
            cur.close()
            return row_count, size
        except Exception as e:
            return None, str(e)
    
    def export_table(self, table_name, category):
        """Export single table using pg_dump"""
        print(f"\n📦 Exporting: {table_name}")
        
        # Get table info
        row_count, size = self.get_table_info(table_name)
        
        if row_count is not None:
            print(f"   Rows: {row_count:,}")
            print(f"   Size: {size}")
        else:
            print(f"   ⚠️  Could not get table info: {size}")
            return False
        
        # Export file path
        export_file = self.export_dir / category / f"{table_name}.sql"
        
        # pg_dump command
        cmd = [
            'pg_dump',
            '-h', DB_HOST,
            '-U', DB_USER,
            '-d', DB_NAME,
            '-t', table_name,
            '--data-only',  # Only data, not schema (saves space)
            '--column-inserts',  # Use INSERT statements (more portable)
            '-f', str(export_file)
        ]
        
        # Set password environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASSWORD
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                file_size = export_file.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                print(f"   ✅ Exported: {export_file.name} ({file_size_mb:.2f} MB)")
                
                # Add to manifest
                self.manifest.append({
                    'category': category,
                    'table': table_name,
                    'rows': row_count,
                    'db_size': size,
                    'file_size_mb': file_size_mb,
                    'export_file': str(export_file.relative_to(self.export_dir))
                })
                return True
            else:
                print(f"   ❌ Export failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"   ❌ Export error: {e}")
            return False
    
    def export_full_schema(self, table_name, category):
        """Export table with schema (structure + data)"""
        print(f"\n📋 Exporting FULL (schema + data): {table_name}")
        
        export_file = self.export_dir / category / f"{table_name}_FULL.sql"
        
        cmd = [
            'pg_dump',
            '-h', DB_HOST,
            '-U', DB_USER,
            '-d', DB_NAME,
            '-t', table_name,
            '--create',  # Include CREATE TABLE
            '-f', str(export_file)
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASSWORD
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                file_size = export_file.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                print(f"   ✅ Full export: {export_file.name} ({file_size_mb:.2f} MB)")
                return True
            else:
                print(f"   ⚠️  Full export failed (not critical): {result.stderr[:100]}")
                return False
        except Exception as e:
            print(f"   ⚠️  Full export error (not critical): {e}")
            return False
    
    def generate_manifest(self):
        """Generate manifest file with export details"""
        print("\n" + "=" * 80)
        print("GENERATING MANIFEST")
        print("=" * 80)
        
        manifest_file = self.export_dir / "EXPORT_MANIFEST.txt"
        
        lines = []
        lines.append("=" * 80)
        lines.append("TABLE EXPORT MANIFEST")
        lines.append("=" * 80)
        lines.append(f"Export Date: {datetime.now()}")
        lines.append(f"Total Tables: {len(self.manifest)}")
        lines.append(f"Export Location: {self.export_dir}")
        lines.append("")
        
        # Group by category
        for category in TABLES_TO_EXPORT.keys():
            category_tables = [m for m in self.manifest if m['category'] == category]
            if category_tables:
                lines.append("")
                lines.append("=" * 80)
                lines.append(f"CATEGORY: {category.upper()}")
                lines.append("=" * 80)
                
                total_rows = sum(t['rows'] for t in category_tables)
                total_size_mb = sum(t['file_size_mb'] for t in category_tables)
                
                lines.append(f"Tables: {len(category_tables)}")
                lines.append(f"Total Rows: {total_rows:,}")
                lines.append(f"Total Export Size: {total_size_mb:.2f} MB")
                lines.append("")
                
                for table in category_tables:
                    lines.append(f"  📦 {table['table']}")
                    lines.append(f"     Rows: {table['rows']:,}")
                    lines.append(f"     DB Size: {table['db_size']}")
                    lines.append(f"     Export File: {table['export_file']}")
                    lines.append(f"     File Size: {table['file_size_mb']:.2f} MB")
                    lines.append("")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("RECOVERY INSTRUCTIONS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("To restore a single table:")
        lines.append("  psql -h localhost -U postgres -d almsdata < path/to/table_FULL.sql")
        lines.append("")
        lines.append("To restore just data (if table exists):")
        lines.append("  psql -h localhost -U postgres -d almsdata < path/to/table.sql")
        lines.append("")
        lines.append("=" * 80)
        
        manifest_text = "\n".join(lines)
        
        with open(manifest_file, 'w', encoding='utf-8') as f:
            f.write(manifest_text)
        
        print(manifest_text)
        print(f"\n✅ Manifest saved: {manifest_file}")
    
    def generate_restore_script(self):
        """Generate PowerShell script to restore all tables if needed"""
        restore_script = self.export_dir / "RESTORE_ALL_TABLES.ps1"
        
        lines = []
        lines.append("# PowerShell script to restore all exported tables")
        lines.append(f"# Generated: {datetime.now()}")
        lines.append("")
        lines.append("$ErrorActionPreference = 'Stop'")
        lines.append("")
        lines.append("Write-Host '=' * 80")
        lines.append("Write-Host 'RESTORING ALL EXPORTED TABLES'")
        lines.append("Write-Host '=' * 80")
        lines.append("")
        
        for category, tables in TABLES_TO_EXPORT.items():
            lines.append(f"# Category: {category}")
            for table in tables:
                file_path = f"{category}\\{table}_FULL.sql"
                lines.append(f"Write-Host 'Restoring: {table}'")
                lines.append(f"psql -h localhost -U postgres -d almsdata -f '{file_path}'")
                lines.append("")
        
        lines.append("Write-Host '✅ All tables restored'")
        
        with open(restore_script, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        print(f"✅ Restore script: {restore_script}")
    
    def run_export(self):
        """Main export process"""
        print("\n" + "=" * 80)
        print("TABLE EXPORT BEFORE CLEANUP")
        print("=" * 80)
        print(f"Exporting 17 tables identified for deletion")
        print(f"Export directory: {self.export_dir}")
        print("=" * 80)
        
        self.setup_export_directory()
        self.connect_db()
        
        total_exported = 0
        
        for category, tables in TABLES_TO_EXPORT.items():
            print("\n" + "=" * 80)
            print(f"CATEGORY: {category.upper()} ({len(tables)} tables)")
            print("=" * 80)
            
            for table in tables:
                # Export data-only version
                success = self.export_table(table, category)
                
                # Also export full version (schema + data) for complete recovery
                self.export_full_schema(table, category)
                
                if success:
                    total_exported += 1
        
        self.conn.close()
        
        # Generate manifest and restore script
        self.generate_manifest()
        self.generate_restore_script()
        
        print("\n" + "=" * 80)
        print("EXPORT COMPLETE")
        print("=" * 80)
        print(f"✅ Successfully exported: {total_exported} / 17 tables")
        print(f"📁 Export location: {self.export_dir}")
        print(f"📋 Manifest: {self.export_dir / 'EXPORT_MANIFEST.txt'}")
        print(f"🔧 Restore script: {self.export_dir / 'RESTORE_ALL_TABLES.ps1'}")
        print("")
        print("Next steps:")
        print("  1. Verify exports completed successfully")
        print("  2. Review manifest file")
        print("  3. Run verification queries (see DATABASE_CLEANUP_PLAN.md)")
        print("  4. Delete tables using cleanup script")
        print("=" * 80)

def main():
    exporter = TableExporter()
    exporter.run_export()

if __name__ == "__main__":
    main()
