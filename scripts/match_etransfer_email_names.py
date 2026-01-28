#!/usr/bin/env python3
"""
Match e-transfer names from email subjects to drivers and verify against banking dates.

Email format examples:
- "Your $400.00 transfer to RICHARD GURSKY has been successfully deposited"
- "JACQUELINE LINTON sent you $400.00"
- "Your money transfer to JOHN D MCLEAN was deposited"
"""

import psycopg2
import os
import re
from datetime import datetime, timedelta

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Email subjects with dates and names
emails = [
    ("11/14/2025", "RICHARD GURSKY", 400, "OUT"),
    ("09/25/2025", "MICHAEL EDWIN WOODROW", 400, "OUT"),
    ("09/04/2025", "MICHAEL RICHARD", 950, "OUT"),
    ("08/29/2025", "Tabatha Foulston", 400, "OUT"),
    ("08/18/2025", "ALANNA MANZ", 400, "OUT"),
    ("06/19/2025", "SEAN THOMAS", 400, "OUT"),
    ("06/06/2025", "JOHN D MCLEAN", 400, "OUT"),
    ("06/06/2025", "JACQUELINE LINTON", 400, "IN"),
    ("05/21/2025", "RICHARD GURSKY", 400, "OUT"),
    ("04/17/2025", "JOHN D MCLEAN", 400, "OUT"),
    ("03/26/2025", "RICHARD GURSKY", 400, "OUT"),
    ("02/14/2025", "MICHAEL RICHARD", 400, "OUT"),
    ("02/11/2025", "MICHAEL EDWIN WOODROW", 400, "OUT"),
    ("01/22/2025", "RICHARD GURSKY", 400, "OUT"),
    ("12/23/2024", "Tabatha Foulston", 400, "OUT"),
    ("12/04/2024", "Mundy Dianne", 400, "OUT"),
    ("11/20/2024", "RICHARD GURSKY", 400, "OUT"),
    ("11/08/2024", "JOHN D MCLEAN", 400, "OUT"),
    ("10/24/2024", "MICHAEL RICHARD", 400, "OUT"),
    ("10/01/2024", "JOHN D MCLEAN", 400, "OUT"),
    ("09/01/2024", "BRITTANY A PEACOCK", 400, "OUT"),
    ("08/30/2024", "RICHARD GURSKY", 400, "OUT"),
    ("08/23/2024", "Jensyn May", 400, "OUT"),
    ("07/05/2024", "SERENA OLSEN", 400, "OUT"),
    ("06/12/2024", "SERENA OLSEN", 400, "OUT"),
    ("06/01/2024", "Tabatha Foulston", 400, "OUT"),
    ("05/14/2024", "Tabatha Foulston", 400, "OUT"),
    ("04/24/2024", "ON THE MARK PRODUCTIONS INC", 0, "IN"),
    ("03/22/2024", "SERENA OLSEN", 400, "OUT"),
    ("03/21/2024", "SEAN THOMAS", 400, "OUT"),
    ("03/04/2024", "MICHAEL RICHARD", 400, "OUT"),
]

print("\n" + "="*80)
print("E-TRANSFER NAME MATCHING")
print("="*80)

# Get all drivers
cur.execute("""
    SELECT employee_id, full_name, first_name, last_name
    FROM employees
    WHERE status = 'active' OR is_chauffeur = TRUE
    ORDER BY full_name
""")
drivers = cur.fetchall()

print(f"\nDrivers in database: {len(drivers)}")

# Get all clients
cur.execute("""
    SELECT client_id, client_name
    FROM clients
    ORDER BY client_name
""")
clients = cur.fetchall()

print(f"Clients in database: {len(clients)}")

def normalize_name(name):
    """Normalize name for comparison."""
    return ' '.join(name.upper().split())

