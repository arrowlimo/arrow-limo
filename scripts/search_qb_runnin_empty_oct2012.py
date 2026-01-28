#!/usr/bin/env python3
"""
Search QuickBooks imports for Run'n On Empty receipt around Oct 03, 2012
Check general ledger and other QB sources
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
    print("SEARCHING QUICKBOOKS IMPORTS FOR RUN'N ON EMPTY - OCT 2012")
    print("="*100)
    
    # Search for Run'n On Empty in October 2012 from any source
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
            banking_transaction_id
        FROM receipts
        WHERE (vendor_name ILIKE '%run%' AND vendor_name ILIKE '%empty%')
        AND receipt_date >= '2012-09-25'
        AND receipt_date <= '2012-10-10'
        ORDER BY receipt_date, receipt_id
    """)
    
    receipts = cur.fetchall()
    
    if receipts:
        print(f"\nFound {len(receipts)} Run'n On Empty receipts between Sept 25 - Oct 10, 2012:")
        print("="*100)
        
        for rec in receipts:
            (rec_id, date, vendor, desc, gross, gst, net, payment, 
             source, src_ref, bank_tx) = rec
            
            print(f"\nReceipt ID: {rec_id}")
            print(f"Date: {date}")
            print(f"Vendor: {vendor}")
            print(f"Description: {desc or 'None'}")
            
            if gross:
                print(f"Gross Amount: ${gross:.2f}")
                if gst:
                    print(f"  GST: ${gst:.2f}")
                    print(f"  Net: ${net:.2f}")
            else:
                print("Amount: NULL")
            
            print(f"Payment Method: {payment or 'NOT SET'}")
            print(f"Source System: {source or 'UNKNOWN'}")
            print(f"Source Reference: {src_ref or 'None'}")
            print(f"Banking TX: {bank_tx or 'NOT LINKED'}")
            
            # Check if this could be the $60 receipt
            if gross and abs(gross - 60.00) < 0.01:
                print("\n*** POSSIBLE MATCH - $60.00 ***")
            
            print("-" * 100)
    else:
        print("\nNo Run'n On Empty receipts found in late Sept / early Oct 2012")
    
    # Check for cash purchases around that time
    print("\n" + "="*100)
    print("CHECKING FOR CASH PURCHASES AROUND OCT 03, 2012")
    print("="*100)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            payment_method,
            source_system
        FROM receipts
        WHERE receipt_date BETWEEN '2012-10-01' AND '2012-10-05'
        AND (payment_method ILIKE '%cash%' 
             OR description ILIKE '%cash%'
             OR source_reference ILIKE '%cash%')
        ORDER BY receipt_date, receipt_id
    """)
    
    cash_receipts = cur.fetchall()
    
    if cash_receipts:
        print(f"\nFound {len(cash_receipts)} cash receipts Oct 01-05, 2012:")
        for rec_id, date, vendor, amount, payment, source in cash_receipts:
            amt_str = f"${amount:.2f}" if amount else "NULL"
            print(f"  #{rec_id} | {date} | {vendor or 'NO VENDOR'} | {amt_str} | {payment} | {source}")
    else:
        print("\nNo cash receipts found Oct 01-05, 2012")
    
    # Check general ledger entries (QuickBooks imports)
    print("\n" + "="*100)
    print("CHECKING GENERAL LEDGER IMPORTS FOR RUN'N ON EMPTY")
    print("="*100)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            source_system,
            source_reference
        FROM receipts
        WHERE (vendor_name ILIKE '%run%' AND vendor_name ILIKE '%empty%')
        AND source_system LIKE '%general_ledger%'
        AND receipt_date >= '2012-10-01'
        AND receipt_date <= '2012-10-31'
        ORDER BY receipt_date
    """)
    
    gl_entries = cur.fetchall()
    
    if gl_entries:
        print(f"\nFound {len(gl_entries)} General Ledger entries for Run'n On Empty in Oct 2012:")
        for rec_id, date, vendor, amount, source, ref in gl_entries:
            amt_str = f"${amount:.2f}" if amount else "NULL"
            print(f"  #{rec_id} | {date} | {vendor} | {amt_str}")
            print(f"    Source: {source}")
            print(f"    Ref: {ref}")
    else:
        print("\nNo General Ledger entries found")
    
    # Check for accountant-verified receipts
    print("\n" + "="*100)
    print("CHECKING FOR VERIFIED RECEIPTS (All vendors, Oct 2012)")
    print("="*100)
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE receipt_date >= '2012-10-01'
        AND receipt_date <= '2012-10-31'
        AND source_system IS NOT NULL
    """)
    
    count, total = cur.fetchone()
    print(f"\nTotal October 2012 receipts: {count}")
    print(f"Total amount: ${total:.2f}" if total else "Total amount: NULL")
    
    # Show source breakdown
    cur.execute("""
        SELECT source_system, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE receipt_date >= '2012-10-01'
        AND receipt_date <= '2012-10-31'
        AND source_system IS NOT NULL
        GROUP BY source_system
        ORDER BY COUNT(*) DESC
    """)
    
    sources = cur.fetchall()
    
    print("\nBreakdown by source system:")
    for source, cnt, amt in sources:
        amt_str = f"${amt:.2f}" if amt else "NULL"
        print(f"  {source}: {cnt} receipts, {amt_str}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
