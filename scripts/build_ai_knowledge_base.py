#!/usr/bin/env python3
"""
Build AI Knowledge Base for In-App Copilot
==========================================

Ingests all business knowledge, documentation, session logs, code, and database schema
into a structured knowledge base for RAG (Retrieval Augmented Generation).

Knowledge Sources:
- .github/copilot-instructions.md (core business rules, critical DB patterns)
- SESSION_*.md files (21+ files: problems solved, context history)
- All MD files in root (300+ analysis/audit reports)
- DATABASE_SCHEMA_REFERENCE.md (table structures, column definitions)
- scripts/*.py docstrings (business logic examples)
- Database metadata (from information_schema)

Output Structure:
knowledge/
  kb_sources/               # Raw source files with metadata
    database/               # Schema, constraints, indexes
    business_rules/         # GST calc, HOS regs, WCB rates
    tax_rules/              # T2/T4 calculations, CCA rates
    session_history/        # Session logs, problems solved
    code_examples/          # Python functions, SQL queries
    analysis_reports/       # Audit findings, data quality issues
  metadata.json             # Source inventory with tags
  
Metadata Tags:
- domain: tax, payroll, charter, banking, fleet, receipt, employee
- type: schema, rule, problem, solution, analysis, code
- date: when created/modified
- priority: critical, high, medium, low (for retrieval ranking)
- tables: list of DB tables referenced
- concepts: key business terms (reserve_number, GST, HOS, WCB, etc.)

Usage:
    python scripts/build_ai_knowledge_base.py --rebuild
    python scripts/build_ai_knowledge_base.py --update   # incremental only
    python scripts/build_ai_knowledge_base.py --stats    # show inventory
"""
import os
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
import psycopg2
from psycopg2.extras import DictCursor

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
if not DB_PASSWORD:
    # Fallback to default
    DB_PASSWORD = "***REMOVED***"

# Knowledge base paths
KB_ROOT = Path("knowledge")
KB_SOURCES = KB_ROOT / "kb_sources"
KB_DATABASE = KB_SOURCES / "database"
KB_BUSINESS_RULES = KB_SOURCES / "business_rules"
KB_TAX_RULES = KB_SOURCES / "tax_rules"
KB_SESSION_HISTORY = KB_SOURCES / "session_history"
KB_CODE_EXAMPLES = KB_SOURCES / "code_examples"
KB_ANALYSIS_REPORTS = KB_SOURCES / "analysis_reports"

# Metadata file
METADATA_FILE = KB_ROOT / "metadata.json"

# Business concept patterns (for auto-tagging)
CONCEPT_PATTERNS = {
    'reserve_number': r'\breserve_number\b',
    'charter_id': r'\bcharter_id\b',
    'GST': r'\b(GST|gst|gross sales tax)\b',
    'HOS': r'\b(HOS|hours of service|cycle \d|160km exemption)\b',
    'WCB': r'\b(WCB|workers compensation|wcb_summary)\b',
    'T2': r'\bT2\b',
    'T4': r'\bT4\b',
    'PD7A': r'\bPD7A\b',
    'trial_balance': r'\btrial.?balance\b',
    'charter': r'\bcharter[s]?\b',
    'payment': r'\bpayment[s]?\b',
    'receipt': r'\breceipt[s]?\b',
    'banking': r'\bbanking|bank.transaction|CIBC|Scotia\b',
    'employee': r'\bemployee[s]?|driver[s]?|payroll\b',
    'vehicle': r'\bvehicle[s]?|fleet\b',
    'lms': r'\b(LMS|lms|legacy)\b',
}

# Table names (for auto-detection)
TABLE_NAMES = [
    'charters', 'payments', 'receipts', 'banking_transactions', 'employees', 
    'vehicles', 'employee_pay_master', 'pay_periods', 'wcb_summary', 
    'charter_driver_logs', 'unified_general_ledger', 'lms_rate_mapping',
    'clients', 'accounts', 'dispatches', 'invoice_ledger', 'vendor_invoices'
]


