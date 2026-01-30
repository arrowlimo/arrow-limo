"""Search for '#37IX' reference in Kevin Balanski reservations and payment records.

Target: client_name LIKE '%Balanski%' OR '%Kevin%'
Search fields: notes, status, payment_key, reference_number, description, square_transaction_id, etc.
"""
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

SEARCH_TERM = '37IX'

def get_conn():
    return psycopg2.connect(**DB)

def main():
    conn = get_conn()
    cur = conn.cursor()

    # Find client_id(s) for Balanski
    cur.execute("""
        SELECT client_id, client_name, email
        FROM clients
        WHERE LOWER(client_name) LIKE '%balanski%' OR LOWER(client_name) LIKE '%kevin%'
    """)
    clients = cur.fetchall()

    print("="*100)
    print("Search for '#37IX' in Kevin Balanski Records")
    print("="*100)
    
    if clients:
        print(f"\nFound {len(clients)} matching client(s):")
        for cid, name, email in clients:
            print(f"  Client ID {cid}: {name} | {email or ''}")
        client_ids = [c[0] for c in clients]
    else:
        print("No client records found matching 'Balanski' or 'Kevin'. Searching all records for '37IX'.")
        client_ids = []

    # Search charters
    if client_ids:
        cur.execute("""
            SELECT reserve_number, charter_date, client_id, total_amount_due, paid_amount, balance, 
                   status, cancelled, notes
            FROM charters
            WHERE client_id = ANY(%s)
               OR LOWER(COALESCE(notes,'')) LIKE %s
            ORDER BY charter_date DESC NULLS LAST
        """, (client_ids, f'%{SEARCH_TERM.lower()}%'))
    else:
        cur.execute("""
            SELECT reserve_number, charter_date, client_id, total_amount_due, paid_amount, balance,
                   status, cancelled, notes
            FROM charters
            WHERE LOWER(COALESCE(notes,'')) LIKE %s
            ORDER BY charter_date DESC NULLS LAST
        """, (f'%{SEARCH_TERM.lower()}%',))
    
    charters = cur.fetchall()
    
    print(f"\n{'='*100}")
    print(f"CHARTERS for Balanski/Kevin (or containing '{SEARCH_TERM}'):")
    print(f"{'='*100}")
    if charters:
        for res, cdate, cid, total, paid, bal, status, cancelled, notes in charters:
            match_flag = f"  *** CONTAINS {SEARCH_TERM} ***" if SEARCH_TERM.lower() in (notes or '').lower() else ''
            total_str = f"{total:.2f}" if total is not None else "NULL"
            paid_str = f"{paid:.2f}" if paid is not None else "NULL"
            bal_str = f"{bal:.2f}" if bal is not None else "NULL"
            print(f"Reserve {res} | Date {cdate} | Client ID {cid} | Total {total_str} Paid {paid_str} Bal {bal_str}")
            print(f"  Status: {status or ''} | Cancelled: {cancelled} | Notes: {(notes or '')[:200]}{match_flag}")
    else:
        print("No charters found.")

    # Search payments
    if client_ids:
        cur.execute("""
            SELECT payment_id, reserve_number, amount, payment_date, payment_method, payment_key,
                   reference_number, status, notes, square_transaction_id
            FROM payments
            WHERE client_id = ANY(%s)
               OR LOWER(COALESCE(notes,'')) LIKE %s
               OR LOWER(COALESCE(payment_key,'')) LIKE %s
               OR LOWER(COALESCE(reference_number,'')) LIKE %s
               OR LOWER(COALESCE(status,'')) LIKE %s
            ORDER BY payment_date DESC NULLS LAST
        """, (client_ids, f'%{SEARCH_TERM.lower()}%', f'%{SEARCH_TERM.lower()}%', f'%{SEARCH_TERM.lower()}%', f'%{SEARCH_TERM.lower()}%'))
    else:
        cur.execute("""
            SELECT payment_id, reserve_number, amount, payment_date, payment_method, payment_key,
                   reference_number, status, notes, square_transaction_id
            FROM payments
            WHERE LOWER(COALESCE(notes,'')) LIKE %s
               OR LOWER(COALESCE(payment_key,'')) LIKE %s
               OR LOWER(COALESCE(reference_number,'')) LIKE %s
               OR LOWER(COALESCE(status,'')) LIKE %s
            ORDER BY payment_date DESC NULLS LAST
        """, (f'%{SEARCH_TERM.lower()}%', f'%{SEARCH_TERM.lower()}%', f'%{SEARCH_TERM.lower()}%', f'%{SEARCH_TERM.lower()}%'))
    
    payments = cur.fetchall()

    print(f"\n{'='*100}")
    print(f"PAYMENTS for Balanski/Kevin (or containing '{SEARCH_TERM}'):")
    print(f"{'='*100}")
    if payments:
        for pid, res, amt, pdate, method, pkey, ref, status, notes, sq_txn in payments:
            fields_with_match = []
            if SEARCH_TERM.lower() in (notes or '').lower():
                fields_with_match.append('notes')
            if SEARCH_TERM.lower() in (pkey or '').lower():
                fields_with_match.append('payment_key')
            if SEARCH_TERM.lower() in (ref or '').lower():
                fields_with_match.append('reference_number')
            if SEARCH_TERM.lower() in (status or '').lower():
                fields_with_match.append('status')
            match_flag = f"  *** MATCH in: {', '.join(fields_with_match)} ***" if fields_with_match else ''
            amt_str = f"{amt:.2f}" if amt is not None else "NULL"
            print(f"Payment ID {pid} | Reserve {res or 'NULL'} | Amount {amt_str} | Date {pdate}")
            print(f"  Method: {method or ''} | Key: {pkey or ''} | Ref: {ref or ''} | Status: {status or ''}")
            print(f"  Notes: {(notes or '')[:150]}{match_flag}")
            if sq_txn:
                print(f"  Square Txn: {sq_txn}")
    else:
        print("No payments found.")

    # Search charter_charges (descriptions might contain reference)
    if client_ids:
        cur.execute("""
            SELECT cc.charge_id, cc.charter_id, c.reserve_number, cc.description, cc.amount
            FROM charter_charges cc
            JOIN charters c ON c.charter_id = cc.charter_id
            WHERE c.client_id = ANY(%s)
               OR LOWER(COALESCE(cc.description,'')) LIKE %s
            ORDER BY cc.charge_id DESC
        """, (client_ids, f'%{SEARCH_TERM.lower()}%'))
    else:
        cur.execute("""
            SELECT cc.charge_id, cc.charter_id, c.reserve_number, cc.description, cc.amount
            FROM charter_charges cc
            JOIN charters c ON c.charter_id = cc.charter_id
            WHERE LOWER(COALESCE(cc.description,'')) LIKE %s
            ORDER BY cc.charge_id DESC
        """, (f'%{SEARCH_TERM.lower()}%',))
    
    charges = cur.fetchall()

    print(f"\n{'='*100}")
    print(f"CHARTER CHARGES for Balanski/Kevin (or containing '{SEARCH_TERM}'):")
    print(f"{'='*100}")
    if charges:
        for charge_id, charter_id, res, desc, amt in charges:
            match_flag = f"  *** CONTAINS {SEARCH_TERM} ***" if SEARCH_TERM.lower() in (desc or '').lower() else ''
            amt_str = f"{amt:.2f}" if amt is not None else "NULL"
            print(f"Charge ID {charge_id} | Charter {charter_id} Reserve {res} | Amount {amt_str}")
            print(f"  Description: {desc or ''}{match_flag}")
    else:
        print("No charter charges found.")

    print(f"\n{'='*100}")
    print("Summary:")
    print(f"  Clients matching Balanski/Kevin: {len(clients)}")
    print(f"  Charters: {len(charters)}")
    print(f"  Payments: {len(payments)}")
    print(f"  Charter Charges: {len(charges)}")
    
    # Highlight direct matches
    direct_match_count = 0
    for _, _, _, _, _, _, _, _, notes in charters:
        if SEARCH_TERM.lower() in (notes or '').lower():
            direct_match_count += 1
    for _, _, _, _, _, pkey, ref, status, notes, _ in payments:
        if any(SEARCH_TERM.lower() in (f or '').lower() for f in [notes, pkey, ref, status]):
            direct_match_count += 1
    for _, _, _, desc, _ in charges:
        if SEARCH_TERM.lower() in (desc or '').lower():
            direct_match_count += 1
    
    print(f"  Direct matches containing '{SEARCH_TERM}': {direct_match_count}")
    print("="*100)

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
