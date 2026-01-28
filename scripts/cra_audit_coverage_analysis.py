#!/usr/bin/env python3
"""
Comprehensive Square-CIBC-Charter Audit Coverage Analysis
Analyzes matching completeness for CRA audit requirements across all transaction types
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
import csv

load_dotenv()

def get_pg_conn():
    """Connect to PostgreSQL almsdata"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'), 
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )

def analyze_square_data_coverage():
    """Analyze Square data coverage and transaction types"""
    print("=== SQUARE DATA COVERAGE ANALYSIS ===")
    
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get date ranges
            cur.execute("""
                SELECT 
                    MIN(payment_date) as earliest_square,
                    MAX(payment_date) as latest_square,
                    COUNT(*) as total_payments,
                    COUNT(CASE WHEN square_payment_id IS NOT NULL THEN 1 END) as square_payments,
                    COUNT(CASE WHEN square_payment_id IS NOT NULL AND charter_id IS NOT NULL THEN 1 END) as matched_to_charter
                FROM payments
            """)
            overview = cur.fetchone()
            
            print(f"Square Payment Date Range: {overview['earliest_square']} to {overview['latest_square']}")
            print(f"Total Payments: {overview['total_payments']:,}")
            print(f"Square Payments: {overview['square_payments']:,}")
            print(f"Matched to Charters: {overview['matched_to_charter']:,}")
            print(f"Square Match Rate: {(overview['matched_to_charter']/overview['square_payments']*100):.1f}%" if overview['square_payments'] > 0 else "N/A")
            
            # Analyze by transaction type/status
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN notes ILIKE '%refund%' THEN 'Refunds'
                        WHEN notes ILIKE '%dispute%' OR notes ILIKE '%chargeback%' THEN 'Disputes/Chargebacks'
                        WHEN notes ILIKE '%loan%' THEN 'Square Loans'
                        WHEN amount < 0 THEN 'Negative Amounts'
                        WHEN amount > 0 AND square_payment_id IS NOT NULL THEN 'Standard Payments'
                        ELSE 'Other'
                    END as transaction_type,
                    COUNT(*) as count,
                    COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as matched,
                    SUM(amount) as total_amount,
                    MIN(payment_date) as earliest_date,
                    MAX(payment_date) as latest_date
                FROM payments 
                WHERE square_payment_id IS NOT NULL
                GROUP BY 1
                ORDER BY count DESC
            """)
            
            print(f"\n--- Square Transaction Type Breakdown ---")
            square_types = cur.fetchall()
            for row in square_types:
                match_rate = (row['matched']/row['count']*100) if row['count'] > 0 else 0
                earliest = str(row['earliest_date']) if row['earliest_date'] else 'N/A'
                latest = str(row['latest_date']) if row['latest_date'] else 'N/A'
                total_amount = row['total_amount'] if row['total_amount'] is not None else 0
                print(f"{row['transaction_type']:20} | {row['count']:5,} | {row['matched']:5,} | {match_rate:5.1f}% | ${total_amount:10,.2f} | {earliest} to {latest}")
            
            return overview, square_types

def analyze_cibc_data_coverage():
    """Analyze CIBC banking data coverage"""
    print("\n=== CIBC BANKING DATA COVERAGE ANALYSIS ===")
    
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get CIBC date ranges and transaction types
            cur.execute("""
                SELECT 
                    MIN(transaction_date) as earliest_cibc,
                    MAX(transaction_date) as latest_cibc,
                    COUNT(*) as total_transactions,
                    COUNT(CASE WHEN description ILIKE '%square%' THEN 1 END) as square_related,
                    COUNT(CASE WHEN description ILIKE '%electronic funds transfer%' THEN 1 END) as eft_transactions,
                    SUM(COALESCE(credit_amount, 0)) as total_credits,
                    SUM(COALESCE(debit_amount, 0)) as total_debits
                FROM banking_transactions
            """)
            overview = cur.fetchone()
            
            print(f"CIBC Transaction Date Range: {overview['earliest_cibc']} to {overview['latest_cibc']}")
            print(f"Total CIBC Transactions: {overview['total_transactions']:,}")
            print(f"Square-Related: {overview['square_related']:,}")
            print(f"EFT Transactions: {overview['eft_transactions']:,}")
            print(f"Total Credits: ${overview['total_credits']:,.2f}")
            print(f"Total Debits: ${overview['total_debits']:,.2f}")
            
            # Analyze by transaction type
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN description ILIKE '%square%' THEN 'Square Deposits'
                        WHEN description ILIKE '%electronic funds transfer%' THEN 'EFT Transactions'
                        WHEN description ILIKE '%loan%' OR description ILIKE '%financing%' THEN 'Loan Transactions'
                        WHEN description ILIKE '%fee%' THEN 'Bank Fees'
                        WHEN description ILIKE '%chargeback%' OR description ILIKE '%reversal%' THEN 'Chargebacks/Reversals'
                        ELSE 'Other Banking'
                    END as transaction_type,
                    COUNT(*) as count,
                    SUM(COALESCE(credit_amount, 0)) as total_credits,
                    SUM(COALESCE(debit_amount, 0)) as total_debits,
                    MIN(transaction_date) as earliest_date,
                    MAX(transaction_date) as latest_date
                FROM banking_transactions
                GROUP BY 1
                ORDER BY count DESC
            """)
            
            print(f"\n--- CIBC Transaction Type Breakdown ---")
            print(f"{'Type':20} | {'Count':>6} | {'Credits':>12} | {'Debits':>12} | Date Range")
            cibc_types = cur.fetchall()
            for row in cibc_types:
                earliest = str(row['earliest_date']) if row['earliest_date'] else 'N/A'
                latest = str(row['latest_date']) if row['latest_date'] else 'N/A'
                total_credits = row['total_credits'] if row['total_credits'] is not None else 0
                total_debits = row['total_debits'] if row['total_debits'] is not None else 0
                print(f"{row['transaction_type']:20} | {row['count']:6,} | ${total_credits:10,.2f} | ${total_debits:10,.2f} | {earliest} to {latest}")
            
            return overview, cibc_types

