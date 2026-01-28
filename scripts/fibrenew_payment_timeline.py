"""
Generate Fibrenew invoice-to-payment timeline showing which payments covered which invoices.
"""
import psycopg2
import pandas as pd
from datetime import datetime


def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )
    cur = conn.cursor()

    # Get all Fibrenew receipts (both banking and cash)
    cur.execute(
        """
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            created_from_banking,
            category
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        ORDER BY receipt_date ASC, receipt_id ASC
    """
    )

    receipts = cur.fetchall()

    # Get linked banking transactions for context
    cur.execute(
        """
        SELECT 
            r.receipt_id,
            bt.transaction_date,
            bt.description as banking_desc,
            bt.debit_amount,
            bt.credit_amount
        FROM receipts r
        JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        JOIN banking_transactions bt ON bm.banking_transaction_id = bt.transaction_id
        WHERE LOWER(r.vendor_name) LIKE '%fibrenew%'
        ORDER BY bt.transaction_date ASC
    """
    )

    banking_links = {row[0]: row for row in cur.fetchall()}

    cur.close()
    conn.close()

    # Build timeline
    print("=" * 120)
    print("FIBRENEW PAYMENT TIMELINE")
    print("=" * 120)
    print()

    total_paid = 0.0
    invoice_map = {}  # Track invoices mentioned in descriptions

    for receipt_id, receipt_date, vendor_name, amount, description, created_from_banking, category in receipts:
        banking_info = banking_links.get(receipt_id)
        
        # Determine payment type
        if created_from_banking:
            payment_type = "BANKING"
        else:
            payment_type = "CASH"

        total_paid += float(amount)

        # Extract invoice number if present in description
        invoice_ref = "N/A"
        if description:
            parts = description.split()
            for part in parts:
                if part.startswith("invoice") or part.startswith("inv"):
                    invoice_ref = part
                    break

        print(f"Date:           {receipt_date}")
        print(f"Receipt ID:     {receipt_id}")
        print(f"Amount:         ${amount:,.2f}")
        print(f"Type:           {payment_type}")
        if banking_info:
            print(f"Banking Date:   {banking_info[1]}")
            print(f"Banking Desc:   {banking_info[2]}")
        print(f"Invoice Ref:    {invoice_ref}")
        print(f"Notes:          {description}")
        print(f"Running Total:  ${total_paid:,.2f}")
        print("-" * 120)

    print()
    print(f"SUMMARY")
    print(f"Total Fibrenew Payments (Receipts): ${total_paid:,.2f}")
    print(f"Total Receipt Count: {len(receipts)}")
    print()

    # Banking vs Cash breakdown
    banking_count = sum(1 for r in receipts if r[5])
    cash_count = len(receipts) - banking_count
    banking_total = sum(r[3] for r in receipts if r[5])
    cash_total = sum(r[3] for r in receipts if not r[5])

    print(f"Banking Payments: {banking_count} receipts, ${banking_total:,.2f}")
    print(f"Cash Payments:    {cash_count} receipts, ${cash_total:,.2f}")
    print()
    print("Note: To determine remaining balance owed, cross-reference with Fibrenew invoices.")
    print("Outstanding invoices not yet paid should be identified from vendor statement.")


if __name__ == "__main__":
    main()
