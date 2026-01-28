#!/usr/bin/env python3
"""
Check Interac e-Transfer refunds from Outlook screenshots.
Extracts refund details and verifies their presence in charter_refunds table.
"""

import psycopg2
import os
import re
from datetime import datetime

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

# Interac e-Transfer refunds from Outlook screenshots
INTERAC_REFUNDS = [
    # From screenshot 1: Sept 30, 2025 - LARISSA KORPESHO
    {
        'date': '2025-09-30',
        'recipient': 'LARISSA KORPESHO',
        'amount': 200.00,
        'reference': 'C1AVJ8xRvU5G',
        'message': 'refund',
        'reserve_numbers': ['019371', '019372']  # User confirmed
    },
    # From screenshot 2: Sept 30, 2024 - One-time contact (liquor refund)
    {
        'date': '2024-09-30',
        'recipient': 'One-time contact',
        'amount': 52.50,
        'reference': 'CAjAmjuKtJ',
        'message': 'liquor refund'
    },
    # From screenshot 3: Aug 27, 2024 - ASHLEY ANDERSON
    {
        'date': '2024-08-27',
        'recipient': 'ASHLEY ANDERSON',
        'amount': 29.00,
        'reference': 'C1AkzAhzCM4qV',
        'message': 'refund'
    },
    # From screenshot 4: Aug 20, 2024 - One-time contact (refund)
    {
        'date': '2024-08-20',
        'recipient': 'One-time contact',
        'amount': 503.50,
        'reference': 'CA8XYeNE',
        'message': 'refund'
    },
    # From screenshot 5: July 29, 2024 - One-time contact (refund)
    {
        'date': '2024-07-29',
        'recipient': 'One-time contact',
        'amount': 280.00,
        'reference': 'CAWNNMq3',
        'message': 'refund'
    },
    # From screenshot 6: July 24, 2024 - CHRISTA LAPP (Rocky wedding)
    {
        'date': '2024-07-24',
        'recipient': 'CHRISTA LAPP',
        'amount': 240.00,
        'reference': 'C1AzCLI2mCaGK',
        'message': 'refund for Rocky wedding'
    },
]