def analyze_charter_revenue_completeness():
    """Analyze charter revenue completeness and payment matching"""
    print("\n=== CHARTER REVENUE COMPLETENESS ANALYSIS ===")
    
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Charter payment status
            cur.execute("""
                SELECT 
                    COUNT(*) as total_charters,
                    COUNT(CASE WHEN c.reserve_number IS NOT NULL THEN 1 END) as with_reserve_number,
                    SUM(COALESCE(c.total_amount_due, c.rate, 0)) as total_charter_amount,
                    COUNT(DISTINCT p.payment_id) as linked_payments,
                    SUM(CASE WHEN p.payment_id IS NOT NULL THEN COALESCE(p.amount, 0) ELSE 0 END) as linked_payment_amount
                FROM charters c
                LEFT JOIN payments p ON c.charter_id = p.charter_id
            """)
            charter_overview = cur.fetchone()
            
            print(f"Total Charters: {charter_overview['total_charters']:,}")
            print(f"With Reserve Numbers: {charter_overview['with_reserve_number']:,}")
            print(f"Total Charter Amount: ${charter_overview['total_charter_amount']:,.2f}")
            print(f"Linked Payments: {charter_overview['linked_payments']:,}")
            print(f"Linked Payment Amount: ${charter_overview['linked_payment_amount']:,.2f}")
            
            # Payment coverage by date (avoid double-counting charters with multiple payments)
            cur.execute("""
                WITH charter_base AS (
                    SELECT 
                        c.charter_id,
                        c.charter_date,
                        COALESCE(c.total_amount_due, c.rate, 0) AS charter_amount
                    FROM charters c
                    WHERE c.charter_date >= '2020-01-01'
                ),
                payments_per_charter AS (
                    SELECT 
                        p.charter_id,
                        COUNT(*) FILTER (WHERE p.square_payment_id IS NOT NULL) AS payment_count,
                        SUM(COALESCE(p.amount, 0)) FILTER (WHERE p.square_payment_id IS NOT NULL) AS payment_amount
                    FROM payments p
                    GROUP BY p.charter_id
                )
                SELECT 
                    DATE_TRUNC('month', cb.charter_date) AS month,
                    COUNT(*) AS charters,
                    SUM(CASE WHEN COALESCE(ppc.payment_count, 0) > 0 THEN 1 ELSE 0 END) AS with_payments,
                    SUM(cb.charter_amount) AS charter_revenue,
                    SUM(COALESCE(ppc.payment_amount, 0)) AS payment_revenue
                FROM charter_base cb
                LEFT JOIN payments_per_charter ppc ON ppc.charter_id = cb.charter_id
                GROUP BY 1
                ORDER BY 1 DESC
                LIMIT 12
            """)
            
            print(f"\n--- Monthly Charter Payment Coverage (Last 12 Months) ---")
            print(f"{'Month':12} | {'Charters':>8} | {'w/Payments':>10} | {'Coverage':>8} | {'Charter $':>12} | {'Payment $':>12}")
            monthly = cur.fetchall()
            for row in monthly:
                coverage = (row['with_payments']/row['charters']*100) if row['charters'] > 0 else 0
                print(f"{str(row['month'])[:10]:12} | {row['charters']:8,} | {row['with_payments']:10,} | {coverage:7.1f}% | ${row['charter_revenue']:10,.0f} | ${row['payment_revenue']:10,.0f}")
            
            return charter_overview, monthly

