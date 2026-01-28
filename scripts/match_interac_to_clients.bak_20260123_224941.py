"""
Match unmatched Interac e-Transfer payments against clients and employees.

Barb Peacock = personal entries (exclude)
Check others against:
1. Client names
2. Employee names
3. Find potential charter matches by name + date + amount
"""

import psycopg2
import os
import re

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def extract_name_from_interac_notes(notes):
    """Extract sender name from Interac e-Transfer notes."""
    if not notes:
        return None
    
    # Pattern: "INTERAC e-Transfer: [NAME] sent you money"
    match = re.search(r'INTERAC e-Transfer:\s*([^s]+)\s+sent you money', notes, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def analyze_interac_payments():
    """Analyze Interac e-Transfer payments against clients and employees."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("INTERAC E-TRANSFER PAYMENT ANALYSIS")
    print("=" * 120)
    print()
    
    # Get all unmatched Interac payments
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_key, notes
        FROM payments
        WHERE charter_id IS NULL
          AND notes ILIKE '%INTERAC e-Transfer%'
        ORDER BY payment_date DESC
    """)
    
    interac_payments = cur.fetchall()
    print(f"Total unmatched Interac e-Transfer payments: {len(interac_payments)}")
    print()
    
    # Extract names and categorize
    personal_entries = []
    potential_client_matches = []
    potential_employee_matches = []
    unknown = []
    
    for row in interac_payments:
        pid, pdate, amount, pkey, notes = row
        sender_name = extract_name_from_interac_notes(notes)
        
        if not sender_name:
            unknown.append((row, 'Could not extract name'))
            continue
        
        # Check if it's Barb Peacock (personal)
        if 'barb peacock' in sender_name.lower() or 'peacock' in sender_name.lower():
            personal_entries.append((row, sender_name))
            continue
        
        # Check against clients
        cur.execute("""
            SELECT client_id, client_name, account_number
            FROM clients
            WHERE LOWER(client_name) LIKE %s
               OR LOWER(client_name) LIKE %s
            LIMIT 5
        """, (f'%{sender_name.lower()}%', f'%{sender_name.split()[0].lower()}%'))
        
        client_matches = cur.fetchall()
        
        # Check against employees
        cur.execute("""
            SELECT employee_id, full_name, first_name, last_name
            FROM employees
            WHERE LOWER(full_name) LIKE %s
               OR LOWER(first_name) LIKE %s
               OR LOWER(last_name) LIKE %s
            LIMIT 5
        """, (f'%{sender_name.lower()}%', f'%{sender_name.split()[0].lower()}%', 
              f'%{sender_name.split()[-1].lower()}%'))
        
        employee_matches = cur.fetchall()
        
        if client_matches:
            potential_client_matches.append((row, sender_name, client_matches))
        elif employee_matches:
            potential_employee_matches.append((row, sender_name, employee_matches))
        else:
            unknown.append((row, sender_name))
    
    # Report personal entries
    print("=" * 120)
    print(f"PERSONAL ENTRIES (Barb Peacock) - EXCLUDE: {len(personal_entries)}")
    print("=" * 120)
    total_personal = 0
    for (pid, pdate, amount, pkey, notes), sender in personal_entries:
        print(f"Payment {pid}: ${amount:.2f} on {pdate} - {sender}")
        total_personal += amount
    print(f"\nTotal personal amount: ${total_personal:.2f}")
    print()
    
    # Report potential client matches
    print("=" * 120)
    print(f"POTENTIAL CLIENT MATCHES: {len(potential_client_matches)}")
    print("=" * 120)
    
    for (pid, pdate, amount, pkey, notes), sender, clients in potential_client_matches:
        print(f"\nPayment {pid}: ${amount:.2f} on {pdate}")
        print(f"  Sender: {sender}")
        print(f"  Matched clients:")
        
        for client_id, client_name, account_number in clients:
            # Find charters for this client around the payment date
            cur.execute("""
                SELECT charter_id, reserve_number, charter_date, balance, total_amount_due
                FROM charters
                WHERE client_id = %s
                  AND charter_date BETWEEN %s::date - INTERVAL '30 days' 
                                       AND %s::date + INTERVAL '30 days'
                ORDER BY ABS(EXTRACT(EPOCH FROM (charter_date::timestamp - %s::timestamp)))
                LIMIT 3
            """, (client_id, pdate, pdate, pdate))
            
            charter_matches = cur.fetchall()
            
            print(f"    Client {client_id}: {client_name} (Account {account_number if account_number else 'NULL'})")
            
            if charter_matches:
                print(f"      Recent charters:")
                for cid, reserve, cdate, balance, total_due in charter_matches:
                    amount_match = ""
                    if balance and abs(float(balance) - float(amount)) < 1.0:
                        amount_match = " [OK] AMOUNT MATCH!"
                    elif total_due and abs(float(total_due) - float(amount)) < 1.0:
                        amount_match = " [OK] AMOUNT MATCH!"
                    
                    print(f"        Charter {cid} (Reserve {reserve}): {cdate}, "
                          f"Balance ${balance if balance else 0:.2f}, "
                          f"Total Due ${total_due if total_due else 0:.2f}{amount_match}")
            else:
                print(f"      No recent charters within 30 days")
    
    # Report potential employee matches
    if potential_employee_matches:
        print("\n" + "=" * 120)
        print(f"POTENTIAL EMPLOYEE MATCHES: {len(potential_employee_matches)}")
        print("=" * 120)
        
        for (pid, pdate, amount, pkey, notes), sender, employees in potential_employee_matches:
            print(f"\nPayment {pid}: ${amount:.2f} on {pdate}")
            print(f"  Sender: {sender}")
            print(f"  Matched employees:")
            for emp_id, full_name, first_name, last_name in employees:
                print(f"    Employee {emp_id}: {full_name}")
    
    # Report unknowns
    if unknown:
        print("\n" + "=" * 120)
        print(f"UNKNOWN SENDERS (no client/employee match): {len(unknown)}")
        print("=" * 120)
        
        for item in unknown[:20]:
            if isinstance(item[1], str) and 'Could not extract' in item[1]:
                pid, pdate, amount, pkey, notes = item[0]
                print(f"Payment {pid}: ${amount:.2f} on {pdate} - {item[1]}")
            else:
                (pid, pdate, amount, pkey, notes), sender = item
                print(f"Payment {pid}: ${amount:.2f} on {pdate} - Sender: {sender}")
    
    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print(f"Total Interac payments:        {len(interac_payments)}")
    print(f"  Personal (Barb Peacock):     {len(personal_entries)} (${sum(r[0][2] for r in personal_entries):.2f})")
    print(f"  Potential client matches:    {len(potential_client_matches)}")
    print(f"  Potential employee matches:  {len(potential_employee_matches)}")
    print(f"  Unknown senders:             {len(unknown)}")
    print()
    print("Next steps:")
    print("  1. Review client matches with charter date/amount alignment")
    print("  2. Mark Barb Peacock payments as personal/excluded")
    print("  3. Investigate employee matches (reimbursements? advances?)")
    print("  4. Research unknown senders")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_interac_payments()
