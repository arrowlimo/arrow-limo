#!/usr/bin/env python3
"""
Find remaining WCB invoices to link to TX 69282 ($3446.02).
We've already linked $1134.16, so we need ~$2311.86 more.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FINDING REMAINING WCB INVOICES FOR $3446.02 PAYMENT")
    print("="*80)
    
    print("\n1. Already linked:")
    cur.execute("""
        SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.description, r.source_reference
        FROM receipts r
        WHERE r.banking_transaction_id = 69282
        ORDER BY r.receipt_date ASC
    """)
    rows = cur.fetchall()
    linked_total = 0.0
    for rec_id, rec_date, amount, desc, src_ref in rows:
        linked_total += float(amount)
        print(f"  Receipt {rec_id}: {rec_date} | ${float(amount):>8.2f} | {desc[:40]}")
    
    print(f"\nTotal linked: ${linked_total:.2f}")
    
    # Now find unlinked WCB invoices from 2012
    print("\n2. Available unlinked WCB invoices (2012):")
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, description, source_reference
        FROM receipts
        WHERE vendor_name ILIKE '%wcb%'
          AND receipt_date >= '2012-01-01' AND receipt_date <= '2012-09-30'
          AND banking_transaction_id IS NULL
          AND gross_amount > 0
        ORDER BY receipt_date ASC
    """)
    
    unlinked = cur.fetchall()
    unlinked_total = 0.0
    for rec_id, rec_date, amount, desc, src_ref in unlinked:
        amt_f = float(amount)
        unlinked_total += amt_f
        desc_str = (desc[:40] if desc else "")
        print(f"  Receipt {rec_id}: {rec_date} | ${amt_f:>8.2f} | Ref: {src_ref} | {desc_str}")
    
    print(f"\nTotal available: ${unlinked_total:.2f}")
    
    payment_needed = 3446.02 - linked_total
    print(f"\nPayment target: $3446.02")
    print(f"Linked so far:  ${linked_total:.2f}")
    print(f"Need to link:   ${payment_needed:.2f}")
    print(f"Unlinked available: ${unlinked_total:.2f}")
    
    if unlinked_total >= payment_needed:
        print(f"\n✓ ENOUGH INVOICES AVAILABLE")
        # Suggest which ones to link
        print(f"\nSuggestion: Link these invoices (sorted by date):")
        running_total = 0.0
        for rec_id, rec_date, amount, desc, src_ref in unlinked:
            amt_f = float(amount)
            if running_total + amt_f <= payment_needed + 0.10:
                running_total += amt_f
                print(f"  Receipt {rec_id}: {rec_date} | ${amt_f:>8.2f} | {src_ref}")
                if abs(running_total - payment_needed) < 0.50:
                    break
        print(f"\nTotal: ${running_total:.2f}")
    else:
        print(f"\n❌ NOT ENOUGH - Missing ${payment_needed - unlinked_total:.2f}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
