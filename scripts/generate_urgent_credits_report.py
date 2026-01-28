#!/usr/bin/env python
"""
Generate detailed report for 95 very large credits (>$2K) requiring urgent refund review.
Includes customer contact info, payment history, and recommended actions.
"""
import psycopg2
import csv
from datetime import datetime


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print("=" * 100)
    print("URGENT CREDIT REVIEW - CHARTERS >$2,000 OVERPAID")
    print("=" * 100)
    
    # Get all very large credits with customer details
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.account_number,
            c.status,
            COALESCE(cl.client_name, cl.company_name) AS client_name,
            cl.email,
            cl.primary_phone,
            cl.address_line1,
            (SELECT COUNT(*) FROM charter_payments cp 
             WHERE cp.charter_id = c.reserve_number::text) AS payment_count,
            (SELECT STRING_AGG(
                CONCAT(
                    TO_CHAR(cp.payment_date, 'YYYY-MM-DD'), 
                    ': $', 
                    ROUND(cp.amount::numeric, 2), 
                    ' (', 
                    COALESCE(cp.payment_method, 'unknown'), 
                    ')'
                ), 
                '; ' 
                ORDER BY cp.payment_date
            )
             FROM charter_payments cp 
             WHERE cp.charter_id = c.reserve_number::text) AS payment_history,
            (SELECT COUNT(*) FROM charters c2 
             WHERE c2.account_number = c.account_number) AS customer_charter_count
        FROM charters c
        LEFT JOIN clients cl ON cl.account_number = c.account_number
        WHERE c.balance < -2000
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        ORDER BY c.balance ASC
    """)
    
    credits = cur.fetchall()
    
    print(f"\nFound {len(credits)} charters with credits >$2,000")
    print(f"Total credit amount: ${sum(float(row[5]) for row in credits):,.2f}")
    
    # Export to CSV for review
    csv_file = 'reports/urgent_credits_review.csv'
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Reserve Number', 'Charter Date', 'Total Due', 'Paid', 'Credit Amount',
            'Customer Name', 'Email', 'Phone', 'Account Number',
            'Payment Count', 'Status', 'Customer Total Charters',
            'Action Recommendation', 'Priority', 'Notes'
        ])
        
        for row in credits:
            charter_id, reserve, date, total, paid, balance, account, status, \
            client_name, email, phone, contact, pay_cnt, pay_hist, cust_charters = row
            
            credit_amt = abs(float(balance))
            
            # Determine action recommendation
            if credit_amt > 4000:
                action = "IMMEDIATE REFUND - Contact customer urgently"
                priority = "CRITICAL"
            elif credit_amt > 3000:
                action = "Contact customer within 48 hours"
                priority = "HIGH"
            else:
                action = "Contact customer within 1 week"
                priority = "MEDIUM"
            
            # Add notes based on patterns
            notes = []
            if float(total or 0) == 0:
                notes.append("Missing total_amount_due - verify charter charges")
            if pay_cnt > 5:
                notes.append(f"Multiple payments ({pay_cnt}) - check for misallocation")
            if cust_charters > 10:
                notes.append(f"Frequent customer ({cust_charters} charters) - may want credit on account")
            if not email and not phone:
                notes.append("MISSING CONTACT INFO - research customer")
            
            notes_str = "; ".join(notes) if notes else ""
            
            writer.writerow([
                reserve, date, f"${float(total or 0):,.2f}", f"${float(paid or 0):,.2f}", 
                f"${credit_amt:,.2f}",
                client_name or 'Unknown', email or '', phone or '', account or '',
                pay_cnt, status or '', cust_charters,
                action, priority, notes_str
            ])
    
    print(f"\n✓ Detailed report exported to: {csv_file}")
    
    # Summary statistics
    print("\n" + "=" * 100)
    print("SUMMARY BY PRIORITY")
    print("=" * 100)
    
    critical = [r for r in credits if abs(float(r[5])) > 4000]
    high = [r for r in credits if 3000 < abs(float(r[5])) <= 4000]
    medium = [r for r in credits if abs(float(r[5])) <= 3000]
    
    print(f"\nCRITICAL (>$4K): {len(critical)} charters")
    print(f"  Total: ${sum(abs(float(r[5])) for r in critical):,.2f}")
    
    print(f"\nHIGH ($3K-$4K): {len(high)} charters")
    print(f"  Total: ${sum(abs(float(r[5])) for r in high):,.2f}")
    
    print(f"\nMEDIUM ($2K-$3K): {len(medium)} charters")
    print(f"  Total: ${sum(abs(float(r[5])) for r in medium):,.2f}")
    
    # Contact info completeness
    print("\n" + "=" * 100)
    print("CONTACT INFO COMPLETENESS")
    print("=" * 100)
    
    has_email = sum(1 for r in credits if r[9])
    has_phone = sum(1 for r in credits if r[10])
    has_either = sum(1 for r in credits if r[9] or r[10])
    has_both = sum(1 for r in credits if r[9] and r[10])
    has_neither = sum(1 for r in credits if not r[9] and not r[10])
    
    print(f"\nHas email: {has_email} ({has_email/len(credits)*100:.1f}%)")
    print(f"Has phone: {has_phone} ({has_phone/len(credits)*100:.1f}%)")
    print(f"Has both: {has_both} ({has_both/len(credits)*100:.1f}%)")
    print(f"Has either: {has_either} ({has_either/len(credits)*100:.1f}%)")
    print(f"Missing both: {has_neither} ({has_neither/len(credits)*100:.1f}%)")
    
    # Show top 10 critical cases
    print("\n" + "=" * 100)
    print("TOP 10 CRITICAL CASES (Immediate Action Required)")
    print("=" * 100)
    
    for i, row in enumerate(credits[:10], 1):
        charter_id, reserve, date, total, paid, balance, account, status, \
        client_name, email, phone, contact, pay_cnt, pay_hist, cust_charters = row
        
        print(f"\n{i}. Reserve {reserve} - ${abs(float(balance)):,.2f} credit")
        print(f"   Charter Date: {date}")
        print(f"   Customer: {client_name or 'Unknown'}")
        print(f"   Email: {email or 'MISSING'}")
        print(f"   Phone: {phone or 'MISSING'}")
        print(f"   Total Due: ${float(total or 0):,.2f}, Paid: ${float(paid or 0):,.2f}")
        print(f"   Payments: {pay_cnt}, Customer Charters: {cust_charters}")
        if pay_hist:
            print(f"   Payment History: {pay_hist[:200]}...")
    
    # Generate action checklist
    print("\n" + "=" * 100)
    print("REFUND PROCESSING CHECKLIST")
    print("=" * 100)
    print("""
1. ✓ Review exported CSV: reports/urgent_credits_review.csv
2. ⬜ Research missing customer contact info ({} charters)
3. ⬜ Contact CRITICAL priority customers ({} charters, ${:,.2f})
4. ⬜ Verify charter charges for $0 total_amount_due cases
5. ⬜ Confirm refund preference (check, transfer, credit on account)
6. ⬜ Process approved refunds
7. ⬜ Update charter_refunds table with refund records
8. ⬜ Re-run final_comprehensive_summary.py to verify

Next Steps:
- Use analyze_credits_for_refunds.py for detailed customer investigation
- Create refund_processing.py script to record refund transactions
- Consider bulk email/phone campaign for medium priority cases
    """.format(has_neither, len(critical), sum(abs(float(r[5])) for r in critical)))
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
