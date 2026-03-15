#!/usr/bin/env python3
"""
Comprehensive Database Relationship Analyzer
===========================================

Analyzes the Arrow Limousine PostgreSQL database to:
1. Map all table relationships through foreign keys
2. Identify payment types and sources (Square, multi-charter, etc.)
3. Validate data integrity across related tables
4. Generate comprehensive data inventory

Usage:
    python scripts/analyze_database_relationships.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import json
from collections import defaultdict

load_dotenv()

PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

class DatabaseRelationshipAnalyzer:
    def __init__(self):
        self.relationships = {}
        self.table_stats = {}
        self.payment_analysis = {}
        
    def connect(self):
        """Connect to PostgreSQL database"""
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = True
        return conn
    
    def analyze_foreign_keys(self):
        """Analyze all foreign key relationships"""
        print("🔗 ANALYZING FOREIGN KEY RELATIONSHIPS")
        print("=" * 50)
        
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all foreign key constraints
                cur.execute("""
                    SELECT 
                        tc.table_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        tc.constraint_name
                    FROM 
                        information_schema.table_constraints AS tc 
                        JOIN information_schema.key_column_usage AS kcu
                          ON tc.constraint_name = kcu.constraint_name
                          AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage AS ccu
                          ON ccu.constraint_name = tc.constraint_name
                          AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_schema = 'public'
                    ORDER BY tc.table_name, kcu.column_name
                """)
                
                relationships = defaultdict(list)
                for row in cur.fetchall():
                    relationships[row['table_name']].append({
                        'column': row['column_name'],
                        'references_table': row['foreign_table_name'],
                        'references_column': row['foreign_column_name'],
                        'constraint_name': row['constraint_name']
                    })
                
                self.relationships = dict(relationships)
                
                # Print relationships
                for table, refs in self.relationships.items():
                    print(f"\n📋 {table.upper()}:")
                    for ref in refs:
                        print(f"   {ref['column']} → {ref['references_table']}.{ref['references_column']}")
    
    def analyze_table_statistics(self):
        """Get record counts and basic statistics for all tables"""
        print("\n\n📊 TABLE STATISTICS")
        print("=" * 50)
        
        with self.connect() as conn:
            with conn.cursor() as cur:
                # Get all tables
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                
                tables = [row[0] for row in cur.fetchall()]
                
                for table in tables:
                    try:
                        # Get record count
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cur.fetchone()[0]
                        
                        # Get latest update if has timestamp column
                        latest_update = None
                        for timestamp_col in ['updated_at', 'created_at', 'date_modified', 'last_updated']:
                            try:
                                cur.execute(f"SELECT MAX({timestamp_col}) FROM {table}")
                                latest_update = cur.fetchone()[0]
                                if latest_update:
                                    break
                            except:
                                continue
                        
                        self.table_stats[table] = {
                            'count': count,
                            'latest_update': latest_update
                        }
                        
                        if count > 0:
                            update_str = f" (Latest: {latest_update})" if latest_update else ""
                            print(f"   {table:<35} {count:>8,} records{update_str}")
                        
                    except Exception as e:
                        print(f"   {table:<35} ERROR: {e}")
    
    def analyze_core_relationships(self):
        """Analyze core business relationships: clients → charters → payments"""
        print("\n\n🎯 CORE BUSINESS RELATIONSHIPS")
        print("=" * 50)
        
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Clients analysis
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_clients,
                        COUNT(DISTINCT account_number) as unique_accounts,
                        COUNT(DISTINCT company_name) as unique_companies
                    FROM clients
                """)
                client_stats = cur.fetchone()
                print(f"👥 CLIENTS: {client_stats['total_clients']:,} total")
                print(f"   • {client_stats['unique_accounts']:,} unique account numbers")
                print(f"   • {client_stats['unique_companies']:,} unique company names")
                
                # Charters analysis
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_charters,
                        COUNT(DISTINCT client_id) as clients_with_charters,
                        COUNT(DISTINCT reserve_number) as unique_reserves,
                        SUM(rate) as total_charter_value,
                        AVG(rate) as avg_charter_value,
                        COUNT(CASE WHEN client_id IS NULL THEN 1 END) as orphaned_charters
                    FROM charters
                """)
                charter_stats = cur.fetchone()
                print(f"\n🚗 CHARTERS: {charter_stats['total_charters']:,} total")
                print(f"   • {charter_stats['unique_reserves']:,} unique reservation numbers")
                print(f"   • {charter_stats['clients_with_charters']:,} clients with charters")
                print(f"   • ${charter_stats['total_charter_value']:,.2f} total charter value")
                print(f"   • ${charter_stats['avg_charter_value']:.2f} average charter value")
                if charter_stats['orphaned_charters'] > 0:
                    print(f"   [WARN]  {charter_stats['orphaned_charters']:,} charters without client_id")
                
                # Payments analysis
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_payments,
                        COUNT(DISTINCT payment_method) as payment_methods,
                        SUM(amount) as total_payment_amount,
                        AVG(amount) as avg_payment_amount,
                        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as linked_to_charters,
                        COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as unlinked_payments
                    FROM payments
                """)
                payment_stats = cur.fetchone()
                print(f"\n💰 PAYMENTS: {payment_stats['total_payments']:,} total")
                print(f"   • {payment_stats['payment_methods']:,} different payment methods")
                print(f"   • ${payment_stats['total_payment_amount']:,.2f} total payment amount")
                print(f"   • ${payment_stats['avg_payment_amount']:.2f} average payment amount")
                print(f"   • {payment_stats['linked_to_charters']:,} linked to charters")
                if payment_stats['unlinked_payments'] > 0:
                    print(f"   [WARN]  {payment_stats['unlinked_payments']:,} unlinked payments")
    
    def analyze_payment_methods(self):
        """Detailed analysis of payment methods and sources"""
        print("\n\n💳 PAYMENT METHOD ANALYSIS")
        print("=" * 50)
        
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                # Payment methods breakdown
                cur.execute("""
                    SELECT 
                        payment_method,
                        COUNT(*) as count,
                        SUM(amount) as total_amount,
                        AVG(amount) as avg_amount,
                        MIN(payment_date) as earliest_date,
                        MAX(payment_date) as latest_date
                    FROM payments 
                    WHERE payment_method IS NOT NULL
                    GROUP BY payment_method
                    ORDER BY count DESC
                """)
                
                payment_methods = cur.fetchall()
                print("📊 Payment Methods Breakdown:")
                for pm in payment_methods:
                    print(f"   {pm['payment_method']:<20} {pm['count']:>6,} payments | ${pm['total_amount']:>12,.2f} | Avg: ${pm['avg_amount']:>7.2f}")
                
                # Square payments analysis
                print(f"\n💠 SQUARE PAYMENTS ANALYSIS:")
                cur.execute("""
                    SELECT 
                        COUNT(*) as square_payments,
                        SUM(amount) as square_total,
                        COUNT(DISTINCT square_customer_name) as unique_customers,
                        COUNT(CASE WHEN square_transaction_id IS NOT NULL THEN 1 END) as with_transaction_id,
                        COUNT(CASE WHEN square_card_brand IS NOT NULL THEN 1 END) as with_card_info
                    FROM payments 
                    WHERE payment_method ILIKE '%square%' OR square_transaction_id IS NOT NULL
                """)
                square_stats = cur.fetchone()
                if square_stats['square_payments'] > 0:
                    print(f"   • {square_stats['square_payments']:,} Square payments")
                    print(f"   • ${square_stats['square_total']:,.2f} total Square revenue")
                    print(f"   • {square_stats['unique_customers']:,} unique Square customers")
                    print(f"   • {square_stats['with_transaction_id']:,} with transaction IDs")
                    print(f"   • {square_stats['with_card_info']:,} with card brand info")
                
                # Multi-charter payments
                print(f"\n🔄 MULTI-CHARTER PAYMENTS:")
                cur.execute("""
                    SELECT 
                        payment_key,
                        COUNT(DISTINCT charter_id) as charter_count,
                        SUM(amount) as total_amount,
                        STRING_AGG(DISTINCT reserve_number, ', ') as reserve_numbers
                    FROM payments 
                    WHERE payment_key IS NOT NULL AND charter_id IS NOT NULL
                    GROUP BY payment_key
                    HAVING COUNT(DISTINCT charter_id) > 1
                    ORDER BY charter_count DESC
                    LIMIT 10
                """)
                multi_charter = cur.fetchall()
                if multi_charter:
                    print(f"   Found {len(multi_charter)} payment keys covering multiple charters:")
                    for mc in multi_charter[:5]:
                        print(f"   • Payment {mc['payment_key']}: {mc['charter_count']} charters | ${mc['total_amount']:,.2f}")
                
                # E-transfer analysis
                print(f"\n📧 E-TRANSFER ANALYSIS:")
                cur.execute("""
                    SELECT 
                        COUNT(*) as etransfer_count,
                        SUM(amount) as etransfer_total,
                        COUNT(DISTINCT reference_number) as unique_references,
                        COUNT(CASE WHEN square_customer_name IS NOT NULL THEN 1 END) as linked_to_square
                    FROM payments 
                    WHERE payment_method ILIKE '%transfer%' OR payment_method ILIKE '%interac%'
                """)
                etransfer_stats = cur.fetchone()
                if etransfer_stats['etransfer_count'] > 0:
                    print(f"   • {etransfer_stats['etransfer_count']:,} e-transfer payments")
                    print(f"   • ${etransfer_stats['etransfer_total']:,.2f} total e-transfer amount")
                    print(f"   • {etransfer_stats['unique_references']:,} unique reference numbers")
                    print(f"   • {etransfer_stats['linked_to_square']:,} linked to Square customers")
    
    def analyze_data_quality(self):
        """Analyze data quality and integrity issues"""
        print("\n\n🔍 DATA QUALITY ANALYSIS")
        print("=" * 50)
        
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                
                issues = []
                
                # Orphaned charters (no client_id)
                cur.execute("SELECT COUNT(*) FROM charters WHERE client_id IS NULL")
                result = cur.fetchone()
                orphaned_charters = result[0] if result else 0
                if orphaned_charters > 0:
                    issues.append(f"🔴 {orphaned_charters:,} charters without client_id")
                
                # Unlinked payments (no charter_id)
                cur.execute("SELECT COUNT(*) FROM payments WHERE charter_id IS NULL AND reserve_number IS NOT NULL")
                result = cur.fetchone()
                unlinked_payments = result[0] if result else 0
                if unlinked_payments > 0:
                    issues.append(f"🟡 {unlinked_payments:,} payments with reserve_number but no charter_id")
                
                # Duplicate reserve numbers
                cur.execute("""
                    SELECT reserve_number, COUNT(*) as count 
                    FROM charters 
                    WHERE reserve_number IS NOT NULL 
                    GROUP BY reserve_number 
                    HAVING COUNT(*) > 1
                """)
                duplicate_reserves = cur.fetchall()
                if duplicate_reserves:
                    issues.append(f"🟠 {len(duplicate_reserves)} duplicate reserve numbers")
                
                # Missing payment amounts
                cur.execute("SELECT COUNT(*) FROM payments WHERE amount IS NULL OR amount = 0")
                result = cur.fetchone()
                zero_payments = result[0] if result else 0
                if zero_payments > 0:
                    issues.append(f"🟡 {zero_payments:,} payments with zero or null amounts")
                
                # Print issues
                if issues:
                    print("[WARN]  Data Quality Issues Found:")
                    for issue in issues:
                        print(f"   {issue}")
                else:
                    print("[OK] No major data quality issues detected")
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report"""
        print("\n\n📋 COMPREHENSIVE SUMMARY REPORT")
        print("=" * 60)
        
        # Key metrics
        total_tables = len(self.table_stats)
        tables_with_data = len([t for t, stats in self.table_stats.items() if stats['count'] > 0])
        total_relationships = sum(len(refs) for refs in self.relationships.values())
        
        print(f"🗄️  DATABASE OVERVIEW:")
        print(f"   • {total_tables} total tables")
        print(f"   • {tables_with_data} tables with data")
        print(f"   • {total_relationships} foreign key relationships")
        
        # Core business data
        clients_count = self.table_stats.get('clients', {}).get('count', 0)
        charters_count = self.table_stats.get('charters', {}).get('count', 0)
        payments_count = self.table_stats.get('payments', {}).get('count', 0)
        
        print(f"\n📊 CORE BUSINESS DATA:")
        print(f"   • {clients_count:,} clients")
        print(f"   • {charters_count:,} charter reservations")
        print(f"   • {payments_count:,} payment transactions")
        
        # Major supporting tables
        major_tables = [
            ('employees', 'Staff and drivers'),
            ('vehicles', 'Fleet vehicles'),
            ('receipts', 'Business receipts'),
            ('banking_transactions', 'Bank transactions'),
            ('email_financial_events', 'Email-derived financial events')
        ]
        
        print(f"\n🏢 SUPPORTING DATA:")
        for table, description in major_tables:
            count = self.table_stats.get(table, {}).get('count', 0)
            if count > 0:
                print(f"   • {count:,} {description.lower()}")
    
    def main(self):
        """Run complete analysis"""
        print("🔍 ARROW LIMOUSINE DATABASE RELATIONSHIP ANALYZER")
        print("=" * 60)
        
        try:
            self.analyze_foreign_keys()
            self.analyze_table_statistics()
            self.analyze_core_relationships()
            self.analyze_payment_methods()
            self.analyze_data_quality()
            self.generate_summary_report()
            
            print(f"\n[OK] Analysis completed successfully!")
            
        except Exception as e:
            print(f"[FAIL] Analysis failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    analyzer = DatabaseRelationshipAnalyzer()
    analyzer.main()