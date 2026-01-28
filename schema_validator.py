"""
SCHEMA REFERENCE LOOKUP SYSTEM
Prevents naming errors by providing quick lookups
Run this to verify table/column existence before writing queries
"""
import os
import json
import psycopg2
from pathlib import Path

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

class SchemaValidator:
    """Validate schema references before queries are executed"""
    
    def __init__(self):
        self.schema_file = Path("l:/limo/DATABASE_SCHEMA_INVENTORY.json")
        self.schema = None
        self.load_schema()
    
    def load_schema(self):
        """Load schema from inventory file"""
        if self.schema_file.exists():
            with open(self.schema_file, 'r') as f:
                self.schema = json.load(f)
            print(f"✅ Loaded schema with {len(self.schema['tables'])} tables")
        else:
            print("❌ Schema file not found. Run audit_database_schema.py first")
    
    def table_exists(self, table_name):
        """Check if table exists"""
        if not self.schema:
            return False
        if table_name in self.schema['tables']:
            return True
        # Check if it's a view
        if table_name in self.schema['views']:
            return True
        return False
    
    def column_exists(self, table_name, column_name):
        """Check if column exists in table"""
        if not self.schema:
            return False
        
        if table_name in self.schema['tables']:
            return column_name in self.schema['tables'][table_name]['columns']
        
        if table_name in self.schema['views']:
            return column_name in self.schema['views'][table_name]['columns']
        
        return False
    
    def get_table_columns(self, table_name):
        """List all columns in table"""
        if table_name in self.schema['tables']:
            return list(self.schema['tables'][table_name]['columns'].keys())
        if table_name in self.schema['views']:
            return list(self.schema['views'][table_name]['columns'].keys())
        return []
    
    def get_table_info(self, table_name):
        """Get full table information"""
        if table_name in self.schema['tables']:
            return self.schema['tables'][table_name]
        if table_name in self.schema['views']:
            return self.schema['views'][table_name]
        return None
    
    def find_columns(self, column_name_pattern):
        """Find all columns matching pattern (e.g., find all '*_id' columns)"""
        results = {}
        
        for table_name, table_info in self.schema['tables'].items():
            for col_name in table_info['columns'].keys():
                if column_name_pattern.lower() in col_name.lower():
                    if table_name not in results:
                        results[table_name] = []
                    results[table_name].append(col_name)
        
        return results
    
    def find_tables(self, table_name_pattern):
        """Find all tables matching pattern"""
        results = []
        
        for table_name in self.schema['tables'].keys():
            if table_name_pattern.lower() in table_name.lower():
                results.append(table_name)
        
        return results
    
    def get_foreign_keys(self, table_name):
        """Get all foreign keys for a table"""
        fks = []
        
        for fk in self.schema['foreign_keys']:
            if fk['table'] == table_name:
                fks.append({
                    'column': fk['column'],
                    'references': f"{fk['references_table']}.{fk['references_column']}"
                })
        
        return fks
    
    def validate_query(self, table_name, columns):
        """Pre-validate that all columns exist before query execution"""
        if not self.table_exists(table_name):
            raise ValueError(f"❌ TABLE NOT FOUND: {table_name}")
        
        missing = []
        for col in columns:
            if not self.column_exists(table_name, col):
                missing.append(col)
        
        if missing:
            available = self.get_table_columns(table_name)
            raise ValueError(
                f"❌ COLUMNS NOT FOUND in {table_name}: {missing}\n"
                f"Available columns: {available}"
            )
        
        print(f"✅ {table_name} + {columns} - validated")
    
    def print_full_schema(self, table_name=None):
        """Print table schema in readable format"""
        if table_name:
            if not self.table_exists(table_name):
                print(f"❌ Table not found: {table_name}")
                suggestions = self.find_tables(table_name)
                if suggestions:
                    print(f"Did you mean: {suggestions}")
                return
            
            info = self.get_table_info(table_name)
            print(f"\n{'='*70}")
            print(f"TABLE: {table_name}")
            print(f"{'='*70}")
            print(f"Rows: {info.get('row_count', 'unknown')}")
            print(f"Size: {info.get('size_mb', 0):.2f} MB")
            print(f"\nCOLUMNS:")
            for col_name, col_info in info['columns'].items():
                nullable = " (nullable)" if col_info.get('nullable') else " (NOT NULL)"
                print(f"  {col_name:30s} {col_info.get('type', 'unknown'):20s} {nullable}")
            
            fks = self.get_foreign_keys(table_name)
            if fks:
                print(f"\nFOREIGN KEYS:")
                for fk in fks:
                    print(f"  {fk['column']:30s} → {fk['references']}")
        else:
            # List all tables
            print(f"\n{'='*70}")
            print(f"TABLES ({len(self.schema['tables'])})")
            print(f"{'='*70}")
            for table_name, info in sorted(self.schema['tables'].items()):
                if info['row_count'] > 0:
                    print(f"  {table_name:40s} {info['row_count']:8d} rows  {info['size_mb']:8.2f} MB")

# Example usage
if __name__ == "__main__":
    validator = SchemaValidator()
    
    print("\n" + "="*70)
    print("SCHEMA VALIDATION EXAMPLES")
    print("="*70)
    
    # Example 1: Validate table exists
    print("\n[1] Check if 'receipts' table exists:")
    if validator.table_exists('receipts'):
        print("✅ receipts table exists")
    
    # Example 2: Validate columns
    print("\n[2] Check if 'receipts' has 'gl_account_code' column:")
    if validator.column_exists('receipts', 'gl_account_code'):
        print("✅ Column exists")
    else:
        print("❌ Column NOT found")
        available = validator.get_table_columns('receipts')
        print(f"Available columns: {available[:5]}... ({len(available)} total)")
    
    # Example 3: Find all columns with pattern
    print("\n[3] Find all columns ending with '_id':")
    results = validator.find_columns('_id')
    print(f"Found in {len(results)} tables:")
    for table_name, cols in list(results.items())[:5]:
        print(f"  {table_name}: {cols[:3]}...")
    
    # Example 4: Find tables with pattern
    print("\n[4] Find all backup tables:")
    backups = validator.find_tables('backup')
    print(f"Found {len(backups)} backup tables:")
    print(f"  {backups[:5]}... (showing first 5)")
    
    # Example 5: Validate a query before execution
    print("\n[5] Validate query columns:")
    try:
        validator.validate_query('receipts', ['receipt_id', 'vendor_name', 'gross_amount'])
        print("✅ Query validated successfully")
    except ValueError as e:
        print(f"{e}")
    
    # Example 6: Print table schema
    print("\n[6] Print full schema for 'receipts':")
    validator.print_full_schema('receipts')
    
    # Example 7: Show foreign keys
    print("\n[7] Foreign keys in 'receipts':")
    fks = validator.get_foreign_keys('receipts')
    for fk in fks[:5]:
        print(f"  {fk['column']:30s} → {fk['references']}")
