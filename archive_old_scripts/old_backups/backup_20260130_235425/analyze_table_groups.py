#!/usr/bin/env python3
"""
Analyze tables by logical groups.
Check dependencies, usage, and provide recommendations.
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def get_table_info(conn, table_name):
    """Get comprehensive table information."""
    cur = conn.cursor()
    
    # Row count
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]
    
    # Size
    cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('public.{table_name}'))")
    size = cur.fetchone()[0]
    
    # Columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    columns = cur.fetchall()
    
    # Foreign keys (outgoing)
    cur.execute("""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = %s
    """, (table_name,))
    foreign_keys = cur.fetchall()
    
    # Referenced by (incoming foreign keys)
    cur.execute("""
        SELECT
            tc.table_name AS referencing_table,
            kcu.column_name AS referencing_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = %s
    """, (table_name,))
    referenced_by = cur.fetchall()
    
    # Views that depend on this table
    cur.execute("""
        SELECT DISTINCT v.table_name as view_name
        FROM information_schema.view_table_usage v
        WHERE v.view_schema = 'public'
          AND v.table_name = %s
    """, (table_name,))
    dependent_views = cur.fetchall()
    
    return {
        'row_count': row_count,
        'size': size,
        'columns': columns,
        'foreign_keys': foreign_keys,
        'referenced_by': referenced_by,
        'dependent_views': dependent_views
    }


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Define table groups for analysis
    groups = {
        'Charter Related': [
            'charter_charges', 'charter_credit_ledger', 'charter_driver_logs',
            'charter_payments', 'charter_reconciliation_status', 'charter_refunds',
            'charter_routes', 'charter_run_types', 'charter_time_updates',
            'charity_trade_charters', 'excluded_charters', 'orphaned_charges_archive',
            'unified_charge_lookup'
        ],
        'Employee/Driver': [
            'driver_alias_map', 'driver_employee_mapping', 'driver_name_employee_map',
            'driver_floats', 'chauffeur_float_tracking', 'chauffeur_pay_entries',
            'driver_pay_entries', 'employee_pay_entries', 'paul_pay_tracking',
            'non_charter_payroll', 'monthly_work_assignments'
        ],
        'Vehicle': [
            'vehicle_financing', 'vehicle_financing_complete', 'vehicle_fuel_log',
            'vehicle_insurance', 'vehicle_loan_payments', 'vehicle_loan_reconciliation_allocations',
            'vehicle_loans', 'vehicle_mileage_log', 'vehicle_purchases',
            'vehicle_repossessions', 'vehicle_sales', 'vehicle_writeoffs',
            'david_richard_vehicle_loans', 'cra_vehicle_events'
        ],
        'Banking/Reconciliation': [
            'banking_inter_account_transfers', 'banking_payment_links',
            'banking_receipt_matching_ledger', 'bank_reconciliation',
            'etransfer_banking_reconciliation', 'square_etransfer_reconciliation',
            'batch_deposit_allocations', 'deposit_records'
        ],
        'E-Transfer': [
            'etransfer_transactions', 'etransfers_processed', 'etransfer_accounting_assessment',
            'etransfer_analysis_results', 'etransfer_fix_final_results'
        ],
        'Square': [
            'square_capital_activity', 'square_capital_loans', 'square_customers',
            'square_loan_payments', 'square_payment_categories', 'square_payouts',
            'square_processing_fees', 'square_review_status', 'square_validation_summary'
        ],
        'Vendor/Supplier': [
            'vendor_account_ledger', 'vendor_accounts', 'vendor_default_categories',
            'vendor_name_mapping', 'vendor_standardization', 'vendor_synonyms',
            'vendors', 'suppliers'
        ],
        'Debt/Loans': [
            'credit_lines', 'financing_payments', 'financing_sources',
            'loan_transactions', 'payday_loan_payments', 'payday_loans',
            'wcb_debt_ledger', 'rent_debt_ledger'
        ]
    }
    
    print("="*100)
    print("TABLE GROUP ANALYSIS")
    print("="*100)
    
    for group_name, table_list in groups.items():
        print(f"\n{'='*100}")
        print(f"{group_name.upper()} TABLES")
        print("="*100)
        
        for table_name in table_list:
            # Check if table exists
            cur.execute("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = %s)", (table_name,))
            exists = cur.fetchone()[0]
            
            if not exists:
                print(f"\n  ⚠️  {table_name} - TABLE DOES NOT EXIST (may have been deleted)")
                continue
            
            info = get_table_info(conn, table_name)
            
            print(f"\n  {table_name}")
            print(f"    Rows: {info['row_count']:,}  |  Size: {info['size']}")
            
            if info['foreign_keys']:
                print(f"    Foreign Keys: {len(info['foreign_keys'])}")
                for col, ftable, fcol in info['foreign_keys'][:3]:
                    print(f"      → {col} → {ftable}.{fcol}")
            
            if info['referenced_by']:
                print(f"    Referenced By: {len(info['referenced_by'])} tables")
                for ref_table, ref_col in info['referenced_by'][:3]:
                    print(f"      ← {ref_table}.{ref_col}")
            
            if info['dependent_views']:
                print(f"    Dependent Views: {len(info['dependent_views'])}")
                for view_name, in info['dependent_views'][:3]:
                    print(f"      ↳ {view_name}")
            
            # Recommendation
            if info['row_count'] == 0 and not info['referenced_by'] and not info['dependent_views']:
                print(f"    ❌ RECOMMENDATION: DELETE (empty, no dependencies)")
            elif info['row_count'] == 0 and (info['referenced_by'] or info['dependent_views']):
                print(f"    ⚠️  RECOMMENDATION: REVIEW (empty but has dependencies)")
            elif info['row_count'] > 0:
                print(f"    ✅ KEEP (has data)")
    
    conn.close()


if __name__ == '__main__':
    main()
