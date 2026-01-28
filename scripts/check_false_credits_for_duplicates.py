#!/usr/bin/env python3
"""Check if any of the 33 reserves with deleted duplicates have false credit ledger entries."""

import psycopg2

affected_reserves = [
    '010029', '010260', '010795', '010912', '011230', '011231', '011253', '011259',
    '012115', '012316', '012406', '012911', '012933', '012938', '012998', '013050',
    '013175', '013368', '014119', '014193', '014215', '014285', '014380', '014411',
    '014433', '014476', '015244', '015271', '015279', '015301', '015542', '016213',
    '019270'
]

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check for credits
cur.execute("""
    SELECT 
        ccl.source_reserve_number,
        cl.client_name,
        ccl.credit_amount,
        ccl.credit_reason,
        c.paid_amount,
        c.total_amount_due,
        c.balance
    FROM charter_credit_ledger ccl
    JOIN clients cl ON cl.client_id = ccl.client_id
    JOIN charters c ON c.reserve_number = ccl.source_reserve_number
    WHERE ccl.source_reserve_number = ANY(%s)
    ORDER BY ccl.credit_amount DESC
""", (affected_reserves,))

credits = cur.fetchall()

if credits:
    print(f"Found {len(credits)} credit ledger entries for reserves that had duplicates deleted:")
    print()
    for reserve, client, amount, reason, paid, due, balance in credits:
        print(f"Reserve {reserve} ({client}):")
        print(f"  Credit: ${amount:.2f} ({reason})")
        print(f"  Charter: Due=${due:.2f}, Paid=${paid:.2f}, Balance=${balance:.2f}")
        if paid <= due:
            print(f"  → FALSE CREDIT - charter is now balanced/underpaid")
        else:
            print(f"  → Excess remains: ${paid - due:.2f}")
        print()
    
    # Count false credits
    false_count = sum(1 for _, _, _, _, paid, due, _ in credits if paid <= due)
    false_amount = sum(amount for _, _, amount, _, paid, due, _ in credits if paid <= due)
    print(f"False credits to delete: {false_count} totaling ${false_amount:.2f}")
else:
    print("No credit ledger entries found for affected reserves - all clean!")

cur.close()
conn.close()