def analyze_audit_gaps():
    """Identify specific gaps for CRA audit requirements"""
    print("\n=== AUDIT GAPS & REQUIREMENTS ANALYSIS ===")
    
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            gaps = []
            
            # Gap 1: Unmatched Square payments
            cur.execute("""
                SELECT COUNT(*) as unmatched_square
                FROM payments 
                WHERE square_payment_id IS NOT NULL AND charter_id IS NULL
            """)
            unmatched_square = cur.fetchone()['unmatched_square']
            if unmatched_square > 0:
                gaps.append(f"Unmatched Square Payments: {unmatched_square:,}")
            
            # Gap 2: Charters without payments  
            cur.execute("""
                SELECT COUNT(*) as charters_no_payments
                FROM charters c
                LEFT JOIN payments p ON c.charter_id = p.charter_id
                WHERE p.payment_id IS NULL AND COALESCE(c.total_amount_due, c.rate, 0) > 0
            """)
            charters_no_payments = cur.fetchone()['charters_no_payments']
            if charters_no_payments > 0:
                gaps.append(f"Charters Without Payments: {charters_no_payments:,}")
            
            # Gap 3: Missing reserve numbers
            cur.execute("""
                SELECT COUNT(*) as missing_reserves
                FROM charters 
                WHERE reserve_number IS NULL AND COALESCE(total_amount_due, rate, 0) > 0
            """)
            missing_reserves = cur.fetchone()['missing_reserves']
            if missing_reserves > 0:
                gaps.append(f"Charters Missing Reserve Numbers: {missing_reserves:,}")
            
            # Gap 4: Date mismatches (payments outside charter date ranges)
            cur.execute("""
                SELECT COUNT(*) as date_mismatches
                FROM payments p
                JOIN charters c ON p.charter_id = c.charter_id
                WHERE ABS(p.payment_date - c.charter_date) > 30
            """)
            date_mismatches = cur.fetchone()['date_mismatches']
            if date_mismatches > 0:
                gaps.append(f"Payment-Charter Date Mismatches (>30 days): {date_mismatches:,}")
            
            # Gap 5: CIBC validation gaps
            cur.execute("""
                SELECT COUNT(*) as no_cibc_validation
                FROM payments p
                WHERE p.square_payment_id IS NOT NULL 
                AND NOT EXISTS (
                    SELECT 1 FROM banking_transactions bt
                    WHERE ABS(bt.transaction_date - p.payment_date) <= 4
                    AND ABS((COALESCE(bt.credit_amount, 0) - COALESCE(bt.debit_amount, 0)) - p.amount) < 0.01
                )
            """)
            no_cibc_validation = cur.fetchone()['no_cibc_validation']
            if no_cibc_validation > 0:
                gaps.append(f"Square Payments Without CIBC Validation: {no_cibc_validation:,}")
            
            # Gap 6: Duplicate transactions
            cur.execute("""
                SELECT COUNT(*) as potential_duplicates
                FROM (
                    SELECT payment_date, amount, COUNT(*) as cnt
                    FROM payments 
                    WHERE square_payment_id IS NOT NULL
                    GROUP BY payment_date, amount
                    HAVING COUNT(*) > 1
                ) dups
            """)
            potential_duplicates = cur.fetchone()['potential_duplicates']
            if potential_duplicates > 0:
                gaps.append(f"Potential Duplicate Transactions: {potential_duplicates:,}")
            
            if gaps:
                print("IDENTIFIED GAPS:")
                for i, gap in enumerate(gaps, 1):
                    print(f"  {i}. {gap}")
            else:
                print("[OK] NO MAJOR GAPS IDENTIFIED")
            
            return gaps

