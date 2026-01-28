#!/usr/bin/env python3
"""
Verification report for vendor reference updates
"""
import psycopg2
import pandas as pd

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
    
    print("="*80)
    print("VENDOR REFERENCE UPDATE VERIFICATION REPORT")
    print("="*80)
    
    # NSF cheques
    print("\n" + "="*80)
    print("NSF CHEQUES (is_nsf = TRUE)")
    print("="*80)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            bt.transaction_date,
            bt.description,
            r.vendor_name,
            r.gross_amount,
            r.comment,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.is_nsf = TRUE
        ORDER BY bt.transaction_date
    """)
    
    nsf_rows = cur.fetchall()
    if nsf_rows:
        for row in nsf_rows:
            print(f"\nReceipt #{row[0]} | Date: {row[1]} | Amount: ${row[4]:.2f}")
            print(f"  Description: {row[2]}")
            print(f"  Vendor: {row[5] if row[5] else 'N/A'}")
            if row[5]:
                print(f"  Notes: {row[5]}")
            print(f"  Banking TX: {row[6]}")
    else:
        print("No NSF cheques found")
    
    # Voided cheques
    print("\n" + "="*80)
    print("VOIDED CHEQUES (is_voided = TRUE)")
    print("="*80)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            bt.transaction_date,
            bt.description,
            r.vendor_name,
            r.gross_amount,
            r.comment,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.is_voided = TRUE
        ORDER BY bt.transaction_date
    """)
    
    void_rows = cur.fetchall()
    if void_rows:
        for row in void_rows:
            print(f"\nReceipt #{row[0]} | Date: {row[1]} | Amount: ${row[4]:.2f}")
            print(f"  Description: {row[2]}")
            print(f"  Vendor: {row[3]}")
            if row[5]:
                print(f"  Notes: {row[5]}")
            print(f"  Banking TX: {row[6]}")
    else:
        print("No voided cheques found")
    
    # Donations
    print("\n" + "="*80)
    print("DONATIONS")
    print("="*80)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            bt.transaction_date,
            bt.description,
            r.vendor_name,
            r.gross_amount,
            r.comment,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.comment ILIKE '%DONATION%'
        ORDER BY bt.transaction_date
    """)
    
    donation_rows = cur.fetchall()
    if donation_rows:
        for row in donation_rows:
            print(f"\nReceipt #{row[0]} | Date: {row[1]} | Amount: ${row[4]:.2f}")
            print(f"  Description: {row[2]}")
            print(f"  Vendor: {row[3]}")
            print(f"  Notes: {row[5]}")
            print(f"  Banking TX: {row[6]}")
    else:
        print("No donations found")
    
    # Loans/Personal payments (Karen Richard)
    print("\n" + "="*80)
    print("LOANS / PERSONAL PAYMENTS")
    print("="*80)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            bt.transaction_date,
            bt.description,
            r.vendor_name,
            r.gross_amount,
            r.comment,
            bt.transaction_id,
            r.is_nsf
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.comment ILIKE '%LOAN%' OR r.vendor_name ILIKE '%karen richard%'
        ORDER BY bt.transaction_date
    """)
    
    loan_rows = cur.fetchall()
    if loan_rows:
        total_loan = 0
        for row in loan_rows:
            nsf_flag = " [NSF]" if row[7] else ""
            print(f"\nReceipt #{row[0]} | Date: {row[1]} | Amount: ${row[4]:.2f}{nsf_flag}")
            print(f"  Description: {row[2]}")
            print(f"  Vendor: {row[3]}")
            print(f"  Notes: {row[5]}")
            print(f"  Banking TX: {row[6]}")
            if not row[7]:  # Don't count NSF cheques
                total_loan += float(row[4])
        
        print(f"\n{'='*80}")
        print(f"TOTAL LOANS/PERSONAL (excluding NSF): ${total_loan:.2f}")
    else:
        print("No loans/personal payments found")
    
    # Recently updated vendor names
    print("\n" + "="*80)
    print("VENDOR NAMES FROM XLS UPDATE")
    print("="*80)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            bt.transaction_date,
            bt.description,
            r.vendor_name,
            r.gross_amount,
            bt.transaction_id
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.transaction_id IN (69110, 80023, 80228, 80227)
        ORDER BY bt.transaction_date
    """)
    
    vendor_rows = cur.fetchall()
    for row in vendor_rows:
        print(f"\nReceipt #{row[0]} | Date: {row[1]} | Amount: ${row[4]:.2f}")
        print(f"  Description: {row[2]}")
        print(f"  Vendor: {row[3]}")
        print(f"  Banking TX: {row[5]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
