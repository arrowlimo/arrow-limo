#!/usr/bin/env python3
"""
Generate comprehensive GST/HST reconciliation report combining:
- Revenue (GST collected) from income_ledger
- Expenses (ITCs) from receipts
- Net GST/HST position for CRA filing

This is the complete tax picture for each fiscal year.
"""

import psycopg2
import csv
from pathlib import Path
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***',
        host='localhost'
    )

def generate_complete_gst_reconciliation(year=None):
    """Generate complete GST reconciliation: collected vs ITCs."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("COMPLETE GST/HST RECONCILIATION REPORT")
    if year:
        print(f"YEAR: {year}")
    else:
        print("ALL YEARS")
    print("="*100)
    
    # Query: Revenue (GST collected) from income_ledger
    where_income = f"WHERE fiscal_year = {year}" if year else ""
    cur.execute(f"""
        SELECT 
            fiscal_year,
            SUM(gross_amount) as total_revenue,
            SUM(gst_collected) as gst_collected,
            SUM(net_amount) as net_revenue
        FROM income_ledger
        {where_income}
        GROUP BY fiscal_year
        ORDER BY fiscal_year
    """)
    income_by_year = {int(row[0]): row[1:] for row in cur.fetchall()}
    
    # Query: Expenses (ITCs) from receipts
    where_receipts = f"WHERE EXTRACT(YEAR FROM receipt_date) = {year}" if year else ""
    cur.execute(f"""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as fiscal_year,
            SUM(gross_amount) as total_expenses,
            SUM(gst_amount) as gst_itc,
            SUM(net_amount) as net_expenses
        FROM receipts
        {where_receipts}
        GROUP BY fiscal_year
        ORDER BY fiscal_year
    """)
    expenses_by_year = {int(row[0]): row[1:] for row in cur.fetchall()}
    
    # Query: CRA payments from banking
    if year:
        where_banking = f"WHERE EXTRACT(YEAR FROM transaction_date) = {year} AND ("
    else:
        where_banking = "WHERE ("
    
    cur.execute(f"""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as fiscal_year,
            SUM(debit_amount) as total_cra_payments
        FROM banking_transactions
        {where_banking}
            LOWER(description) LIKE '%receiver general%'
            OR LOWER(description) LIKE '%cra%gst%'
            OR LOWER(description) LIKE '%gst remittance%'
            OR LOWER(description) LIKE '%gst payment%'
        )
        GROUP BY fiscal_year
        ORDER BY fiscal_year
    """)
    cra_by_year = {int(row[0]): row[1] for row in cur.fetchall()}
    
    # Combine all years
    all_years = sorted(set(income_by_year.keys()) | set(expenses_by_year.keys()) | set(cra_by_year.keys()))
    
    print(f"\n{'Year':<6} | {'Revenue':>15} | {'GST Collected':>15} | {'Expenses':>15} | {'ITCs Claimed':>15} | {'Net GST':>15} | {'CRA Paid':>15} | {'Status':<12}")
    print("-"*145)
    
    total_revenue = Decimal('0')
    total_gst_collected = Decimal('0')
    total_expenses = Decimal('0')
    total_itc = Decimal('0')
    total_cra_payments = Decimal('0')
    
    results = []
    
    for yr in all_years:
        # Income data
        inc_data = income_by_year.get(yr, (Decimal('0'), Decimal('0'), Decimal('0')))
        revenue = inc_data[0]
        gst_collected = inc_data[1]
        
        # Expense data
        exp_data = expenses_by_year.get(yr, (Decimal('0'), Decimal('0'), Decimal('0')))
        expenses = exp_data[0]
        gst_itc = exp_data[1]
        
        # CRA payments
        cra_paid = cra_by_year.get(yr, Decimal('0'))
        
        # Net GST/HST
        net_gst = gst_collected - gst_itc
        
        # Status
        if net_gst > 10:
            status = "OWING"
        elif net_gst < -10:
            status = "REFUND DUE"
        else:
            status = "BALANCED"
        
        print(f"{yr:<6} | ${revenue:>14,.2f} | ${gst_collected:>14,.2f} | ${expenses:>14,.2f} | ${gst_itc:>14,.2f} | ${net_gst:>14,.2f} | ${cra_paid:>14,.2f} | {status:<12}")
        
        total_revenue += revenue
        total_gst_collected += gst_collected
        total_expenses += expenses
        total_itc += gst_itc
        total_cra_payments += cra_paid
        
        results.append({
            'year': yr,
            'revenue': revenue,
            'gst_collected': gst_collected,
            'expenses': expenses,
            'itc_claimed': gst_itc,
            'net_gst': net_gst,
            'cra_payments': cra_paid,
            'status': status
        })
    
    print("-"*145)
    total_net_gst = total_gst_collected - total_itc
    overall_status = "OWING" if total_net_gst > 10 else "REFUND DUE" if total_net_gst < -10 else "BALANCED"
    print(f"{'TOTAL':<6} | ${total_revenue:>14,.2f} | ${total_gst_collected:>14,.2f} | ${total_expenses:>14,.2f} | ${total_itc:>14,.2f} | ${total_net_gst:>14,.2f} | ${total_cra_payments:>14,.2f} | {overall_status:<12}")
    
    print("\n" + "="*100)
    print("SUMMARY ANALYSIS")
    print("="*100)
    print(f"\n📊 REVENUE:")
    print(f"   • Total Revenue (Gross): ${total_revenue:,.2f}")
    print(f"   • GST Collected: ${total_gst_collected:,.2f}")
    print(f"   • Net Revenue: ${total_revenue - total_gst_collected:,.2f}")
    
    print(f"\n💰 EXPENSES:")
    print(f"   • Total Expenses (Gross): ${total_expenses:,.2f}")
    print(f"   • Input Tax Credits (ITCs): ${total_itc:,.2f}")
    print(f"   • Net Expenses: ${total_expenses - total_itc:,.2f}")
    
    print(f"\n📈 GST/HST POSITION:")
    print(f"   • GST Collected: ${total_gst_collected:,.2f}")
    print(f"   • ITCs Claimed: ${total_itc:,.2f}")
    print(f"   • Net GST/HST: ${total_net_gst:,.2f} ({overall_status})")
    
    print(f"\n💳 CRA PAYMENTS:")
    print(f"   • Total CRA Payments Made: ${total_cra_payments:,.2f}")
    
    if total_net_gst > 10:
        print(f"\n[WARN]  OWING TO CRA:")
        print(f"   • GST/HST owed: ${total_net_gst:,.2f}")
        print(f"   • Already paid: ${total_cra_payments:,.2f}")
        outstanding = total_net_gst - total_cra_payments
        if outstanding > 0:
            print(f"   • Still owing: ${outstanding:,.2f}")
        else:
            print(f"   • Overpaid by: ${abs(outstanding):,.2f} (claim refund)")
    elif total_net_gst < -10:
        potential_refund = abs(total_net_gst)
        print(f"\n💰 REFUND DUE FROM CRA:")
        print(f"   • Refund available: ${potential_refund:,.2f}")
        print(f"   • CRA payments made: ${total_cra_payments:,.2f}")
        print(f"   • Combined refund potential: ${potential_refund + total_cra_payments:,.2f}")
    
    print(f"\n📋 NEXT STEPS:")
    if total_net_gst > 10:
        print(f"   1. File GST/HST returns for all years showing amounts owing")
        print(f"   2. Remit outstanding GST/HST balance to CRA")
        print(f"   3. Include supporting documentation (income_ledger + receipts)")
    elif total_net_gst < -10:
        print(f"   1. File GST/HST returns claiming Input Tax Credits")
        print(f"   2. Request refund from CRA")
        print(f"   3. Reconcile CRA payments already made")
    else:
        print(f"   1. File GST/HST returns showing balanced position")
        print(f"   2. Maintain records for CRA audit compliance")
    
    print(f"   4. **IMPORTANT**: Consult accountant before filing")
    print(f"   5. Maintain QuickBooks-style categorization in income_ledger")
    print(f"   6. Keep all receipts and payment records for 7 years (CRA requirement)")
    
    # Save to CSV
    output_dir = Path(__file__).parent.parent / 'exports' / 'cra' / 'reconciliation'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / f"gst_reconciliation{'_' + str(year) if year else '_all_years'}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'year', 'revenue', 'gst_collected', 'expenses', 'itc_claimed',
            'net_gst', 'cra_payments', 'status'
        ])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n[OK] Report saved to: {csv_path}")
    
    cur.close()
    conn.close()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate complete GST reconciliation')
    parser.add_argument('--year', type=int, help='Generate for specific year only')
    args = parser.parse_args()
    
    generate_complete_gst_reconciliation(year=args.year)

if __name__ == '__main__':
    main()
