#!/usr/bin/env python3
"""
Database Structure Analysis - Duplication, Merge Opportunities, Safety
Analyzes all 405 tables for:
1. Duplicate table structures (similar column sets)
2. Data duplication (same data in multiple tables)
3. Merge opportunities (tables that should be one)
4. Foreign key relationships and data integrity
5. Redundant columns across tables
"""

import psycopg2
from collections import defaultdict
import json
from datetime import datetime

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

class DatabaseStructureAnalyzer:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        self.cur = self.conn.cursor()
        self.results = {
            'similar_tables': [],
            'duplicate_data': [],
            'merge_opportunities': [],
            'redundant_columns': [],
            'foreign_keys': [],
            'missing_relationships': [],
            'safety_issues': []
        }
    
    def get_all_tables(self):
        """Get all table names"""
        self.cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row[0] for row in self.cur.fetchall()]
    
    def get_table_structure(self, table_name):
        """Get column names and types for a table"""
        self.cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        return [(row[0], row[1], row[2]) for row in self.cur.fetchall()]
    
    def get_table_row_count(self, table_name):
        """Get row count safely"""
        try:
            self.cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            return self.cur.fetchone()[0]
        except Exception as e:
            return None
    
    def find_similar_table_structures(self, tables):
        """Find tables with very similar column structures"""
        print("\n" + "="*80)
        print("ANALYZING: Similar Table Structures")
        print("="*80)
        
        table_structures = {}
        for table in tables:
            cols = self.get_table_structure(table)
            col_names = frozenset([col[0] for col in cols])
            table_structures[table] = {
                'columns': col_names,
                'column_list': [col[0] for col in cols],
                'full_structure': cols
            }
        
        # Find tables with >70% column overlap
        similar_groups = []
        checked = set()
        
        for table1 in tables:
            if table1 in checked:
                continue
            
            group = [table1]
            cols1 = table_structures[table1]['columns']
            
            for table2 in tables:
                if table2 == table1 or table2 in checked:
                    continue
                
                cols2 = table_structures[table2]['columns']
                overlap = len(cols1 & cols2)
                total = len(cols1 | cols2)
                
                if total > 0:
                    similarity = overlap / total
                    if similarity > 0.7:  # 70% similar
                        group.append(table2)
                        checked.add(table2)
            
            if len(group) > 1:
                similar_groups.append({
                    'tables': group,
                    'shared_columns': list(cols1 & table_structures[group[1]]['columns'])
                })
                checked.add(table1)
        
        self.results['similar_tables'] = similar_groups
        
        print(f"Found {len(similar_groups)} groups of similar tables")
        for i, group in enumerate(similar_groups, 1):
            print(f"\nGroup {i}: {len(group['tables'])} tables")
            for table in group['tables']:
                row_count = self.get_table_row_count(table)
                print(f"  - {table:<40} ({row_count or '?'} rows)")
            print(f"  Shared columns ({len(group['shared_columns'])}): {', '.join(group['shared_columns'][:5])}...")
    
    def find_duplicate_data_candidates(self, tables):
        """Find tables that might contain duplicate data"""
        print("\n" + "="*80)
        print("ANALYZING: Potential Duplicate Data")
        print("="*80)
        
        # Look for tables with same prefixes/suffixes
        table_families = defaultdict(list)
        
        for table in tables:
            # Group by common prefixes
            if '_' in table:
                prefix = table.split('_')[0]
                table_families[prefix].append(table)
        
        duplicate_candidates = []
        for prefix, family_tables in table_families.items():
            if len(family_tables) > 1:
                # Check if these tables have similar structures
                structures = {}
                for t in family_tables:
                    row_count = self.get_table_row_count(t)
                    cols = self.get_table_structure(t)
                    structures[t] = {
                        'columns': [c[0] for c in cols],
                        'row_count': row_count
                    }
                
                duplicate_candidates.append({
                    'prefix': prefix,
                    'tables': family_tables,
                    'structures': structures
                })
        
        self.results['duplicate_data'] = duplicate_candidates
        
        print(f"Found {len(duplicate_candidates)} table families")
        for family in duplicate_candidates[:10]:  # Show first 10
            print(f"\nFamily: {family['prefix']}_*")
            for table in family['tables']:
                info = family['structures'][table]
                print(f"  - {table:<40} ({info['row_count'] or '?':>6} rows, {len(info['columns']):>3} cols)")
    
    def check_foreign_key_relationships(self, tables):
        """Check for existing foreign keys and missing relationships"""
        print("\n" + "="*80)
        print("ANALYZING: Foreign Key Relationships")
        print("="*80)
        
        # Get existing foreign keys
        self.cur.execute("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """)
        
        fks = self.cur.fetchall()
        self.results['foreign_keys'] = [
            {
                'table': fk[0],
                'column': fk[1],
                'references_table': fk[2],
                'references_column': fk[3]
            }
            for fk in fks
        ]
        
        print(f"Found {len(fks)} existing foreign key constraints")
        
        # Look for potential missing foreign keys (columns ending in _id)
        missing_fks = []
        for table in tables[:100]:  # Check first 100 tables
            cols = self.get_table_structure(table)
            for col_name, col_type, _ in cols:
                if col_name.endswith('_id') and col_type in ('integer', 'bigint'):
                    # Check if FK exists
                    has_fk = any(
                        fk['table'] == table and fk['column'] == col_name 
                        for fk in self.results['foreign_keys']
                    )
                    if not has_fk:
                        # Try to find matching table
                        potential_table = col_name[:-3] + 's'  # e.g., client_id -> clients
                        if potential_table in tables:
                            missing_fks.append({
                                'table': table,
                                'column': col_name,
                                'likely_references': potential_table
                            })
        
        self.results['missing_relationships'] = missing_fks
        print(f"Found {len(missing_fks)} potential missing foreign keys (first 100 tables)")
    
    def find_merge_opportunities(self):
        """Identify tables that should potentially be merged"""
        print("\n" + "="*80)
        print("ANALYZING: Merge Opportunities")
        print("="*80)
        
        merge_opportunities = []
        
        # Check similar tables from earlier analysis
        for group in self.results['similar_tables']:
            if len(group['tables']) == 2:
                table1, table2 = group['tables']
                count1 = self.get_table_row_count(table1)
                count2 = self.get_table_row_count(table2)
                
                # If both tables small and very similar, consider merging
                if count1 is not None and count2 is not None:
                    if count1 < 1000 and count2 < 1000:
                        merge_opportunities.append({
                            'tables': [table1, table2],
                            'reason': 'Similar structure, both small (<1000 rows)',
                            'rows': [count1, count2],
                            'recommendation': f'Consider merging into single table with type/category column'
                        })
        
        # Check for staging/production duplicates
        for family in self.results['duplicate_data']:
            staging_tables = [t for t in family['tables'] if 'staging' in t or 'temp' in t or 'old' in t]
            active_tables = [t for t in family['tables'] if t not in staging_tables]
            
            if staging_tables and active_tables:
                for staging in staging_tables:
                    count = family['structures'][staging]['row_count']
                    if count == 0:
                        merge_opportunities.append({
                            'tables': [staging],
                            'reason': f'Empty staging/temp table (0 rows)',
                            'rows': [0],
                            'recommendation': f'Consider dropping if no longer needed'
                        })
        
        self.results['merge_opportunities'] = merge_opportunities
        
        print(f"Found {len(merge_opportunities)} merge/cleanup opportunities")
        for i, opp in enumerate(merge_opportunities[:10], 1):
            print(f"\n{i}. {' + '.join(opp['tables'])}")
            print(f"   Reason: {opp['reason']}")
            print(f"   Recommendation: {opp['recommendation']}")
    
    def check_data_safety(self, tables):
        """Check for data safety concerns"""
        print("\n" + "="*80)
        print("ANALYZING: Data Safety Concerns")
        print("="*80)
        
        safety_issues = []
        
        # Check for tables without primary keys
        for table in tables[:100]:
            self.cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE table_name = %s AND constraint_type = 'PRIMARY KEY'
            """, (table,))
            
            has_pk = self.cur.fetchone()[0] > 0
            if not has_pk:
                row_count = self.get_table_row_count(table)
                if row_count and row_count > 0:
                    safety_issues.append({
                        'table': table,
                        'issue': 'No PRIMARY KEY',
                        'severity': 'HIGH' if row_count > 100 else 'MEDIUM',
                        'rows': row_count
                    })
        
        # Check for nullable columns that should probably be NOT NULL
        critical_columns = ['id', 'created_at', 'updated_at', 'status']
        for table in tables[:50]:
            cols = self.get_table_structure(table)
            for col_name, col_type, is_nullable in cols:
                if any(crit in col_name.lower() for crit in critical_columns):
                    if is_nullable == 'YES':
                        safety_issues.append({
                            'table': table,
                            'issue': f'Critical column {col_name} allows NULL',
                            'severity': 'MEDIUM',
                            'column': col_name
                        })
        
        self.results['safety_issues'] = safety_issues
        
        print(f"Found {len(safety_issues)} safety concerns")
        for issue in safety_issues[:10]:
            print(f"  [{issue['severity']}] {issue['table']}: {issue['issue']}")
    
    def generate_report(self):
        """Generate comprehensive report"""
        print("\n" + "="*80)
        print("GENERATING REPORT")
        print("="*80)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"L:/limo/reports/database_structure_analysis_{timestamp}.json"
        summary_file = f"L:/limo/reports/database_structure_summary_{timestamp}.txt"
        
        # Save JSON report
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Generate text summary
        summary = []
        summary.append("=" * 80)
        summary.append("DATABASE STRUCTURE ANALYSIS SUMMARY")
        summary.append("=" * 80)
        summary.append(f"Generated: {datetime.now()}")
        summary.append("")
        
        summary.append(f"Similar Table Groups: {len(self.results['similar_tables'])}")
        summary.append(f"Table Families: {len(self.results['duplicate_data'])}")
        summary.append(f"Existing Foreign Keys: {len(self.results['foreign_keys'])}")
        summary.append(f"Missing Foreign Keys: {len(self.results['missing_relationships'])}")
        summary.append(f"Merge Opportunities: {len(self.results['merge_opportunities'])}")
        summary.append(f"Safety Issues: {len(self.results['safety_issues'])}")
        summary.append("")
        
        summary.append("="*80)
        summary.append("TOP RECOMMENDATIONS")
        summary.append("="*80)
        summary.append("")
        
        # Top merge opportunities
        summary.append("1. MERGE/CLEANUP OPPORTUNITIES:")
        for i, opp in enumerate(self.results['merge_opportunities'][:5], 1):
            summary.append(f"   {i}. {' + '.join(opp['tables'])}")
            summary.append(f"      {opp['recommendation']}")
        summary.append("")
        
        # Top safety issues
        summary.append("2. SAFETY CONCERNS:")
        high_severity = [s for s in self.results['safety_issues'] if s['severity'] == 'HIGH']
        for i, issue in enumerate(high_severity[:5], 1):
            summary.append(f"   {i}. {issue['table']}: {issue['issue']}")
        summary.append("")
        
        # Similar tables
        summary.append("3. SIMILAR TABLE GROUPS (potential duplicates):")
        for i, group in enumerate(self.results['similar_tables'][:5], 1):
            summary.append(f"   {i}. {', '.join(group['tables'])}")
        summary.append("")
        
        summary_text = "\n".join(summary)
        
        with open(summary_file, 'w') as f:
            f.write(summary_text)
        
        print(summary_text)
        print(f"\n✅ Full report: {report_file}")
        print(f"✅ Summary: {summary_file}")
        
        return summary_text

def main():
    analyzer = DatabaseStructureAnalyzer()
    
    tables = analyzer.get_all_tables()
    print(f"\n📊 Analyzing {len(tables)} tables for duplication and merge opportunities...\n")
    
    # Run all analyses
    analyzer.find_similar_table_structures(tables)
    analyzer.find_duplicate_data_candidates(tables)
    analyzer.check_foreign_key_relationships(tables)
    analyzer.find_merge_opportunities()
    analyzer.check_data_safety(tables)
    
    # Generate report
    analyzer.generate_report()
    
    analyzer.cur.close()
    analyzer.conn.close()

if __name__ == "__main__":
    main()
