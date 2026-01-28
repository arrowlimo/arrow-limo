#!/usr/bin/env python3
"""
Compare FAS GAS and RUN'N ON EMPTY transactions in detail.
Look at full descriptions, timing, and transaction details.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 140)
    print("DETAILED COMPARISON: FAS GAS vs RUN'N ON EMPTY (09/17/2012)")
    print("=" * 140)
    
    # Get RUN'N ON EMPTY (69336)
    print("\n🔵 BANKING ID 69336: RUN'N ON EMPTY")
    print("-" * 140)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            vendor_extracted,
            business_personal,
            card_last4_detected,
            reconciliation_status,
            reconciled_receipt_id
        FROM banking_transactions
        WHERE transaction_id = 69336
    """)
    
    txn = cur.fetchone()
    if txn:
        tid, tdate, pdate, desc, damt, camt, vendor, bus_pers, card4, recon_status, recon_rec = txn
        amt = damt if damt and damt > 0 else camt
        print(f"Transaction ID: {tid}")
        print(f"Date: {tdate}")
        print(f"Posted: {pdate}")
        print(f"Full Description: {desc}")
        print(f"Amount: ${amt:.2f}")
        print(f"Vendor (extracted): {vendor}")
        print(f"Business/Personal: {bus_pers}")
        print(f"Card Last 4: {card4}")
        print(f"Reconciliation Status: {recon_status}")
        print(f"Linked to Receipt ID: {recon_rec}")
    
    # Get FISHER ST STATION (69333)
    print("\n" + "=" * 140)
    print("🟢 BANKING ID 69333: FISHER ST STATION ON (likely SHELL)")
    print("-" * 140)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            posted_date,
            description,
            debit_amount,
            credit_amount,
            vendor_extracted,
            business_personal,
            card_last4_detected,
            reconciliation_status,
            reconciled_receipt_id
        FROM banking_transactions
        WHERE transaction_id = 69333
    """)
    
    txn = cur.fetchone()
    if txn:
        tid, tdate, pdate, desc, damt, camt, vendor, bus_pers, card4, recon_status, recon_rec = txn
        amt = damt if damt and damt > 0 else camt
        print(f"Transaction ID: {tid}")
        print(f"Date: {tdate}")
        print(f"Posted: {pdate}")
        print(f"Full Description: {desc}")
        print(f"Amount: ${amt:.2f}")
        print(f"Vendor (extracted): {vendor}")
        print(f"Business/Personal: {bus_pers}")
        print(f"Card Last 4: {card4}")
        print(f"Reconciliation Status: {recon_status}")
        print(f"Linked to Receipt ID: {recon_rec}")
    
    # Get ALL receipts for these vendors
    print("\n" + "=" * 140)
    print("RECEIPTS IN SYSTEM - MATCHING VENDORS")
    print("=" * 140)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category,
            description,
            parent_receipt_id,
            banking_transaction_id
        FROM receipts
        WHERE vendor_name IN ('FAS GAS', 'FAS GAS PLUS', 'RUN''N ON EMPTY', 'FUEL STATION')
        AND EXTRACT(YEAR FROM receipt_date) = 2012
        AND EXTRACT(MONTH FROM receipt_date) = 9
        ORDER BY receipt_date, receipt_id
    """)
    
    receipts = cur.fetchall()
    print(f"\nFound {len(receipts)} receipts:\n")
    for rec in receipts:
        rid, rdate, vendor, amt, cat, desc, parent, bank_id = rec
        parent_str = f"(child of {parent})" if parent else "(parent)"
        bank_str = f"→ Banking {bank_id}" if bank_id else "(no banking link)"
        print(f"Receipt {rid:6} | {rdate} | {vendor:25} | ${amt:>10.2f} | {parent_str:20} | {bank_str}")
        print(f"    Description: {desc}")
    
    # Key question: Are there TWO SEPARATE gas station purchases on 09/15?
    print("\n" + "=" * 140)
    print("KEY QUESTION: Are FAS GAS and RUN'N ON EMPTY two different purchases?")
    print("=" * 140)
    
    print("""
Observations:

1. TIMING:
   - FAS GAS: 18:55:29 (6:55:29 PM)
   - RUN'N ON EMPTY: 19:04 (7:04 PM) - 9 minutes later

2. PAYMENT METHOD:
   - FAS GAS: Has INTERAC coding (debit card)
   - RUN'N ON EMPTY: No INTERAC coding (possibly cash or different method)

3. RECEIPTS:
   - FAS GAS: Shows 1 fuel purchase
   - RUN'N ON EMPTY: Shows 3 separate purchases

4. LOCATION:
   - Both at SAME ADDRESS

POSSIBLE INTERPRETATIONS:

A) TWO DIFFERENT TRANSACTIONS at same location
   - Driver went to station at 18:55 (FAS GAS INTERAC)
   - Then again at 19:04 (RUN'N ON EMPTY cash/different payment)
   - Total: $135 + $135 = $270 in one visit

B) ONE TRANSACTION shown two ways
   - Bank exported it as both FAS GAS and RUN'N ON EMPTY
   - One is a DUPLICATE in banking data
   - Total: Only $135

C) FAS GAS is a DIFFERENT vendor, RUN'N ON EMPTY is the actual station
   - FAS GAS might be a rewards program or brand overlay
   - RUN'N ON EMPTY is the same physical location
   - One receipt ($135) split into 3 child components
""")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
