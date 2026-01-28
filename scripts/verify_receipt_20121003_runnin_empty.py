#!/usr/bin/env python3
"""
Verify specific receipt: Oct 03, 2012 - Runn'in On Empty - $60.00 (Cash)
"""
import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("RECEIPT VERIFICATION")
    print("Looking for: Oct 03, 2012 | Runnin On Empty | $60.00 | CASH")
    print("="*100)
    
    # Search for the specific receipt (try multiple spelling variations)
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            gst_amount,
            net_amount,
            payment_method,
            source_system,
            source_reference,
            banking_transaction_id,
            created_from_banking,
            is_nsf,
            is_voided,
            exclude_from_reports
        FROM receipts
        WHERE receipt_date = '2012-10-03'
        AND (vendor_name ILIKE '%runn%' OR vendor_name ILIKE '%empty%' 
             OR description ILIKE '%runn%' OR description ILIKE '%empty%')
        ORDER BY receipt_id
    """)
    
    exact_matches = cur.fetchall()
    
    if exact_matches:
        print(f"\nFOUND {len(exact_matches)} EXACT MATCH(ES) for Oct 03, 2012 - Runnin On Empty:")
        print("="*100)
        
        for rec in exact_matches:
            (rec_id, date, vendor, desc, gross, gst, net, payment, source, 
             src_ref, bank_tx, from_banking, is_nsf, is_void, excluded) = rec
            
            print(f"\nReceipt ID: {rec_id}")
            print(f"Date: {date}")
            print(f"Vendor: {vendor}")
            print(f"Description: {desc or 'None'}")
            print(f"Amount: ${gross:.2f}" if gross else "Amount: NULL")
            if gst:
                print(f"  GST: ${gst:.2f}")
                print(f"  Net: ${net:.2f}")
            print(f"Payment Method: {payment or 'NOT SET'}")
            print(f"Source: {source or 'UNKNOWN'}")
            print(f"Source Reference: {src_ref or 'None'}")
            print(f"Banking Transaction: {bank_tx or 'NOT LINKED'}")
            print(f"Created from Banking: {from_banking}")
            print(f"NSF: {is_nsf}")
            print(f"Voided: {is_void}")
            print(f"Excluded from Reports: {excluded}")
            
            # Check if amount matches
            if gross and abs(gross - 60.00) < 0.01:
                print("\nAMOUNT MATCHES: $60.00 [VERIFIED]")
            elif gross:
                print(f"\nWARNING: Amount is ${gross:.2f}, expected $60.00")
            
            # Check payment method
            if payment and 'CASH' in payment.upper():
                print("PAYMENT METHOD MATCHES: CASH [VERIFIED]")
            else:
                print(f"WARNING: Payment method is '{payment}', expected CASH")
            
            # Check if in banking (cash shouldn't be)
            if bank_tx:
                print("\nWARNING: Cash receipt linked to banking transaction!")
                cur.execute("""
                    SELECT transaction_date, description, debit_amount, credit_amount
                    FROM banking_transactions
                    WHERE transaction_id = %s
                """, (bank_tx,))
                bank = cur.fetchone()
                if bank:
                    b_date, b_desc, b_debit, b_credit = bank
                    b_amt = b_debit if b_debit else b_credit
                    print(f"  Banking TX: {b_date} | ${b_amt:.2f} | {b_desc}")
            else:
                print("\nCORRECT: Cash receipt NOT linked to banking [VERIFIED]")
            
            print("\n" + "-"*100)
    else:
        print("\nNO EXACT MATCHES FOUND")
        print("\nSearching for similar receipts on Oct 03, 2012...")
        
        # Look for any receipts on that date
        cur.execute("""
            SELECT 
                receipt_id,
                vendor_name,
                description,
                gross_amount,
                payment_method
            FROM receipts
            WHERE receipt_date = '2012-10-03'
            ORDER BY receipt_id
        """)
        
        date_matches = cur.fetchall()
        
        if date_matches:
            print(f"\nFound {len(date_matches)} receipts on Oct 03, 2012:")
            for rec_id, vendor, desc, amount, payment in date_matches:
                amt_str = f"${amount:.2f}" if amount else "$0.00"
                print(f"  #{rec_id} | {vendor or 'NO VENDOR'} | {amt_str} | {payment or 'NO PAYMENT'}")
        
        # Search for "Runnin On Empty" on any date
        print("\n" + "="*100)
        print("Searching for 'Runnin On Empty' on ANY date...")
        
        cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                payment_method
            FROM receipts
            WHERE vendor_name ILIKE '%runn%' OR vendor_name ILIKE '%empty%'
            ORDER BY receipt_date
            LIMIT 20
        """)
        
        vendor_matches = cur.fetchall()
        
        if vendor_matches:
            print(f"\nFound {len(vendor_matches)} receipts for similar vendor:")
            for rec_id, date, vendor, amount, payment in vendor_matches:
                amt_str = f"${amount:.2f}" if amount else "$0.00"
                print(f"  #{rec_id} | {date} | {vendor} | {amt_str} | {payment or 'NO PAYMENT'}")
        
        # Search for $60.00 on Oct 03, 2012
        print("\n" + "="*100)
        print("Searching for $60.00 receipts on Oct 03, 2012...")
        
        cur.execute("""
            SELECT 
                receipt_id,
                vendor_name,
                description,
                gross_amount,
                payment_method
            FROM receipts
            WHERE receipt_date = '2012-10-03'
            AND gross_amount BETWEEN 59.99 AND 60.01
            ORDER BY receipt_id
        """)
        
        amount_matches = cur.fetchall()
        
        if amount_matches:
            print(f"\nFound {len(amount_matches)} $60.00 receipts on Oct 03, 2012:")
            for rec_id, vendor, desc, amount, payment in amount_matches:
                print(f"  #{rec_id} | {vendor or 'NO VENDOR'} | ${amount:.2f} | {payment or 'NO PAYMENT'}")
                print(f"  Description: {desc or 'None'}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
