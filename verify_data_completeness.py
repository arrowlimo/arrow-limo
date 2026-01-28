#!/usr/bin/env python3
"""
Comprehensive almsdata Data Completeness Verification
Check if all missing data issues have been corrected after payment matching
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from api import get_db_connection

def verify_data_completeness():
    """Verify comprehensive data completeness across all tables"""
    
    print("🔍 COMPREHENSIVE ALMSDATA COMPLETENESS VERIFICATION...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Payment completeness verification
        print("\n1. 📊 PAYMENT DATA COMPLETENESS:")
        
        cur.execute("SELECT COUNT(*) FROM payments")
        total_payments = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number IS NOT NULL")
        matched_payments = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM payments WHERE LOWER(COALESCE(payment_method, '')) = 'cash'")
        cash_payments = cur.fetchone()[0]
        
        properly_handled = matched_payments + cash_payments
        completeness_percentage = (properly_handled / total_payments * 100) if total_payments > 0 else 0
        
        print(f"   Total payments: {total_payments:,}")
        print(f"   ✅ Matched to charters: {matched_payments:,}")
        print(f"   💵 Cash payments: {cash_payments:,}")
        print(f"   📈 Completeness: {completeness_percentage:.1f}%")
        
        status = "✅ COMPLETE" if completeness_percentage >= 98 else "⚠️ INCOMPLETE"
        print(f"   Status: {status}")
        
        # 2. Charter data completeness
        print("\n2. 🚗 CHARTER DATA COMPLETENESS:")
        
        cur.execute("SELECT COUNT(*) FROM charters")
        total_charters = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM charters WHERE client_id IS NOT NULL")
        charters_with_clients = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM charters WHERE reserve_number IS NOT NULL")
        charters_with_reserves = cur.fetchone()[0]
        
        charter_client_percentage = (charters_with_clients / total_charters * 100) if total_charters > 0 else 0
        charter_reserve_percentage = (charters_with_reserves / total_charters * 100) if total_charters > 0 else 0
        
        print(f"   Total charters: {total_charters:,}")
        print(f"   With client_id: {charters_with_clients:,} ({charter_client_percentage:.1f}%)")
        print(f"   With reserve_number: {charters_with_reserves:,} ({charter_reserve_percentage:.1f}%)")
        
        # 3. Client data completeness
        print("\n3. 👥 CLIENT DATA COMPLETENESS:")
        
        cur.execute("SELECT COUNT(*) FROM clients")
        total_clients = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM clients WHERE client_name IS NOT NULL AND client_name != ''")
        clients_with_names = cur.fetchone()[0]
        
        client_name_percentage = (clients_with_names / total_clients * 100) if total_clients > 0 else 0
        
        print(f"   Total clients: {total_clients:,}")
        print(f"   With names: {clients_with_names:,} ({client_name_percentage:.1f}%)")
        
        # 4. Financial data integrity
        print("\n4. 💰 FINANCIAL DATA INTEGRITY:")
        
        cur.execute("SELECT SUM(amount) FROM payments WHERE amount IS NOT NULL")
        total_payment_amount = cur.fetchone()[0] or 0
        
        cur.execute("SELECT SUM(rate) FROM charters WHERE rate IS NOT NULL")
        total_charter_amount = cur.fetchone()[0] or 0
        
        cur.execute("SELECT SUM(balance) FROM charters WHERE balance IS NOT NULL AND balance > 0")
        total_outstanding_balance = cur.fetchone()[0] or 0
        
        print(f"   Total payment amount: ${total_payment_amount:,.2f}")
        print(f"   Total charter rates: ${total_charter_amount:,.2f}")
        print(f"   Outstanding balances: ${total_outstanding_balance:,.2f}")
        
        # 5. Recent data verification
        print("\n5. 📅 RECENT DATA VERIFICATION:")
        
        cur.execute("""
            SELECT COUNT(*) FROM payments 
            WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent_payments = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM charters 
            WHERE charter_date >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent_charters = cur.fetchone()[0]
        
        print(f"   Recent payments (30 days): {recent_payments:,}")
        print(f"   Recent charters (30 days): {recent_charters:,}")
        
        # 6. Check for critical missing data patterns
        print("\n6. 🔍 CRITICAL MISSING DATA CHECK:")
        
        # Payments without any identifying information
        cur.execute("""
            SELECT COUNT(*) FROM payments 
            WHERE reserve_number IS NULL 
            AND client_id IS NULL 
            AND account_number IS NULL 
            AND reserve_number IS NULL
            AND LOWER(COALESCE(payment_method, '')) != 'cash'
        """)
        orphaned_payments = cur.fetchone()[0]
        
        # Charters without client information
        cur.execute("""
            SELECT COUNT(*) FROM charters 
            WHERE client_id IS NULL 
            AND account_number IS NULL
        """)
        orphaned_charters = cur.fetchone()[0]
        
        print(f"   Orphaned payments: {orphaned_payments:,}")
        print(f"   Orphaned charters: {orphaned_charters:,}")
        
        # 7. Data consistency checks
        print("\n7. 🔄 DATA CONSISTENCY VERIFICATION:")
        
        # Check for duplicate reserve numbers
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT reserve_number, COUNT(*) 
                FROM charters 
                WHERE reserve_number IS NOT NULL 
                GROUP BY reserve_number 
                HAVING COUNT(*) > 1
            ) duplicates
        """)
        duplicate_reserves = cur.fetchone()[0]
        
        # Check for negative amounts that aren't marked as refunds
        cur.execute("""
            SELECT COUNT(*) FROM payments 
            WHERE amount < 0 
            AND LOWER(COALESCE(payment_method, '')) NOT IN ('refund', 'adjustment')
        """)
        unhandled_negatives = cur.fetchone()[0]
        
        print(f"   Duplicate reserve numbers: {duplicate_reserves:,}")
        print(f"   Unhandled negative amounts: {unhandled_negatives:,}")
        
        # 8. Overall assessment
        print(f"\n8. 🎯 OVERALL DATA COMPLETENESS ASSESSMENT:")
        
        issues_found = 0
        
        if completeness_percentage < 98:
            issues_found += 1
            print(f"   ❌ Payment matching below 98%")
        else:
            print(f"   ✅ Payment matching excellent (98%+)")
            
        if charter_client_percentage < 95:
            issues_found += 1
            print(f"   ❌ Charter-client linking needs improvement")
        else:
            print(f"   ✅ Charter-client linking good")
            
        if client_name_percentage < 95:
            issues_found += 1
            print(f"   ❌ Client name completeness needs improvement")
        else:
            print(f"   ✅ Client name completeness good")
            
        if orphaned_payments > 1000:
            issues_found += 1
            print(f"   ❌ Too many orphaned payments")
        else:
            print(f"   ✅ Orphaned payments under control")
            
        if duplicate_reserves > 10:
            issues_found += 1
            print(f"   ❌ Too many duplicate reserve numbers")
        else:
            print(f"   ✅ Reserve number integrity good")
        
        print(f"\n🏆 FINAL ASSESSMENT:")
        if issues_found == 0:
            print(f"   🎉 EXCELLENT: All data completeness issues corrected!")
            overall_status = "COMPLETE"
        elif issues_found <= 2:
            print(f"   🟡 GOOD: Minor issues remain ({issues_found} areas)")
            overall_status = "MOSTLY_COMPLETE"
        else:
            print(f"   🔴 NEEDS WORK: Multiple issues found ({issues_found} areas)")
            overall_status = "INCOMPLETE"
        
        return {
            'overall_status': overall_status,
            'payment_completeness': completeness_percentage,
            'total_payments': total_payments,
            'total_charters': total_charters,
            'total_clients': total_clients,
            'issues_found': issues_found,
            'orphaned_payments': orphaned_payments,
            'orphaned_charters': orphaned_charters
        }
        
    finally:
        cur.close()
        conn.close()

def check_specific_missing_data():
    """Check for specific data that was previously identified as missing"""
    
    print("\n🔍 CHECKING PREVIOUSLY IDENTIFIED MISSING DATA...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if reserve number standardization is complete
        print("\n1. Reserve Number Standardization:")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN reserve_number ~ '^[0-9]{6}$' THEN 1 ELSE 0 END) as standardized,
                SUM(CASE WHEN reserve_number LIKE 'REF%' THEN 1 ELSE 0 END) as ref_format,
                SUM(CASE WHEN reserve_number IS NULL THEN 1 ELSE 0 END) as null_values
            FROM charters
        """)
        reserve_stats = cur.fetchone()
        total, standardized, ref_format, null_values = reserve_stats
        
        standardized_percentage = (standardized / total * 100) if total > 0 else 0
        print(f"   Total charters: {total:,}")
        print(f"   Standardized format: {standardized:,} ({standardized_percentage:.1f}%)")
        print(f"   REF format remaining: {ref_format:,}")
        print(f"   NULL reserve numbers: {null_values:,}")
        
        # Check customer data synchronization
        print("\n2. Customer Data Synchronization:")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN client_name IS NOT NULL AND client_name != '' THEN 1 ELSE 0 END) as with_names
            FROM clients
        """)
        client_stats = cur.fetchone()
        client_total, client_with_names = client_stats
        client_percentage = (client_with_names / client_total * 100) if client_total > 0 else 0
        
        print(f"   Total clients: {client_total:,}")
        print(f"   With complete names: {client_with_names:,} ({client_percentage:.1f}%)")
        
        # Check payment data gaps
        print("\n3. Payment Data Completeness:")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN charter_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN payment_method = 'cash' THEN 1 ELSE 0 END) as cash,
                SUM(CASE WHEN charter_id IS NULL AND payment_method != 'cash' THEN 1 ELSE 0 END) as unresolved
            FROM payments
        """)
        payment_stats = cur.fetchone()
        pay_total, pay_matched, pay_cash, pay_unresolved = payment_stats
        
        resolved = pay_matched + pay_cash
        resolved_percentage = (resolved / pay_total * 100) if pay_total > 0 else 0
        
        print(f"   Total payments: {pay_total:,}")
        print(f"   Matched to charters: {pay_matched:,}")
        print(f"   Marked as cash: {pay_cash:,}")
        print(f"   Still unresolved: {pay_unresolved:,}")
        print(f"   Resolution rate: {resolved_percentage:.1f}%")
        
        return resolved_percentage >= 98
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("🔍 ALMSDATA COMPLETENESS VERIFICATION")
    print("=" * 60)
    
    # Comprehensive verification
    results = verify_data_completeness()
    
    # Check specific previously missing data
    payment_resolved = check_specific_missing_data()
    
    print(f"\n" + "=" * 60)
    print("🔍 VERIFICATION COMPLETE")
    
    if results:
        print(f"Overall Status: {results['overall_status']}")
        print(f"Payment Completeness: {results['payment_completeness']:.1f}%")
        print(f"Issues Found: {results['issues_found']}")
        
        if results['overall_status'] == 'COMPLETE' and payment_resolved:
            print("✅ ALL MISSING ALMSDATA ISSUES HAVE BEEN CORRECTED!")
        elif results['overall_status'] == 'MOSTLY_COMPLETE':
            print("🟡 MOST MISSING DATA ISSUES CORRECTED - MINOR ITEMS REMAIN")
        else:
            print("🔴 SIGNIFICANT MISSING DATA ISSUES STILL NEED ATTENTION")
    
    print("=" * 60)