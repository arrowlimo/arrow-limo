#!/usr/bin/env python3
"""
Generate comprehensive vehicle loan reports for dashboard and financial analysis.
Produces multiple CSV/Excel reports from the dashboard views.
"""
import os
import csv
import psycopg2
import pandas as pd
from datetime import datetime, date

REPORTS_DIR = r"L:\\limo\\reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

DB = dict(
    dbname=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

def run_query_to_csv(cur, query: str, filename: str, title: str = None):
    """Execute query and save results to CSV"""
    try:
        cur.execute(query)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        
        filepath = os.path.join(REPORTS_DIR, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if title:
                writer.writerow([title])
                writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow([])  # Empty row
            writer.writerow(columns)
            writer.writerows(rows)
        
        print(f"[OK] {title or filename}: {len(rows)} records → {filepath}")
        return len(rows)
    except Exception as e:
        print(f"[FAIL] Error generating {title or filename}: {e}")
        return 0

def generate_executive_summary(cur):
    """Generate high-level KPI summary"""
    queries = {
        "Portfolio Overview": """
            SELECT 
                'Total Loans' as metric, total_loans as value, '' as details
            FROM v_loan_portfolio_kpis
            UNION ALL
            SELECT 
                'Active Loans', active_loans::text, 
                ROUND((active_loans::numeric/total_loans::numeric)*100,1)::text || '% of portfolio'
            FROM v_loan_portfolio_kpis
            UNION ALL
            SELECT 
                'Total Outstanding', 
                '$' || TO_CHAR(total_outstanding_balance, 'FM999,999,999.00'),
                'Across all active loans'
            FROM v_loan_portfolio_kpis
            UNION ALL
            SELECT 
                'Total Collected (All Time)', 
                '$' || TO_CHAR(total_amount_paid, 'FM999,999,999.00'),
                ''
            FROM v_loan_portfolio_kpis
            UNION ALL
            SELECT 
                'Interest Earned', 
                '$' || TO_CHAR(total_interest_earned, 'FM999,999,999.00'),
                ''
            FROM v_loan_portfolio_kpis
            UNION ALL
            SELECT 
                'Fees Collected', 
                '$' || TO_CHAR(total_fees_collected, 'FM999,999,999.00'),
                'NSF and other fees'
            FROM v_loan_portfolio_kpis
            UNION ALL
            SELECT 
                'Recent Activity (30 days)', 
                payments_last_30_days::text || ' payments',
                '$' || TO_CHAR(amount_received_last_30_days, 'FM999,999.00') || ' received'
            FROM v_loan_portfolio_kpis
        """,
        
        "Top 5 Outstanding Balances": """
            SELECT 
                vehicle_name,
                '$' || TO_CHAR(current_balance, 'FM999,999.00') as outstanding,
                lender,
                loan_status,
                days_since_last_payment::text || ' days' as last_payment
            FROM v_loan_dashboard_summary 
            WHERE current_balance > 0 
            ORDER BY current_balance DESC 
            LIMIT 5
        """,
        
        "Recent NSF Activity": """
            SELECT 
                vehicle_name,
                vin_number,
                total_nsf_fees,
                '$' || TO_CHAR(total_nsf_amount, 'FM999,999.00') as total_fees,
                last_nsf_date
            FROM v_nsf_fees_summary 
            ORDER BY last_nsf_date DESC 
            LIMIT 10
        """
    }
    
    summary_content = []
    summary_content.append("EXECUTIVE DASHBOARD SUMMARY")
    summary_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_content.append("")
    
    for section_title, query in queries.items():
        summary_content.append(f"=== {section_title} ===")
        try:
            cur.execute(query)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            
            # Format as simple table
            for row in rows:
                line = " | ".join(str(val) for val in row)
                summary_content.append(line)
        except Exception as e:
            summary_content.append(f"Error: {e}")
        
        summary_content.append("")
    
    # Write summary
    filepath = os.path.join(REPORTS_DIR, 'executive_summary.txt')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(summary_content))
    
    print(f"📊 Executive Summary → {filepath}")

def main():
    """Generate all loan dashboard reports"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Report definitions
    reports = [
        {
            'query': 'SELECT * FROM v_loan_dashboard_summary ORDER BY loan_status, current_balance DESC',
            'filename': f'loan_summary_{timestamp}.csv',
            'title': 'Vehicle Loan Dashboard Summary'
        },
        {
            'query': 'SELECT * FROM v_payment_history_detail ORDER BY payment_date DESC LIMIT 500',
            'filename': f'payment_history_{timestamp}.csv',
            'title': 'Recent Payment History (Last 500)'
        },
        {
            'query': 'SELECT * FROM v_nsf_fees_summary ORDER BY total_nsf_amount DESC',
            'filename': f'nsf_fees_summary_{timestamp}.csv',
            'title': 'NSF and Fees Summary by Vehicle'
        },
        {
            'query': 'SELECT * FROM v_monthly_payment_summary ORDER BY payment_month DESC LIMIT 24',
            'filename': f'monthly_trends_{timestamp}.csv',
            'title': 'Monthly Payment Trends (Last 24 Months)'
        },
        {
            'query': 'SELECT * FROM v_overdue_loans ORDER BY days_overdue DESC',
            'filename': f'overdue_analysis_{timestamp}.csv',
            'title': 'Overdue Loans Analysis'
        },
        {
            'query': 'SELECT * FROM v_lender_performance ORDER BY total_financed DESC',
            'filename': f'lender_performance_{timestamp}.csv',
            'title': 'Performance by Lender'
        },
        {
            'query': 'SELECT * FROM v_loan_portfolio_kpis',
            'filename': f'portfolio_kpis_{timestamp}.csv',
            'title': 'Portfolio KPIs and Metrics'
        }
    ]
    
    conn = psycopg2.connect(**DB)
    try:
        with conn:
            with conn.cursor() as cur:
                print("=== Generating Vehicle Loan Dashboard Reports ===")
                print(f"Timestamp: {timestamp}")
                print()
                
                total_records = 0
                
                # Generate individual reports
                for report in reports:
                    count = run_query_to_csv(
                        cur, 
                        report['query'], 
                        report['filename'], 
                        report['title']
                    )
                    total_records += count
                
                print()
                
                # Generate executive summary
                generate_executive_summary(cur)
                
                print()
                print("=== Summary ===")
                print(f"Generated {len(reports)} reports with {total_records} total records")
                print(f"Reports saved to: {REPORTS_DIR}")
                
                # Test a few key queries for validation
                print("\n=== Quick Validation ===")
                
                # Active loans count
                cur.execute("SELECT COUNT(*) FROM v_loan_dashboard_summary WHERE loan_status = 'ACTIVE'")
                active_count = cur.fetchone()[0]
                print(f"Active loans: {active_count}")
                
                # Total outstanding
                cur.execute("SELECT SUM(current_balance) FROM v_loan_dashboard_summary WHERE current_balance > 0")
                outstanding = cur.fetchone()[0] or 0
                print(f"Total outstanding: ${outstanding:,.2f}")
                
                # Recent payments
                cur.execute("SELECT COUNT(*) FROM vehicle_loan_payments WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days'")
                recent_payments = cur.fetchone()[0]
                print(f"Payments last 30 days: {recent_payments}")
                
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    raise SystemExit(main())