def generate_cra_audit_report():
    """Generate comprehensive CRA audit readiness report"""
    print("\n" + "="*80)
    print("COMPREHENSIVE CRA AUDIT READINESS REPORT")
    print("="*80)
    
    # Analyze all components
    square_overview, square_types = analyze_square_data_coverage()
    cibc_overview, cibc_types = analyze_cibc_data_coverage()  
    charter_overview, monthly = analyze_charter_revenue_completeness()
    gaps = analyze_audit_gaps()
    
    # Calculate overall completeness score
    total_square = square_overview['square_payments']
    matched_square = square_overview['matched_to_charter'] 
    overall_match_rate = (matched_square / total_square * 100) if total_square > 0 else 0
    
    print(f"\n=== OVERALL AUDIT READINESS SCORE ===")
    print(f"Square Payment Match Rate: {overall_match_rate:.1f}%")
    
    if overall_match_rate >= 95:
        grade = "A - Excellent"
        status = "[OK] AUDIT READY"
    elif overall_match_rate >= 90:
        grade = "B - Good" 
        status = "[WARN]  MOSTLY READY"
    elif overall_match_rate >= 80:
        grade = "C - Fair"
        status = "[WARN]  NEEDS IMPROVEMENT"
    else:
        grade = "D - Poor"
        status = "[FAIL] NOT AUDIT READY"
    
    print(f"Audit Readiness Grade: {grade}")
    print(f"Status: {status}")
    
    # Save detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"l:/limo/reports/cra_audit_readiness_{timestamp}.csv"
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['CRA Audit Readiness Report', f'Generated: {datetime.now()}'])
        writer.writerow([])
        writer.writerow(['Metric', 'Value', 'Status'])
        writer.writerow(['Overall Match Rate', f'{overall_match_rate:.1f}%', status])
        writer.writerow(['Total Square Payments', f'{total_square:,}', ''])
        writer.writerow(['Matched to Charters', f'{matched_square:,}', ''])
        writer.writerow(['Unmatched Payments', f'{total_square - matched_square:,}', ''])
        writer.writerow([])
        writer.writerow(['Identified Gaps:'])
        for gap in gaps:
            writer.writerow(['', gap, ''])
    
    print(f"\nDetailed report saved to: {report_file}")
    
    return {
        'overall_match_rate': overall_match_rate,
        'grade': grade, 
        'status': status,
        'gaps': gaps,
        'report_file': report_file
    }

def main():
    try:
        result = generate_cra_audit_report()
        
        print(f"\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Match Rate: {result['overall_match_rate']:.1f}%")
        print(f"Grade: {result['grade']}")
        print(f"Status: {result['status']}")
        
        if result['gaps']:
            print(f"\nPriority Actions:")
            for i, gap in enumerate(result['gaps'][:3], 1):
                print(f"  {i}. Address: {gap}")
        else:
            print(f"\n[OK] System appears audit-ready for CRA requirements")
            
    except Exception as e:
        print(f"Error generating audit report: {e}")
        raise

if __name__ == "__main__":
    main()