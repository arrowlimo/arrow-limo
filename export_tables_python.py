#!/usr/bin/env python3
"""
Export Duplicate/Backup Tables Before Deletion (Pure Python Version)
Uses psycopg2 directly - no pg_dump required
"""

import psycopg2
from datetime import datetime
from pathlib import Path
import json
import csv

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
        """Connect to database"""
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
            
            # Get column names and types
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            
            cur.close()
            return row_count, size, columns
        except Exception as e:
            return None, str(e), []
    
    def export_table_as_sql(self, table_name, category, columns):
        """Export table as SQL INSERT statements"""
        print(f"   Exporting as SQL...")
        
        export_file = self.export_dir / category / f"{table_name}.sql"
        
        try:
            cur = self.conn.cursor()
            
            # Get all data
            col_names = [col[0] for col in columns]
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()
            
            with open(export_file, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"-- Export of table: {table_name}\n")
                f.write(f"-- Export date: {datetime.now()}\n")
                f.write(f"-- Row count: {len(rows)}\n")
                f.write(f"\n")
                
                # Write INSERT statements
                if rows:
                    col_list = ", ".join(col_names)
                    
                    for row in rows:
                        # Format values
                        values = []
                        for val in row:
                            if val is None:
                                values.append('NULL')
                            elif isinstance(val, str):
                                # Escape single quotes
                                escaped = val.replace("'", "''")
                                values.append(f"'{escaped}'")
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, datetime):
                                values.append(f"'{val}'")
                            else:
                                values.append(f"'{str(val)}'")
                        
                        value_list = ", ".join(values)
                        f.write(f"INSERT INTO {table_name} ({col_list}) VALUES ({value_list});\n")
            
            cur.close()
            
            file_size = export_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"   ✅ SQL export: {export_file.name} ({file_size_mb:.2f} MB)")
            
            return True, file_size_mb
        except Exception as e:
            print(f"   ❌ SQL export failed: {e}")
            return False, 0
    
    def export_table_as_csv(self, table_name, category, columns):
        """Export table as CSV"""
        print(f"   Exporting as CSV...")
        
        export_file = self.export_dir / category / f"{table_name}.csv"
        
        try:
            cur = self.conn.cursor()
            
            # Get all data
            col_names = [col[0] for col in columns]
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()
            
            with open(export_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(col_names)
                # Write data
                writer.writerows(rows)
            
            cur.close()
            
            file_size = export_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"   ✅ CSV export: {export_file.name} ({file_size_mb:.2f} MB)")
            
            return True, file_size_mb
        except Exception as e:
            print(f"   ❌ CSV export failed: {e}")
            return False, 0
    
    def export_table_schema(self, table_name, category, columns):
        """Export table schema definition"""
        print(f"   Exporting schema...")
        
        export_file = self.export_dir / category / f"{table_name}_SCHEMA.sql"
        
        try:
            cur = self.conn.cursor()
            
            # Get CREATE TABLE statement (reconstruct)
            with open(export_file, 'w', encoding='utf-8') as f:
                f.write(f"-- Schema for table: {table_name}\n")
                f.write(f"-- Export date: {datetime.now()}\n\n")
                
                f.write(f"DROP TABLE IF EXISTS {table_name};\n\n")
                f.write(f"CREATE TABLE {table_name} (\n")
                
                col_defs = []
                for col_name, col_type in columns:
                    col_defs.append(f"    {col_name} {col_type}")
                
                f.write(",\n".join(col_defs))
                f.write("\n);\n")
            
            cur.close()
            print(f"   ✅ Schema export: {export_file.name}")
            
            return True
        except Exception as e:
            print(f"   ⚠️  Schema export failed: {e}")
            return False
    
    def export_table(self, table_name, category):
        """Export single table in multiple formats"""
        print(f"\n📦 Exporting: {table_name}")
        
        # Get table info
        row_count, size, columns = self.get_table_info(table_name)
        
        if row_count is None:
            print(f"   ❌ Could not get table info: {size}")
            return False
        
        print(f"   Rows: {row_count:,}")
        print(f"   Size: {size}")
        print(f"   Columns: {len(columns)}")
        
        # Export in multiple formats for safety
        sql_success, sql_size = self.export_table_as_sql(table_name, category, columns)
        csv_success, csv_size = self.export_table_as_csv(table_name, category, columns)
        schema_success = self.export_table_schema(table_name, category, columns)
        
        if sql_success or csv_success:
            # Add to manifest
            self.manifest.append({
                'category': category,
                'table': table_name,
                'rows': row_count,
                'db_size': size,
                'columns': len(columns),
                'sql_export_mb': sql_size,
                'csv_export_mb': csv_size,
                'schema_exported': schema_success
            })
            return True
        else:
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
        lines.append(f"Total Tables Exported: {len(self.manifest)}")
        lines.append(f"Export Location: {self.export_dir}")
        lines.append("")
        
        total_rows = sum(t['rows'] for t in self.manifest)
        total_sql_mb = sum(t['sql_export_mb'] for t in self.manifest)
        total_csv_mb = sum(t['csv_export_mb'] for t in self.manifest)
        
        lines.append(f"TOTALS:")
        lines.append(f"  Total Rows Exported: {total_rows:,}")
        lines.append(f"  Total SQL Size: {total_sql_mb:.2f} MB")
        lines.append(f"  Total CSV Size: {total_csv_mb:.2f} MB")
        lines.append("")
        
        # Group by category
        for category in TABLES_TO_EXPORT.keys():
            category_tables = [m for m in self.manifest if m['category'] == category]
            if category_tables:
                lines.append("")
                lines.append("=" * 80)
                lines.append(f"CATEGORY: {category.upper()}")
                lines.append("=" * 80)
                
                cat_rows = sum(t['rows'] for t in category_tables)
                cat_sql_mb = sum(t['sql_export_mb'] for t in category_tables)
                cat_csv_mb = sum(t['csv_export_mb'] for t in category_tables)
                
                lines.append(f"Tables: {len(category_tables)}")
                lines.append(f"Total Rows: {cat_rows:,}")
                lines.append(f"SQL Size: {cat_sql_mb:.2f} MB")
                lines.append(f"CSV Size: {cat_csv_mb:.2f} MB")
                lines.append("")
                
                for table in category_tables:
                    lines.append(f"  📦 {table['table']}")
                    lines.append(f"     Rows: {table['rows']:,}")
                    lines.append(f"     DB Size: {table['db_size']}")
                    lines.append(f"     Columns: {table['columns']}")
                    lines.append(f"     SQL Export: {table['sql_export_mb']:.2f} MB")
                    lines.append(f"     CSV Export: {table['csv_export_mb']:.2f} MB")
                    lines.append(f"     Schema: {'✅' if table['schema_exported'] else '❌'}")
                    lines.append("")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("RECOVERY INSTRUCTIONS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("To restore a table from SQL backup:")
        lines.append("  1. Create table structure:")
        lines.append("     psql -h localhost -U postgres -d almsdata < table_SCHEMA.sql")
        lines.append("  2. Import data:")
        lines.append("     psql -h localhost -U postgres -d almsdata < table.sql")
        lines.append("")
        lines.append("To import from CSV:")
        lines.append("  Use COPY command or import tool with table.csv")
        lines.append("")
        lines.append("=" * 80)
        
        manifest_text = "\n".join(lines)
        
        with open(manifest_file, 'w', encoding='utf-8') as f:
            f.write(manifest_text)
        
        # Also save JSON version
        json_file = self.export_dir / "EXPORT_MANIFEST.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.manifest, f, indent=2, default=str)
        
        print(manifest_text)
        print(f"\n✅ Text manifest: {manifest_file}")
        print(f"✅ JSON manifest: {json_file}")
    
    def run_export(self):
        """Main export process"""
        print("\n" + "=" * 80)
        print("TABLE EXPORT BEFORE CLEANUP (Python Version)")
        print("=" * 80)
        print(f"Exporting 17 tables identified for deletion")
        print(f"Export directory: {self.export_dir}")
        print(f"Export formats: SQL, CSV, Schema")
        print("=" * 80)
        
        self.setup_export_directory()
        self.connect_db()
        
        total_exported = 0
        
        for category, tables in TABLES_TO_EXPORT.items():
            print("\n" + "=" * 80)
            print(f"CATEGORY: {category.upper()} ({len(tables)} tables)")
            print("=" * 80)
            
            for table in tables:
                success = self.export_table(table, category)
                if success:
                    total_exported += 1
        
        self.conn.close()
        
        # Generate manifest
        self.generate_manifest()
        
        print("\n" + "=" * 80)
        print("EXPORT COMPLETE")
        print("=" * 80)
        print(f"✅ Successfully exported: {total_exported} / 17 tables")
        print(f"📁 Export location: {self.export_dir}")
        print(f"📋 Manifest: {self.export_dir / 'EXPORT_MANIFEST.txt'}")
        print(f"📋 JSON: {self.export_dir / 'EXPORT_MANIFEST.json'}")
        print("")
        
        if total_exported == 17:
            print("✅ ALL TABLES EXPORTED SUCCESSFULLY!")
            print("")
            print("Next steps:")
            print("  1. Review manifest file")
            print("  2. Run verification queries (see DATABASE_CLEANUP_PLAN.md)")
            print("  3. Execute cleanup script to delete tables")
        else:
            print(f"⚠️  WARNING: Only {total_exported} of 17 tables exported")
            print("   Review errors above before proceeding with deletion")
        
        print("=" * 80)

def main():
    exporter = TableExporter()
    exporter.run_export()

if __name__ == "__main__":
    main()