def extract_reserve_number(text):
    """Extract reservation number from text."""
    if not text:
        return None
    
    patterns = [
        r'\bres(?:erve)?\s*#?\s*0?(\d{5,6})\b',
        r'\b0(\d{5})\b',
        r'\b(\d{6})\b'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            reserve_num = match.group(1)
            # Pad to 6 digits
            return reserve_num.zfill(6)
    
    return None

def search_client_by_name(conn, client_name):
    """Search for client by name."""
    if client_name == 'One-time contact':
        return None
    
    cur = conn.cursor()
    cur.execute("""
        SELECT client_id, client_name, email
        FROM clients
        WHERE client_name ILIKE %s
        OR client_name ILIKE %s
        LIMIT 3
    """, (f"%{client_name}%", f"%{client_name.split()[0]}%"))
    
    results = cur.fetchall()
    cur.close()
    return results

def find_recent_charters_for_client(conn, client_name, refund_date):
    """Find recent charters for a client around the refund date."""
    if client_name == 'One-time contact':
        return []
    
    cur = conn.cursor()
    # Search by name in notes or booking_notes
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.notes,
            EXTRACT(EPOCH FROM (%s::timestamp - c.charter_date::timestamp)) / 86400 as days_after
        FROM charters c
        WHERE (c.notes ILIKE %s OR c.booking_notes ILIKE %s)
        AND c.charter_date <= %s
        AND c.charter_date >= %s::date - INTERVAL '90 days'
        ORDER BY c.charter_date DESC
        LIMIT 5
    """, (refund_date, f"%{client_name}%", f"%{client_name}%", refund_date, refund_date))
    
    results = cur.fetchall()
    cur.close()
    return results

def check_refund_in_database(conn, refund_info):
    """Check if refund exists in charter_refunds table."""
    cur = conn.cursor()
    
    amount = refund_info['amount']
    refund_date = refund_info['date']
    recipient = refund_info['recipient']
    
    # Search by amount within 7 days of the refund date
    cur.execute("""
        SELECT 
            cr.id,
            cr.refund_date,
            cr.amount,
            cr.reserve_number,
            cr.charter_id,
            cr.description,
            cr.source_file,
            EXTRACT(EPOCH FROM (cr.refund_date::timestamp - %s::timestamp)) / 86400 as days_diff
        FROM charter_refunds cr
        WHERE ABS(cr.amount - %s) < 0.01
        AND ABS(EXTRACT(EPOCH FROM (cr.refund_date::timestamp - %s::timestamp))) < 7 * 86400
        ORDER BY ABS(EXTRACT(EPOCH FROM (cr.refund_date::timestamp - %s::timestamp)))
        LIMIT 5
    """, (refund_date, amount, refund_date, refund_date))
    
    matches = cur.fetchall()
    
    # Also search by reference number in description
    cur.execute("""
        SELECT 
            cr.id,
            cr.refund_date,
            cr.amount,
            cr.reserve_number,
            cr.charter_id,
            cr.description,
            cr.source_file
        FROM charter_refunds cr
        WHERE cr.description ILIKE %s
        LIMIT 3
    """, (f"%{refund_info['reference']}%",))
    
    ref_matches = cur.fetchall()
    
    cur.close()
    return matches, ref_matches

def main():
    conn = get_db_connection()
    
    print("=" * 80)
    print("INTERAC E-TRANSFER REFUNDS FROM OUTLOOK")
    print("=" * 80)
    print(f"\nTotal refunds to check: {len(INTERAC_REFUNDS)}")
    print(f"Total amount: ${sum(r['amount'] for r in INTERAC_REFUNDS):,.2f}")
    print()
    
    found_linked = 0
    found_unlinked = 0
    not_found = 0
    
    for i, refund in enumerate(INTERAC_REFUNDS, 1):
        print(f"\n{'='*80}")
        print(f"Refund {i}/{len(INTERAC_REFUNDS)}")
        print(f"{'='*80}")
        print(f"Date: {refund['date']}")
        print(f"Recipient: {refund['recipient']}")
        print(f"Amount: ${refund['amount']:,.2f}")
        print(f"Reference: {refund['reference']}")
        print(f"Message: '{refund['message']}'")
        
        # Check if message contains reservation info
        reserve_in_message = extract_reserve_number(refund['message'])
        if reserve_in_message:
            print(f"  🎯 RESERVATION IN MESSAGE: {reserve_in_message}")
        
        amount_matches, ref_matches = check_refund_in_database(conn, refund)
        
        if amount_matches or ref_matches:
            # Prioritize reference matches
            if ref_matches:
                print(f"\n[OK] FOUND BY REFERENCE NUMBER:")
                for match in ref_matches:
                    refund_id, date, amt, reserve, charter_id, desc, source = match
                    status = "[OK] LINKED" if reserve else "[WARN] UNLINKED"
                    print(f"  {status}")
                    print(f"    Refund ID: {refund_id}")
                    print(f"    Date: {date}")
                    print(f"    Amount: ${amt:,.2f}")
                    print(f"    Reserve: {reserve or 'NOT LINKED'}")
                    print(f"    Charter ID: {charter_id or 'NOT LINKED'}")
                    print(f"    Description: {desc or 'N/A'}")
                    print(f"    Source: {source or 'N/A'}")
                    
                    if reserve:
                        found_linked += 1
                    else:
                        found_unlinked += 1
            
            elif amount_matches:
                print(f"\n[OK] FOUND BY AMOUNT (within 7 days):")
                for match in amount_matches:
                    refund_id, date, amt, reserve, charter_id, desc, source, days_diff = match
                    status = "[OK] LINKED" if reserve else "[WARN] UNLINKED"
                    print(f"  {status}")
                    print(f"    Refund ID: {refund_id}")
                    print(f"    Date: {date} (days difference: {days_diff:.1f})")
                    print(f"    Amount: ${amt:,.2f}")
                    print(f"    Reserve: {reserve or 'NOT LINKED'}")
                    print(f"    Charter ID: {charter_id or 'NOT LINKED'}")
                    print(f"    Description: {desc or 'N/A'}")
                    print(f"    Source: {source or 'N/A'}")
                    
                    if reserve:
                        found_linked += 1
                    else:
                        found_unlinked += 1
        else:
            print(f"\n[FAIL] NOT FOUND IN charter_refunds")
            not_found += 1
            
            # Check if user provided reserve numbers
            if 'reserve_numbers' in refund and refund['reserve_numbers']:
                print(f"\n🎯 USER-PROVIDED RESERVE NUMBERS:")
                for reserve in refund['reserve_numbers']:
                    # Verify charter exists
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT charter_id, reserve_number, charter_date, 
                               total_amount_due, paid_amount, balance
                        FROM charters
                        WHERE reserve_number = %s
                    """, (reserve,))
                    charter = cur.fetchone()
                    cur.close()
                    
                    if charter:
                        charter_id, reserve_num, charter_date, total, paid, balance = charter
                        print(f"  [OK] Reserve {reserve_num} → Charter {charter_id}")
                        print(f"     Date: {charter_date}")
                        print(f"     Total: ${total:,.2f}, Paid: ${paid:,.2f}, Balance: ${balance:,.2f}")
                    else:
                        print(f"  [FAIL] Reserve {reserve} NOT FOUND in charters table")
            
            # Search for client and recent charters
            client_results = search_client_by_name(conn, refund['recipient'])
            if client_results:
                print(f"\n📋 CLIENT SEARCH RESULTS:")
                for client_id, client_name, email in client_results:
                    print(f"  Client ID: {client_id}")
                    print(f"  Name: {client_name}")
                    print(f"  Email: {email or 'N/A'}")
            
            # Find recent charters
            charter_results = find_recent_charters_for_client(conn, refund['recipient'], refund['date'])
            if charter_results:
                print(f"\n📅 RECENT CHARTERS (within 90 days before refund):")
                for charter_id, reserve, charter_date, total, paid, balance, notes, days_after in charter_results:
                    print(f"  Charter ID: {charter_id}, Reserve: {reserve}")
                    print(f"    Date: {charter_date} ({days_after:.0f} days before refund)")
                    print(f"    Amount: ${total:,.2f}, Paid: ${paid:,.2f}, Balance: ${balance:,.2f}")
                    if notes:
                        print(f"    Notes: {notes[:100]}")
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total Interac refunds checked: {len(INTERAC_REFUNDS)}")
    print(f"Found and linked: {found_linked}")
    print(f"Found but unlinked: {found_unlinked}")
    print(f"Not found in database: {not_found}")
    print(f"\nNext steps:")
    if not_found > 0:
        print(f"  - Add {not_found} missing refund(s) to charter_refunds")
    if found_unlinked > 0:
        print(f"  - Link {found_unlinked} unlinked refund(s) to charters")
    
    conn.close()

if __name__ == '__main__':
    main()
