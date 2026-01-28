#!/usr/bin/env python3
"""
Comprehensive Woodridge Ford vehicle loan report.

Includes:
- Vehicle and loan details
- Complete payment history
- GST breakdown by year for CRA reporting
- NSF fees and reversals
- Final reconciliation against bill of sale
"""

import os
import psycopg2
from datetime import datetime

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

def main():
    print("=" * 100)
    print(" " * 25 + "WOODRIDGE FORD VEHICLE LOAN REPORT")
    print("=" * 100)
    
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            # Loan details
            print("\nVEHICLE DETAILS:")
            print("-" * 100)
            cur.execute("""
                SELECT DISTINCT vehicle_vin, vehicle_description, lender_name
                FROM vehicle_loan_payments
                WHERE lender_name = 'WOODRIDGE FORD'
                LIMIT 1
            """)
            vin, desc, lender = cur.fetchone()
            print(f"  Vehicle: {desc}")
            print(f"  VIN: {vin}")
            print(f"  Lender: {lender}")
            
            # Bill of sale reference
            print("\nBILL OF SALE (2019-01-02):")
            print("-" * 100)
            print("  Total Price: $100.00")
            print("  Sub-total: $2,061.00 (includes monthly payments + deposits)")
            print("  Total Credits: -$1,935.70 (deposits and trade-in)")
            print("  Due on Delivery: $130.30 (paid 2019-01-02)")
            
            # Complete payment history
            print("\nPAYMENT HISTORY:")
            print("-" * 100)
            print(f"{'Date':<12s} {'Type':<20s} {'Amount':>12s} {'GST':>10s} {'Net':>12s} {'NSF':>5s} {'Bank ID':>8s}")
            print("-" * 100)
            
            cur.execute("""
                SELECT 
                    payment_date,
                    payment_type,
                    gross_amount,
                    gst_amount,
                    net_amount,
                    nsf_related,
                    banking_transaction_id,
                    notes
                FROM vehicle_loan_payments
                WHERE lender_name = 'WOODRIDGE FORD'
                ORDER BY payment_date, id
            """)
            
            for row in cur.fetchall():
                date, pay_type, gross, gst, net, nsf, bank_id, notes = row
                nsf_flag = 'YES' if nsf else 'NO'
                sign = '-' if pay_type == 'reversal' else ' '
                print(f"{date} {pay_type:<20s} {sign}${gross:>10.2f} ${gst:>8.2f} ${net:>10.2f} {nsf_flag:>5s} {bank_id:>8d}")
            
            # GST by year
            print("\n" + "=" * 100)
            print("GST BREAKDOWN BY YEAR (for CRA reporting):")
            print("-" * 100)
            print(f"{'Year':<8s} {'Payments':>10s} {'Total Gross':>15s} {'Total GST':>12s} {'Total Net':>15s}")
            print("-" * 100)
            
            cur.execute("""
                SELECT 
                    EXTRACT(YEAR FROM payment_date)::INT as year,
                    COUNT(*) as count,
                    SUM(CASE WHEN payment_type = 'reversal' THEN -gross_amount ELSE gross_amount END) as total_gross,
                    SUM(CASE WHEN payment_type = 'reversal' THEN -gst_amount ELSE gst_amount END) as total_gst,
                    SUM(CASE WHEN payment_type = 'reversal' THEN -net_amount ELSE net_amount END) as total_net
                FROM vehicle_loan_payments
                WHERE lender_name = 'WOODRIDGE FORD'
                GROUP BY EXTRACT(YEAR FROM payment_date)
                ORDER BY year
            """)
            
            grand_gross = 0
            grand_gst = 0
            grand_net = 0
            
            for row in cur.fetchall():
                year, count, gross, gst, net = row
                print(f"{year:<8d} {count:>10d} ${gross:>13.2f} ${gst:>10.2f} ${net:>13.2f}")
                grand_gross += gross or 0
                grand_gst += gst or 0
                grand_net += net or 0
            
            print("-" * 100)
            print(f"{'TOTAL':<8s} {'':>10s} ${grand_gross:>13.2f} ${grand_gst:>10.2f} ${grand_net:>13.2f}")
            
            # NSF Analysis
            print("\n" + "=" * 100)
            print("NSF ANALYSIS:")
            print("-" * 100)
            
            cur.execute("""
                SELECT 
                    payment_date,
                    payment_type,
                    gross_amount,
                    notes
                FROM vehicle_loan_payments
                WHERE lender_name = 'WOODRIDGE FORD'
                  AND nsf_related = true
                ORDER BY payment_date
            """)
            
            nsf_rows = cur.fetchall()
            if nsf_rows:
                for row in nsf_rows:
                    date, pay_type, amount, notes = row
                    print(f"  {date} {pay_type:<20s} ${amount:>10.2f} - {notes}")
                
                print("\nNSF Event Summary:")
                print("  2018-10-17: Original payment reversed due to NSF")
                print("  2018-10-17: Payment re-attempted (same day)")
                print("  Note: Bank likely charged NSF fee separately (check for $45-$48 NSF charges)")
            else:
                print("  No NSF events recorded")
            
            # Summary totals
            print("\n" + "=" * 100)
            print("LOAN SUMMARY:")
            print("-" * 100)
            
            cur.execute("""
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN payment_type = 'monthly' THEN 1 ELSE 0 END) as monthly_count,
                    SUM(CASE WHEN payment_type = 'final_settlement' THEN 1 ELSE 0 END) as final_count,
                    SUM(CASE WHEN payment_type = 'reversal' THEN 1 ELSE 0 END) as reversal_count,
                    SUM(CASE WHEN payment_type = 'reversal' THEN -gross_amount ELSE gross_amount END) as net_total,
                    SUM(CASE WHEN payment_type = 'reversal' THEN -gst_amount ELSE gst_amount END) as net_gst
                FROM vehicle_loan_payments
                WHERE lender_name = 'WOODRIDGE FORD'
            """)
            
            total_txn, monthly, final, reversals, net_total, net_gst = cur.fetchone()
            
            print(f"  Total Transactions: {total_txn}")
            print(f"    - Monthly Payments: {monthly}")
            print(f"    - Final Settlements: {final}")
            print(f"    - Reversals (NSF): {reversals}")
            print(f"\n  Total Paid (net of reversals): ${net_total:.2f}")
            print(f"  Total GST Included: ${net_gst:.2f}")
            print(f"  Total Net (before GST): ${net_total - net_gst:.2f}")
            
            print("\n  Bill of Sale Reconciliation:")
            print(f"    Due on Delivery (per bill): $130.30")
            print(f"    Final settlements paid: ${261.56:.2f} (includes $131.26 + $130.30)")
            print(f"    Note: $131.26 payment predates bill of sale (2017-04-20)")
            
            print("\n" + "=" * 100)
            print("REPORT COMPLETE - Generated: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            print("=" * 100)


if __name__ == '__main__':
    main()