def find_driver_match(name, drivers):
    """Find driver by name."""
    norm_name = normalize_name(name)
    
    for emp_id, full, first, last in drivers:
        if full and normalize_name(full) == norm_name:
            return emp_id, full, "exact"
        if first and last:
            full_constructed = f"{first} {last}"
            if normalize_name(full_constructed) == norm_name:
                return emp_id, full, "first+last"
        if last and normalize_name(last) in norm_name:
            return emp_id, full, "last_name"
    
    return None, None, None

def find_client_match(name, clients):
    """Find client by name."""
    norm_name = normalize_name(name)
    
    for client_id, client_name in clients:
        if client_name and normalize_name(client_name) == norm_name:
            return client_id, client_name, "exact"
        if client_name and norm_name in normalize_name(client_name):
            return client_id, client_name, "partial"
    
    return None, None, None

# Analyze e-transfers
print("\n" + "="*80)
print("E-TRANSFER ANALYSIS")
print("="*80)

out_transfers = []
in_transfers = []

for email_date, name, amount, direction in emails:
    # Parse date
    try:
        date = datetime.strptime(email_date, "%m/%d/%Y").date()
    except:
        continue
    
    # Find matches
    driver_id, driver_name, driver_type = find_driver_match(name, drivers)
    client_id, client_name, client_type = find_client_match(name, clients)
    
    # Check banking transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
        AND (
            (description ILIKE %s AND %s = 'OUT' AND debit_amount BETWEEN %s AND %s)
            OR
            (description ILIKE %s AND %s = 'IN' AND credit_amount BETWEEN %s AND %s)
        )
        LIMIT 5
    """, (
        date - timedelta(days=2), date + timedelta(days=2),
        f'%{name}%', direction, amount-10, amount+10,
        f'%{name}%', direction, amount-10, amount+10
    ))
    
    banking_matches = cur.fetchall()
    
    record = {
        'date': date,
        'name': name,
        'amount': amount,
        'direction': direction,
        'driver_match': driver_name if driver_id else None,
        'driver_type': driver_type,
        'client_match': client_name if client_id else None,
        'client_type': client_type,
        'banking_matches': len(banking_matches)
    }
    
    if direction == 'OUT':
        out_transfers.append(record)
    else:
        in_transfers.append(record)

# Print results
print(f"\nOUTGOING E-TRANSFERS (payments to drivers): {len(out_transfers)}")
print(f"{'Date':>12} {'Amount':>8} {'Name':>30} {'Driver Match':>30} {'Banking':>8}")
print("-"*100)

driver_matched = 0
for t in out_transfers:
    driver_str = t['driver_match'] if t['driver_match'] else "NO MATCH"
    banking_str = f"{t['banking_matches']} txn" if t['banking_matches'] > 0 else "NONE"
    print(f"{str(t['date']):>12} ${t['amount']:>6} {t['name'][:30]:>30} {driver_str[:30]:>30} {banking_str:>8}")
    if t['driver_match']:
        driver_matched += 1

print(f"\nDriver match rate: {driver_matched}/{len(out_transfers)} ({driver_matched/len(out_transfers)*100:.1f}%)")

print(f"\n\nINCOMING E-TRANSFERS (payments from clients): {len(in_transfers)}")
print(f"{'Date':>12} {'Amount':>8} {'Name':>30} {'Client Match':>30} {'Banking':>8}")
print("-"*100)

client_matched = 0
for t in in_transfers:
    client_str = t['client_match'] if t['client_match'] else "NO MATCH"
    banking_str = f"{t['banking_matches']} txn" if t['banking_matches'] > 0 else "NONE"
    print(f"{str(t['date']):>12} ${t['amount']:>6} {t['name'][:30]:>30} {client_str[:30]:>30} {banking_str:>8}")
    if t['client_match']:
        client_matched += 1

print(f"\nClient match rate: {client_matched}/{len(in_transfers)} ({client_matched/len(in_transfers)*100:.1f}%)")

print("\n" + "="*80)

cur.close()
conn.close()
