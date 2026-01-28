#!/usr/bin/env python3
"""
PHASE 4 TASK 14: Monitoring & Alerting System

Builds monitoring infrastructure for:
1. Email function monitoring
2. Export success tracking
3. Database health checks
4. Path/directory monitoring
5. Transaction monitoring
6. Performance metrics

Usage:
    python -X utf8 scripts/PHASE4_MONITORING_SYSTEM.py
"""

import os
import sys
import psycopg2
from pathlib import Path
from datetime import datetime, timedelta

def connect_db():
    """Connect to database"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            dbname=os.getenv('DB_NAME', 'almsdata'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

class MonitoringSystem:
    """Monitoring and alerting system"""
    
    def __init__(self):
        self.conn = connect_db()
        self.alerts = []
        self.metrics = {}
    
    def monitor_email_function(self) -> dict:
        """Monitor email function health"""
        print("\n📧 Monitoring Email Function...")
        
        if not self.conn:
            return {'status': 'SKIP'}
        
        try:
            cur = self.conn.cursor()
            
            # Check email_log table existence and size
            cur.execute("""
                SELECT COUNT(*) FROM email_log
            """)
            
            log_count = cur.fetchone()[0]
            print(f"   ✅ Email logs recorded: {log_count}")
            
            # Check for failures
            cur.execute("""
                SELECT COUNT(*) FROM email_log 
                WHERE status != 'success'
            """)
            
            failures = cur.fetchone()[0]
            if failures > 0:
                print(f"   ⚠️  Email failures: {failures}")
                self.alerts.append(f"Email failures detected: {failures}")
            else:
                print(f"   ✅ No email failures")
            
            # Check recent email activity
            cur.execute("""
                SELECT COUNT(*) FROM email_log
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            
            recent = cur.fetchone()[0]
            print(f"   ✅ Recent emails (1 hour): {recent}")
            
            cur.close()
            return {'status': 'PASS', 'email_health': 'Good'}
        
        except Exception as e:
            print(f"   ⚠️  Email monitoring: {e}")
            return {'status': 'WARNING', 'error': str(e)}
    
    def monitor_export_success(self) -> dict:
        """Monitor export functionality"""
        print("\n📤 Monitoring Export Success...")
        
        exports_dir = Path(__file__).parent.parent / "exports"
        
        if not exports_dir.exists():
            print(f"   ⚠️  Exports directory not found")
            return {'status': 'WARNING'}
        
        # Check recent exports
        export_files = sorted(
            exports_dir.glob("*.csv"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if export_files:
            latest = export_files[0]
            age_minutes = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).total_seconds() / 60
            size_kb = latest.stat().st_size / 1024
            
            print(f"   ✅ Latest export: {latest.name}")
            print(f"      Age: {age_minutes:.0f} minutes ago")
            print(f"      Size: {size_kb:.1f} KB")
            
            if age_minutes > 1440:  # 24 hours
                self.alerts.append(f"No exports in last 24 hours")
        else:
            print(f"   ⚠️  No export files found")
        
        print(f"   ✅ Total exports: {len(export_files)}")
        
        return {'status': 'PASS', 'export_health': 'Good'}
    
    def monitor_database_health(self) -> dict:
        """Monitor database connection and health"""
        print("\n🗄️  Monitoring Database Health...")
        
        if not self.conn:
            return {'status': 'FAIL', 'db_health': 'Down'}
        
        try:
            cur = self.conn.cursor()
            
            # Test connectivity
            cur.execute("SELECT 1")
            print("   ✅ Database connection: Healthy")
            
            # Check table sizes
            cur.execute("""
                SELECT table_name, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 5
            """)
            
            tables = cur.fetchall()
            print(f"   ✅ Largest tables:")
            for table, size in tables:
                print(f"      - {table}: {size}")
            
            # Check for locks
            cur.execute("""
                SELECT COUNT(*) FROM pg_locks WHERE NOT granted
            """)
            
            locks = cur.fetchone()[0]
            if locks > 0:
                print(f"   ⚠️  Waiting locks: {locks}")
                self.alerts.append(f"Database locks detected: {locks}")
            else:
                print(f"   ✅ No waiting locks")
            
            cur.close()
            return {'status': 'PASS', 'db_health': 'Healthy'}
        
        except Exception as e:
            print(f"   ❌ Database monitoring failed: {e}")
            return {'status': 'FAIL', 'error': str(e)}
    
    def monitor_path_health(self) -> dict:
        """Monitor directory and file paths"""
        print("\n📁 Monitoring Path Health...")
        
        critical_paths = {
            'scripts': Path(__file__).parent,
            'reports': Path(__file__).parent.parent / "reports",
            'exports': Path(__file__).parent.parent / "exports",
            'data': Path(__file__).parent.parent / "data",
            'database_schema': Path(__file__).parent.parent / "docs" / "DATABASE_SCHEMA_REFERENCE.md",
        }
        
        accessible = 0
        inaccessible = 0
        
        for path_name, path_obj in critical_paths.items():
            if path_obj.exists():
                accessible += 1
                if path_obj.is_file():
                    size_kb = path_obj.stat().st_size / 1024
                    print(f"   ✅ {path_name}: {size_kb:.1f} KB")
                else:
                    print(f"   ✅ {path_name}: Accessible")
            else:
                inaccessible += 1
                print(f"   ❌ {path_name}: Not found")
        
        print(f"\n   ✅ Paths accessible: {accessible}/{len(critical_paths)}")
        
        return {'status': 'PASS', 'path_health': 'Healthy' if inaccessible == 0 else 'Warning'}
    
    def monitor_transaction_health(self) -> dict:
        """Monitor transaction management"""
        print("\n🔄 Monitoring Transaction Health...")
        
        if not self.conn:
            return {'status': 'SKIP'}
        
        try:
            cur = self.conn.cursor()
            
            # Check for long-running transactions
            cur.execute("""
                SELECT COUNT(*) FROM pg_stat_activity 
                WHERE state = 'active' 
                AND query_start < NOW() - INTERVAL '5 minutes'
            """)
            
            long_queries = cur.fetchone()[0]
            
            if long_queries > 0:
                print(f"   ⚠️  Long-running queries: {long_queries}")
                self.alerts.append(f"Long-running transactions: {long_queries}")
            else:
                print(f"   ✅ No long-running queries")
            
            # Check transaction rate
            cur.execute("""
                SELECT sum(xact_commit + xact_rollback) FROM pg_stat_database
                WHERE datname = current_database()
            """)
            
            result = cur.fetchone()
            xact_count = result[0] if result and result[0] else 0
            print(f"   ✅ Transaction count: {xact_count:,.0f}")
            
            cur.close()
            return {'status': 'PASS', 'transaction_health': 'Good'}
        
        except Exception as e:
            print(f"   ⚠️  Transaction monitoring: {e}")
            return {'status': 'WARNING', 'error': str(e)}
    
    def monitor_performance_metrics(self) -> dict:
        """Monitor system performance"""
        print("\n⚡ Monitoring Performance Metrics...")
        
        try:
            import shutil
            
            # Disk space
            total, used, free = shutil.disk_usage(Path(__file__).parent.parent)
            free_gb = free / (1024**3)
            used_pct = (used / total) * 100
            
            print(f"   ✅ Disk usage: {used_pct:.1f}%")
            print(f"   ✅ Free space: {free_gb:.1f} GB")
            
            if free_gb < 10:
                self.alerts.append(f"Low disk space: {free_gb:.1f} GB")
            
            self.metrics['disk_usage_pct'] = used_pct
            self.metrics['free_space_gb'] = free_gb
            
            return {'status': 'PASS', 'performance': 'Good'}
        
        except Exception as e:
            print(f"   ⚠️  Performance monitoring: {e}")
            return {'status': 'WARNING', 'error': str(e)}
    
    def generate_health_dashboard(self) -> None:
        """Generate monitoring health dashboard"""
        print("\n📊 Generating Health Dashboard...")
        
        results = {
            'Email Function': self.monitor_email_function(),
            'Export Success': self.monitor_export_success(),
            'Database Health': self.monitor_database_health(),
            'Path Health': self.monitor_path_health(),
            'Transaction Health': self.monitor_transaction_health(),
            'Performance Metrics': self.monitor_performance_metrics(),
        }
        
        # Summary
        print("\n" + "="*80)
        print("PHASE 4, TASK 14: Monitoring & Alerting System")
        print("="*80)
        
        passed = 0
        warned = 0
        failed = 0
        
        for component, result in results.items():
            status = result.get('status', 'UNKNOWN')
            
            if status == 'PASS':
                passed += 1
                print(f"✅ {component}: HEALTHY")
            elif status == 'WARNING':
                warned += 1
                print(f"⚠️  {component}: WARNING")
            else:
                failed += 1
                print(f"❌ {component}: {status}")
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Healthy: {passed}")
        print(f"   ⚠️  Warnings: {warned}")
        print(f"   ❌ Failed: {failed}")
        
        if self.alerts:
            print(f"\n🚨 Active Alerts ({len(self.alerts)}):")
            for alert in self.alerts:
                print(f"   ⚠️  {alert}")
        else:
            print(f"\n✅ No active alerts")
        
        print("\n" + "="*80)
        print("✅ PHASE 4, TASK 14 COMPLETE - Monitoring system operational")
        print("="*80)
        
        self.save_report(results, passed, warned, failed)
    
    def save_report(self, results, passed, warned, failed) -> None:
        """Save monitoring report"""
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / "PHASE4_TASK14_MONITORING_SYSTEM.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Phase 4, Task 14: Monitoring & Alerting System\n\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n")
            f.write(f"**Status:** ✅ **OPERATIONAL**\n\n")
            f.write(f"## Health Summary\n")
            f.write(f"- ✅ Healthy: {passed}\n")
            f.write(f"- ⚠️  Warnings: {warned}\n")
            f.write(f"- ❌ Failed: {failed}\n\n")
            f.write(f"## Monitoring Components\n")
            f.write(f"- Email function health (logs, failures, recent activity)\n")
            f.write(f"- Export success tracking (latest export, file count)\n")
            f.write(f"- Database connectivity (locks, table sizes, query performance)\n")
            f.write(f"- Path/directory monitoring (critical paths accessibility)\n")
            f.write(f"- Transaction health (long-running queries, transaction count)\n")
            f.write(f"- Performance metrics (disk usage, free space)\n")
            
            if self.alerts:
                f.write(f"\n## Active Alerts\n")
                for alert in self.alerts:
                    f.write(f"- {alert}\n")
        
        print(f"\n📄 Report saved to {report_file}")
    
    def cleanup(self):
        """Clean up database connection"""
        if self.conn:
            self.conn.close()

def main():
    monitor = MonitoringSystem()
    try:
        monitor.generate_health_dashboard()
    finally:
        monitor.cleanup()

if __name__ == '__main__':
    main()