class KnowledgeBaseBuilder:
    def __init__(self):
        self.metadata = {}
        self.source_hashes = {}  # SHA256 hashes to detect changes
        
        # Create directory structure
        for path in [KB_DATABASE, KB_BUSINESS_RULES, KB_TAX_RULES, 
                     KB_SESSION_HISTORY, KB_CODE_EXAMPLES, KB_ANALYSIS_REPORTS]:
            path.mkdir(parents=True, exist_ok=True)
        
        # Load existing metadata
        if METADATA_FILE.exists():
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
                self.source_hashes = self.metadata.get('source_hashes', {})
    
    def compute_hash(self, filepath: Path) -> str:
        """Compute SHA256 hash of file for change detection"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def extract_concepts(self, content: str) -> List[str]:
        """Auto-detect business concepts in content"""
        concepts = set()
        for concept, pattern in CONCEPT_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                concepts.add(concept)
        return sorted(concepts)
    
    def extract_tables(self, content: str) -> List[str]:
        """Auto-detect table references in content"""
        tables = set()
        for table in TABLE_NAMES:
            if re.search(rf'\b{table}\b', content, re.IGNORECASE):
                tables.add(table)
        return sorted(tables)
    
    def determine_domain(self, filepath: Path, content: str) -> str:
        """Auto-determine domain from filename and content"""
        filename_lower = str(filepath).lower()
        content_lower = content.lower()
        
        if 'tax' in filename_lower or 't2' in filename_lower or 't4' in filename_lower:
            return 'tax'
        elif 'payroll' in filename_lower or 'employee_pay' in content_lower:
            return 'payroll'
        elif 'charter' in filename_lower or 'booking' in filename_lower:
            return 'charter'
        elif 'banking' in filename_lower or 'reconcil' in filename_lower:
            return 'banking'
        elif 'receipt' in filename_lower or 'vendor' in filename_lower:
            return 'receipt'
        elif 'vehicle' in filename_lower or 'fleet' in filename_lower:
            return 'fleet'
        elif 'employee' in filename_lower or 'driver' in filename_lower:
            return 'employee'
        else:
            return 'general'
    
    def determine_type(self, filepath: Path, content: str) -> str:
        """Auto-determine content type"""
        filename = filepath.name.lower()
        
        if 'schema' in filename or 'DATABASE_SCHEMA' in str(filepath):
            return 'schema'
        elif 'session' in filename:
            return 'session_log'
        elif filename.endswith('.py'):
            return 'code'
        elif 'audit' in filename or 'analysis' in filename:
            return 'analysis'
        elif 'copilot-instructions' in filename:
            return 'rule'
        elif 'fix' in filename or 'bug' in filename or 'crash' in filename.lower():
            return 'problem_solution'
        else:
            return 'documentation'
    
    def determine_priority(self, filepath: Path, content: str) -> str:
        """Determine retrieval priority"""
        filename = str(filepath).lower()
        
        # Critical sources (always retrieved first)
        if 'copilot-instructions' in filename:
            return 'critical'
        elif 'database_schema_reference' in filename:
            return 'critical'
        
        # High priority
        if 'session' in filename or 'current' in filename or 'urgent' in filename:
            return 'high'
        
        # Medium priority
        if 'audit' in filename or 'analysis' in filename or 'summary' in filename:
            return 'medium'
        
        # Low priority
        return 'low'
    
    def ingest_file(self, source_path: Path, dest_category: Path, 
                   force: bool = False) -> Dict:
        """Ingest single file into knowledge base with metadata"""
        
        # Check if file changed (skip if unchanged unless force=True)
        file_hash = self.compute_hash(source_path)
        file_key = str(source_path)
        
        if not force and file_key in self.source_hashes:
            if self.source_hashes[file_key] == file_hash:
                return None  # Skip unchanged file
        
        # Read content
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            print(f"  ⚠️  Skipping binary file: {source_path.name}")
            return None
        
        # Extract metadata
        concepts = self.extract_concepts(content)
        tables = self.extract_tables(content)
        domain = self.determine_domain(source_path, content)
        doc_type = self.determine_type(source_path, content)
        priority = self.determine_priority(source_path, content)
        
        # Copy to knowledge base
        dest_file = dest_category / source_path.name
        dest_file.write_text(content, encoding='utf-8')
        
        # Build metadata entry
        metadata_entry = {
            'source_path': str(source_path),
            'kb_path': str(dest_file.relative_to(KB_ROOT)),
            'size_bytes': len(content),
            'ingested_at': datetime.now().isoformat(),
            'modified_at': datetime.fromtimestamp(source_path.stat().st_mtime).isoformat(),
            'hash': file_hash,
            'domain': domain,
            'type': doc_type,
            'priority': priority,
            'concepts': concepts,
            'tables': tables,
            'line_count': content.count('\n') + 1,
        }
        
        # Update hash registry
        self.source_hashes[file_key] = file_hash
        
        return metadata_entry
    
    def ingest_database_schema(self):
        """Extract database schema from PostgreSQL information_schema"""
        print("\n📊 Extracting database schema...")
        
        try:
            conn = psycopg2.connect(
                host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
            )
            cur = conn.cursor(cursor_factory=DictCursor)
        except psycopg2.OperationalError as e:
            print(f"  ⚠️  Database connection failed: {e}")
            print(f"  ⚠️  Skipping database schema extraction (will use DATABASE_SCHEMA_REFERENCE.md instead)")
            return
        
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        
        schema_content = "# Database Schema (Auto-Generated)\n\n"
        schema_content += f"Generated: {datetime.now().isoformat()}\n\n"
        
        for table in tables:
            schema_content += f"## Table: {table}\n\n"
            
            # Get columns
            cur.execute("""
                SELECT column_name, data_type, character_maximum_length,
                       is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            
            schema_content += "| Column | Type | Nullable | Default |\n"
            schema_content += "|--------|------|----------|----------|\n"
            
            for col in cur.fetchall():
                col_type = col['data_type']
                if col['character_maximum_length']:
                    col_type += f"({col['character_maximum_length']})"
                
                schema_content += f"| {col['column_name']} | {col_type} | "
                schema_content += f"{col['is_nullable']} | {col['column_default'] or ''} |\n"
            
            # Get indexes
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = %s
            """, (table,))
            
            indexes = cur.fetchall()
            if indexes:
                schema_content += f"\n**Indexes ({len(indexes)}):**\n"
                for idx in indexes:
                    schema_content += f"- `{idx['indexname']}`\n"
            
            schema_content += "\n---\n\n"
        
        cur.close()
        conn.close()
        
        # Save schema
        schema_file = KB_DATABASE / "postgresql_schema_auto.md"
        schema_file.write_text(schema_content, encoding='utf-8')
        
        # Add to metadata
        self.metadata['database_schema'] = {
            'kb_path': str(schema_file.relative_to(KB_ROOT)),
            'generated_at': datetime.now().isoformat(),
            'table_count': len(tables),
            'type': 'schema',
            'priority': 'critical',
            'domain': 'database',
        }
        
        print(f"  ✅ Extracted {len(tables)} tables")
    
    def ingest_copilot_instructions(self):
        """Ingest main copilot instructions (critical business rules)"""
        print("\n📋 Ingesting copilot instructions...")
        
        copilot_file = Path(".github/copilot-instructions.md")
        if copilot_file.exists():
            meta = self.ingest_file(copilot_file, KB_BUSINESS_RULES, force=True)
            if meta:
                self.metadata['copilot_instructions'] = meta
                print(f"  ✅ {copilot_file.name} ({meta['line_count']} lines)")
        else:
            print(f"  ⚠️  File not found: {copilot_file}")
    
    def ingest_session_logs(self):
        """Ingest all SESSION_*.md files (historical context)"""
        print("\n📝 Ingesting session logs...")
        
        session_files = sorted(Path(".").glob("SESSION_*.md"))
        ingested_count = 0
        
        for session_file in session_files:
            meta = self.ingest_file(session_file, KB_SESSION_HISTORY)
            if meta:
                file_key = f"session_{session_file.stem}"
                self.metadata[file_key] = meta
                print(f"  ✅ {session_file.name}")
                ingested_count += 1
        
        print(f"  📊 Total: {ingested_count} session logs")
    
    def ingest_analysis_reports(self):
        """Ingest all analysis/audit MD files in root and additional folders"""
        print("\n📊 Ingesting analysis reports...")
        
        # Exclude session logs (already processed)
        md_files = [
            f for f in Path(".").glob("*.md") 
            if not f.name.startswith("SESSION_") 
            and not f.name.startswith(".")
        ]
        
        # Add files from "New folder" directory
        new_folder = Path("New folder")
        if new_folder.exists():
            print(f"  📁 Scanning 'New folder' for additional MD files...")
            new_folder_files = list(new_folder.glob("*.md"))
            md_files.extend(new_folder_files)
            print(f"  📁 Found {len(new_folder_files)} additional files")
        
        ingested_count = 0
        for md_file in md_files:
            meta = self.ingest_file(md_file, KB_ANALYSIS_REPORTS)
            if meta:
                file_key = f"report_{md_file.stem}"
                self.metadata[file_key] = meta
                ingested_count += 1
        
        print(f"  📊 Total: {ingested_count} analysis reports")
    
    def ingest_database_reference(self):
        """Ingest DATABASE_SCHEMA_REFERENCE.md (critical)"""
        print("\n📚 Ingesting database reference...")
        
        db_ref_file = Path("DATABASE_SCHEMA_REFERENCE.md")
        if db_ref_file.exists():
            meta = self.ingest_file(db_ref_file, KB_DATABASE, force=True)
            if meta:
                self.metadata['database_schema_reference'] = meta
                print(f"  ✅ {db_ref_file.name} ({meta['line_count']} lines)")
        else:
            print(f"  ⚠️  File not found: {db_ref_file}")
    
    def ingest_code_examples(self):
        """Ingest select Python scripts with business logic"""
        print("\n🐍 Ingesting code examples...")
        
        # Priority scripts with business logic
        priority_scripts = [
            "scripts/generate_t2_tax_summary.py",
            "scripts/generate_t2_return.py",
            "desktop_app/payroll_entry_widget.py",
            "desktop_app/driver_calendar_widget.py",
            "desktop_app/main.py",
        ]
        
        ingested_count = 0
        for script_path in priority_scripts:
            script_file = Path(script_path)
            if script_file.exists():
                meta = self.ingest_file(script_file, KB_CODE_EXAMPLES)
                if meta:
                    file_key = f"code_{script_file.stem}"
                    self.metadata[file_key] = meta
                    print(f"  ✅ {script_file.name}")
                    ingested_count += 1
        
        print(f"  📊 Total: {ingested_count} code examples")
    
    def save_metadata(self):
        """Save metadata inventory to JSON"""
        self.metadata['source_hashes'] = self.source_hashes
        self.metadata['last_updated'] = datetime.now().isoformat()
        self.metadata['total_sources'] = len([k for k in self.metadata.keys() if k not in ['source_hashes', 'last_updated', 'total_sources', 'statistics']])
        
        # Calculate statistics
        stats = {
            'by_domain': {},
            'by_type': {},
            'by_priority': {},
        }
        
        for key, meta in self.metadata.items():
            if key in ['source_hashes', 'last_updated', 'total_sources', 'statistics']:
                continue
            
            domain = meta.get('domain', 'unknown')
            doc_type = meta.get('type', 'unknown')
            priority = meta.get('priority', 'unknown')
            
            stats['by_domain'][domain] = stats['by_domain'].get(domain, 0) + 1
            stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1
            stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
        
        self.metadata['statistics'] = stats
        
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2)
        
        print(f"\n💾 Saved metadata: {METADATA_FILE}")
    
    def print_statistics(self):
        """Print knowledge base statistics"""
        stats = self.metadata.get('statistics', {})
        
        print("\n" + "=" * 60)
        print("KNOWLEDGE BASE STATISTICS")
        print("=" * 60)
        print(f"Total Sources: {self.metadata.get('total_sources', 0)}")
        print(f"Last Updated: {self.metadata.get('last_updated', 'N/A')}")
        
        print("\nBy Domain:")
        for domain, count in sorted(stats.get('by_domain', {}).items()):
            print(f"  {domain:15} {count:3} files")
        
        print("\nBy Type:")
        for doc_type, count in sorted(stats.get('by_type', {}).items()):
            print(f"  {doc_type:15} {count:3} files")
        
        print("\nBy Priority:")
        for priority, count in sorted(stats.get('by_priority', {}).items()):
            print(f"  {priority:15} {count:3} files")
        
        print("=" * 60)
    
    def rebuild(self):
        """Full rebuild of knowledge base"""
        print("🔨 REBUILDING KNOWLEDGE BASE")
        print("=" * 60)
        
        self.ingest_database_schema()
        self.ingest_copilot_instructions()
        self.ingest_database_reference()
        self.ingest_session_logs()
        self.ingest_analysis_reports()
        self.ingest_code_examples()
        
        self.save_metadata()
        self.print_statistics()
        
        print("\n✅ Knowledge base rebuild complete!")
    
    def update(self):
        """Incremental update (only changed files)"""
        print("🔄 UPDATING KNOWLEDGE BASE")
        print("=" * 60)
        
        # Re-check all sources (only ingest if changed)
        self.ingest_database_schema()
        self.ingest_copilot_instructions()
        self.ingest_database_reference()
        self.ingest_session_logs()
        self.ingest_analysis_reports()
        self.ingest_code_examples()
        
        self.save_metadata()
        self.print_statistics()
        
        print("\n✅ Knowledge base update complete!")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build AI Knowledge Base")
    parser.add_argument('--rebuild', action='store_true', help='Full rebuild (ignore hashes)')
    parser.add_argument('--update', action='store_true', help='Incremental update (only changed files)')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    
    args = parser.parse_args()
    
    builder = KnowledgeBaseBuilder()
    
    if args.stats:
        if METADATA_FILE.exists():
            builder.print_statistics()
        else:
            print("❌ No metadata found. Run --rebuild first.")
    elif args.update:
        builder.update()
    else:  # Default to rebuild
        builder.rebuild()


if __name__ == "__main__":
    main()
