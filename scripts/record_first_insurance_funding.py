#!/usr/bin/env python3
"""
Record First Insurance Funding premium financing schedule
Agreement #901-1259126
Based on 3-08322011B_ocred.pdf Notice of Endorsement
"""
import psycopg2
import os
from datetime import date

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()
    
    # Agreement details
    agreement_number = "901-1259126"
    insured = "David Richard & Arrow Limousine & Sedan Services Ltd, 135 Metcalf Avenue, Red Deer, AB T4R 1T9"
    broker = "Drayden Insurance Ltd - Morinville, 9512 - 100 Street, Morinville, AB T8R 1V4"
    
    # Payment schedule from document
    notice_date = "2018-08-21"
    anticipated_funding_date = "2018-09-05"
    final_payment_date = "2019-04-20"
    day_of_month = 20
    frequency = "6 Monthly"
    
    # Financial breakdown
    total_premium = 10718.00
    down_payment = 3391.61
    principal_balance = 7324.39
    finance_charge = 650.41
    amount_added_to_balance = 7974.80
    
    # New installment amount after adjustment
    new_installment = 2031.18
    
    # Policy details
    policies = [
        {
            'policy_number': 'C00681-Nordic Insurance Co. of Canada - Calgary',
            'inception_date': '2018-05-30',
            'type_of_coverage': 'AUTO',
            'policy_term_months': 12,
            'premium': 69.00
        },
        {
            'policy_number': 'C00681-Nordic Insurance Co. of Canada - Calgary',
            'inception_date': '2018-08-09',
            'type_of_coverage': 'AUTO',
            'policy_term_months': 12,
            'premium': 10654.00
        }
    ]
    
    # Revised payment schedule
    payment_schedule = [
        {'due_date': '2018-08-23', 'type': 'Down Payment', 'amount': 3391.61, 'method': 'ACH'},
        {'due_date': '2018-09-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2018-10-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2018-11-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2018-12-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2019-01-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2019-02-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2019-03-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
        {'due_date': '2019-04-20', 'type': 'Payment', 'amount': 2031.18, 'method': 'ACH'},
    ]
    
    print(f"Recording First Insurance Funding Agreement {agreement_number}")
    print(f"Insured: {insured}")
    print(f"Broker: {broker}")
    print(f"\nFinancing Summary:")
    print(f"  Total Premium: ${total_premium:,.2f}")
    print(f"  Down Payment: ${down_payment:,.2f}")
    print(f"  Principal Balance: ${principal_balance:,.2f}")
    print(f"  Finance Charge: ${finance_charge:,.2f}")
    print(f"  Amount Financed: ${amount_added_to_balance:,.2f}")
    print(f"  Monthly Installment: ${new_installment:,.2f}")
    print(f"  Number of Payments: {len(payment_schedule)}")
    
    # Insert into email_financial_events for each payment
    print(f"\nInserting {len(payment_schedule)} payment schedule entries...")
    
    for payment in payment_schedule:
        cur.execute("""
            INSERT INTO email_financial_events (
                source,
                entity,
                from_email,
                subject,
                email_date,
                event_type,
                amount,
                currency,
                due_date,
                status,
                lender_name,
                loan_external_id,
                policy_number,
                notes,
                created_at
            ) VALUES (
                'Insurance Financing Document',
                'First Insurance Funding',
                'billing@firstinsurancefunding.com',
                'Premium Finance Agreement - Notice of Endorsement',
                %s,
                %s,
                %s,
                'CAD',
                %s,
                'Scheduled',
                'First Insurance Funding',
                %s,
                'C00681',
                %s,
                CURRENT_TIMESTAMP
            )
        """, (
            notice_date,
            payment['type'],
            payment['amount'],
            payment['due_date'],
            agreement_number,
            f"Premium Finance Payment via {payment['method']}. "
            f"Agreement {agreement_number}. "
            f"Total premium ${total_premium:,.2f} financed over {len(payment_schedule)} payments. "
            f"Down payment ${down_payment:,.2f}, monthly ${new_installment:,.2f}. "
            f"Covers Nordic Insurance policies for AUTO coverage."
        ))
    
    conn.commit()
    
    print(f"[OK] Inserted {len(payment_schedule)} payment schedule entries")
    
    # Summary
    print("\n" + "="*70)
    print("FIRST INSURANCE FUNDING - PREMIUM FINANCE AGREEMENT")
    print("="*70)
    print(f"Agreement Number: {agreement_number}")
    print(f"Notice Date: {notice_date}")
    print(f"Anticipated Funding: {anticipated_funding_date}")
    print(f"Final Payment: {final_payment_date}")
    print(f"\nInsured: {insured}")
    print(f"Broker: {broker}")
    print(f"\nPolicies Covered:")
    for i, policy in enumerate(policies, 1):
        print(f"  {i}. {policy['policy_number']}")
        print(f"     Inception: {policy['inception_date']}")
        print(f"     Coverage: {policy['type_of_coverage']}")
        print(f"     Term: {policy['policy_term_months']} months")
        print(f"     Premium: ${policy['premium']:,.2f}")
    
    print(f"\nFinancing Terms:")
    print(f"  Total Premium: ${total_premium:,.2f}")
    print(f"  Down Payment: ${down_payment:,.2f}")
    print(f"  Principal Balance: ${principal_balance:,.2f}")
    print(f"  Finance Charge: ${finance_charge:,.2f}")
    print(f"  Total Financed: ${amount_added_to_balance:,.2f}")
    print(f"  Payment Frequency: {frequency}")
    print(f"  Installment Amount: ${new_installment:,.2f}")
    print(f"  Number of Payments: {len(payment_schedule)}")
    
    print(f"\nPayment Schedule:")
    total_paid = 0
    for payment in payment_schedule:
        print(f"  {payment['due_date']}: ${payment['amount']:>8,.2f} ({payment['type']}) via {payment['method']}")
        total_paid += payment['amount']
    print(f"  {'Total:':<12} ${total_paid:>8,.2f}")
    
    print("\n[OK] First Insurance Funding payment schedule recorded successfully!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
