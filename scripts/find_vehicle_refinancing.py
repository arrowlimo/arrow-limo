#!/usr/bin/env python3
"""
Search for vehicle refinancing transactions in 2012-2013 banking data.
Look for large credit transactions (money coming in) from lenders.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("SEARCHING FOR VEHICLE REFINANCING PAYOUT")
    print("="*80)
    
    # Look for large credit transactions (money coming IN) from lenders
    # Refinancing = new loan pays off old loan
    cur.execute("""
        SELECT 
            transaction_date,
            account_number,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2013-12-31'
        AND (
            description ILIKE '%heffner%'
            OR description ILIKE '%loan%'
            OR description ILIKE '%refinanc%'
            OR description ILIKE '%finance%'
            OR description ILIKE '%auto%'
            OR description ILIKE '%vehicle%'
            OR description ILIKE '%lease%'
            OR description ILIKE '%aaron%'
            OR description ILIKE '%woodridge%'
        )
        AND credit_amount > 0
        ORDER BY credit_amount DESC, transaction_date
    """)
    
    credits = cur.fetchall()
    
    if credits:
        print(f"\nFound {len(credits)} potential refinancing credits (money IN):")
        print("="*80)
        
        total_credits = 0
        for credit in credits:
            date = credit[0]
            account = credit[1]
            desc = credit[2][:60]
            debit = float(credit[3] or 0)
            credit_amt = float(credit[4])
            balance = float(credit[5] or 0)
            
            total_credits += credit_amt
            
            print(f"\n{date} | Account {account}")
            print(f"  ${credit_amt:12,.2f} IN")
            print(f"  {desc}")
            print(f"  Balance after: ${balance:,.2f}")
        
        print(f"\n{'='*80}")
        print(f"Total refinancing credits: ${total_credits:,.2f}")
        print(f"{'='*80}")
    else:
        print("\nNo refinancing credits found in description search")
    
    # Also look for any LARGE credits (>$50K) regardless of description
    print("\n" + "="*80)
    print("LARGE CREDITS (>$50K) - Potential Loan Payouts")
    print("="*80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            account_number,
            description,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2013-12-31'
        AND credit_amount > 50000
        ORDER BY credit_amount DESC
    """)
    
    large_credits = cur.fetchall()
    
    if large_credits:
        for credit in large_credits:
            date = credit[0]
            account = credit[1]
            desc = credit[2][:70]
            amount = float(credit[3])
            balance = float(credit[4] or 0)
            
            print(f"\n{date} | ${amount:,.2f} | Account {account}")
            print(f"  {desc}")
            print(f"  Balance after: ${balance:,.2f}")
    
    # Look for LARGE debits (loan payoff payments going OUT)
    print("\n" + "="*80)
    print("LARGE DEBITS (>$50K) - Potential Loan Payoffs")
    print("="*80)
    
    cur.execute("""
        SELECT 
            transaction_date,
            account_number,
            description,
            debit_amount,
            balance
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2013-12-31'
        AND debit_amount > 50000
        ORDER BY debit_amount DESC
    """)
    
    large_debits = cur.fetchall()
    
    if large_debits:
        for debit in large_debits:
            date = debit[0]
            account = debit[1]
            desc = debit[2][:70]
            amount = float(debit[3])
            balance = float(debit[4] or 0)
            
            print(f"\n{date} | ${amount:,.2f} OUT | Account {account}")
            print(f"  {desc}")
            print(f"  Balance after: ${balance:,.2f}")
    
    # Check email_financial_events for loan events
    print("\n" + "="*80)
    print("EMAIL FINANCIAL EVENTS - Loan/Vehicle Related")
    print("="*80)
    
    try:
        cur.execute("""
            SELECT 
                email_date,
                event_type,
                amount,
                lender_name,
                vehicle_name,
                vin,
                subject,
                notes
            FROM email_financial_events
            WHERE email_date BETWEEN '2012-01-01' AND '2013-12-31'
            AND (
                event_type ILIKE '%loan%'
                OR event_type ILIKE '%payment%'
                OR lender_name IS NOT NULL
                OR vehicle_name IS NOT NULL
            )
            ORDER BY email_date
        """)
        
        events = cur.fetchall()
        
        if events:
            for event in events:
                date = event[0]
                event_type = event[1]
                amount = float(event[2]) if event[2] else 0
                lender = event[3] or 'N/A'
                vehicle = event[4] or 'N/A'
                vin = event[5] or 'N/A'
                subject = event[6] or 'N/A'
                notes = event[7] or ''
                
                print(f"\n{date} | {event_type}")
                print(f"  Amount: ${amount:,.2f}")
                print(f"  Lender: {lender}")
                print(f"  Vehicle: {vehicle}")
                if vin != 'N/A':
                    print(f"  VIN: {vin}")
                if notes:
                    print(f"  Notes: {notes[:100]}")
        else:
            print("\nNo loan-related email events found")
    except Exception as e:
        print(f"\nCould not query email_financial_events: {e}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
