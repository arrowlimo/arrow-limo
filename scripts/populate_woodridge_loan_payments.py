#!/usr/bin/env python3
"""
Populate vehicle_loan_payments with Woodridge Ford payments for 2008 Navigator.

Includes:
- Monthly $965.50 payments (GST included)
- NSF fees and reversals
- Final settlement payments
- GST calculations for CRA reporting
"""

import os
import psycopg2
from decimal import Decimal

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

# Known Woodridge transaction IDs from search
WOODRIDGE_PAYMENTS = [
    # Monthly payments ($965.50)
    (42121, '2018-09-17', 'monthly', 965.50, False, 'First monthly payment'),
    (41966, '2018-10-17', 'monthly', 965.50, True, 'Re-attempted after NSF'),
    (41820, '2018-11-19', 'monthly', 965.50, False, 'Monthly payment'),
    (41695, '2018-12-17', 'monthly', 965.50, False, 'Monthly payment'),
    
    # NSF reversal
    (41965, '2018-10-17', 'reversal', 965.50, True, 'EFT DEBIT REVERSAL - NSF'),
    
    # Final settlement payments
    (43061, '2017-04-20', 'final_settlement', 131.26, False, 'E-transfer to Tenisha Woodridge ford'),
    (41646, '2019-01-02', 'final_settlement', 130.30, False, 'Final due on delivery payment'),
]

def calculate_gst_included(gross):
    """Calculate GST amount when GST is included in gross."""
    gst = round(Decimal(str(gross)) * Decimal('0.05') / Decimal('1.05'), 2)
    net = Decimal(str(gross)) - gst
    return float(gst), float(net)


def main():
    print("POPULATING WOODRIDGE FORD LOAN PAYMENTS")
    print("=" * 80)
    
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            inserted_count = 0
            
            for txn_id, date, pay_type, amount, is_nsf, note in WOODRIDGE_PAYMENTS:
                # Calculate GST
                if pay_type == 'reversal':
                    # Reversals are credits, don't calculate GST
                    gst = 0.0
                    net = amount
                else:
                    gst, net = calculate_gst_included(amount)
                
                # Insert payment record
                cur.execute("""
                    INSERT INTO vehicle_loan_payments (
                        vehicle_vin,
                        vehicle_description,
                        lender_name,
                        banking_transaction_id,
                        payment_date,
                        payment_type,
                        gross_amount,
                        gst_amount,
                        net_amount,
                        gst_rate,
                        nsf_related,
                        notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    'L-19',  # VIN placeholder
                    '2008 Lincoln Navigator L-19',
                    'WOODRIDGE FORD',
                    txn_id,
                    date,
                    pay_type,
                    amount,
                    gst,
                    net,
                    0.05,
                    is_nsf,
                    note
                ))
                
                new_id = cur.fetchone()[0]
                inserted_count += 1
                
                print(f"  {date}  {pay_type:20s}  ${amount:8.2f}  GST ${gst:6.2f}  (ID {new_id})")
            
            conn.commit()
            print(f"\n[OK] Inserted {inserted_count} loan payment records")
            
            # Summary report
            print("\n" + "=" * 80)
            print("LOAN PAYMENT SUMMARY")
            print("=" * 80)
            
            cur.execute("""
                SELECT 
                    payment_type,
                    COUNT(*) as count,
                    SUM(gross_amount) as total_gross,
                    SUM(gst_amount) as total_gst,
                    SUM(net_amount) as total_net
                FROM vehicle_loan_payments
                WHERE lender_name = 'WOODRIDGE FORD'
                GROUP BY payment_type
                ORDER BY payment_type
            """)
            
            print(f"\n{'Type':<20s} {'Count':>6s} {'Gross':>12s} {'GST':>10s} {'Net':>12s}")
            print("-" * 70)
            
            grand_gross = 0
            grand_gst = 0
            grand_net = 0
            
            for row in cur.fetchall():
                pay_type, count, gross, gst, net = row
                print(f"{pay_type:<20s} {count:>6d} ${gross:>10.2f} ${gst:>8.2f} ${net:>10.2f}")
                if pay_type != 'reversal':
                    grand_gross += gross or 0
                    grand_gst += gst or 0
                    grand_net += net or 0
                else:
                    # Reversals are credits - subtract
                    grand_gross -= gross or 0
                    grand_gst -= gst or 0
                    grand_net -= net or 0
            
            print("-" * 70)
            print(f"{'TOTAL (net of reversals)':<20s} {'':>6s} ${grand_gross:>10.2f} ${grand_gst:>8.2f} ${grand_net:>10.2f}")
            print("\nGST Reporting: ${:.2f} GST included in ${:.2f} total payments".format(grand_gst, grand_gross))


if __name__ == '__main__':
    main()
