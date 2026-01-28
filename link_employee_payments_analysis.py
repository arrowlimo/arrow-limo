#!/usr/bin/env python3
"""
Link employee banking transactions (e-transfers) to employee payment records.

Strategy:
1. Match banking.description names (PAUL RICHARD, SHERRI, etc.) to employees.first_name + employees.last_name
2. For matched employees, find or create payment records
3. Link banking_transactions.reconciled_payment_id to payment records
4. Skip NSF pairs (e-transfer + immediate reversal = bounced)

Key data sources:
- employees table: employee_id, first_name, last_name
- banking_transactions: unreconciled e-transfers with employee names
- payments table: may already have these linked (check reserve_number and notes)
- employee_pay_master: final employee pay records
"""

import os
import psycopg2
import sys
import re
from difflib import SequenceMatcher

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DRY_RUN = True  # Set to False to actually update

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def similar(a, b):
    """Calculate string similarity 0-1"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_employee_name_from_description(desc):
    """Extract employee name from banking description."""
    if not desc:
        return None
    
    # Common patterns
    patterns = {
        'PAUL RICHARD': ['PAUL RICHARD', 'PAUL R'],
        'SHERRI RYCKMAN': ['SHERRI RYCKMAN', 'SHERRI'],
        'BARB PEACOCK': ['BARB PEACOCK', 'BARB P'],
        'DAVID RICHARD': ['DAVID RICHARD', 'DAVID R'],
        'MATTHEW': ['MATTHEW'],
        'JERRY': ['JERRY'],
        'JEANNIE': ['JEANNIE'],
    }
    
    for emp_name, keywords in patterns.items():
        for keyword in keywords:
            if keyword.upper() in desc.upper():
                return emp_name
    
    return None

def link_employee_payments():
    """Link employee e-transfers to payment records."""
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("LINK EMPLOYEE E-TRANSFERS TO PAYMENT RECORDS (DRY_RUN={})".format(DRY_RUN))
    print("="*100)
    
    # 1. Get employees
    print("\n1️⃣ LOADING EMPLOYEES:")
    print("-" * 100)
    
    cur.execute("""
        SELECT employee_id, first_name, last_name, email
        FROM employees
        WHERE first_name IS NOT NULL
        AND last_name IS NOT NULL
        ORDER BY employee_id
    """)
    
    employees = {}  # name_key -> employee_id
    employees_by_id = {}  # employee_id -> name
    
    for emp_id, fname, lname, email in cur.fetchall():
        full_name = f"{fname.upper()} {lname.upper()}".strip()
        employees[full_name] = emp_id
        employees_by_id[emp_id] = full_name
    
    print(f"   Loaded {len(employees)} employees")
    for name, emp_id in list(employees.items())[:10]:
        print(f"   - {name} (ID: {emp_id})")
    
    # 2. Get unmatched employee banking transactions
    print("\n2️⃣ FINDING UNMATCHED EMPLOYEE BANKING TRANSACTIONS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount,
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE '%PAUL%RICHARD%'
            OR description ILIKE '%SHERRI%'
            OR description ILIKE '%BARB%PEACOCK%'
            OR description ILIKE '%DAVID%RICHARD%'
            OR description ILIKE '%MATTHEW%'
            OR description ILIKE '%JERRY%'
            OR description ILIKE '%JEANNIE%'
        )
        ORDER BY transaction_date DESC
    """)
    
    banking_trans = cur.fetchall()
    print(f"   Found {len(banking_trans)} unmatched employee e-transfers")
    
    employee_matches = {}  # (emp_name, emp_id) -> list of transactions
    unmatched_trans = []
    
    for trans_id, date, credit, debit, desc, rec_id in banking_trans:
        emp_name = extract_employee_name_from_description(desc)
        amount = credit if credit else debit
        
        if emp_name and emp_name in employees:
            emp_id = employees[emp_name]
            key = (emp_name, emp_id)
            if key not in employee_matches:
                employee_matches[key] = []
            employee_matches[key].append({
                'trans_id': trans_id,
                'date': date,
                'amount': amount,
                'desc': desc
            })
        else:
            unmatched_trans.append((trans_id, date, amount, desc))
    
    print(f"   ✅ Matched: {len(employee_matches)} employee names")
    for (name, emp_id), trans_list in list(employee_matches.items())[:10]:
        total = sum([t['amount'] for t in trans_list])
        print(f"   - {name} (ID: {emp_id:6d}) | {len(trans_list):3d} trans | ${total:10.2f}")
    
    print(f"\n   ⚠️  Unmatched: {len(unmatched_trans)} transactions (couldn't extract name)")
    for trans_id, date, amount, desc in unmatched_trans[:5]:
        print(f"   - Trans {trans_id} | {amount:8.2f} | {desc[:50]}")
    
    # 3. Check for existing payment records for these employees
    print("\n3️⃣ CHECKING EXISTING PAYMENT RECORDS FOR EMPLOYEES:")
    print("-" * 100)
    
    matching_emp_ids = [emp_id for _, emp_id in employee_matches.keys()]
    if matching_emp_ids:
        placeholders = ','.join(['%s'] * len(matching_emp_ids))
        
        # Note: Payments don't have employee_id directly, so check by notes or pattern
        cur.execute(f"""
            SELECT payment_id, reserve_number, amount, payment_date, 
                   payment_method, status, notes
            FROM payments
            WHERE (
                reserve_number LIKE 'EMP%'
                OR reserve_number LIKE 'PAY%'
                OR reserve_number LIKE 'PAYROLL%'
                OR notes LIKE '%employee%'
                OR notes LIKE '%PAUL%'
                OR notes LIKE '%SHERRI%'
            )
            ORDER BY payment_date DESC
            LIMIT 20
        """)
        
        existing_payments = cur.fetchall()
        print(f"   Found {len(existing_payments)} existing employee-linked payments")
        for p in existing_payments[:10]:
            p_id, reserve, amount, date, method, status, notes = p
            print(f"   Payment {p_id:6d} | {reserve or 'NULL':10s} | ${amount:10.2f} | {date}")
    
    # 4. NSF Pair Detection
    print("\n4️⃣ DETECTING NSF PAIRS (Bounced E-Transfers):")
    print("-" * 100)
    
    nsf_pairs = set()
    for (name, emp_id), trans_list in employee_matches.items():
        # Look for same-amount credit + debit within 3 days = NSF
        for t1 in trans_list:
            for t2 in trans_list:
                if t1 != t2 and abs(t1['amount'] - t2['amount']) < 0.01:
                    date_diff = abs((t1['date'] - t2['date']).days)
                    if date_diff <= 3:
                        nsf_pairs.add(t1['trans_id'])
                        nsf_pairs.add(t2['trans_id'])
    
    print(f"   Found {len(nsf_pairs)} transactions in NSF pairs")
    print(f"   (These are excluded from linking)")
    
    # 5. Link strategy summary
    print("\n5️⃣ LINKING SUMMARY:")
    print("-" * 100)
    
    valid_transactions = []
    for (name, emp_id), trans_list in employee_matches.items():
        for trans in trans_list:
            if trans['trans_id'] not in nsf_pairs:
                valid_transactions.append((trans, name, emp_id))
    
    total_valid = len(valid_transactions)
    total_valid_amount = sum([t[0]['amount'] for t in valid_transactions])
    
    print(f"   ✅ Valid transactions (non-NSF): {total_valid} | ${total_valid_amount:.2f}")
    print(f"   ⚠️  NSF pairs: {len(nsf_pairs)} | (excluded)")
    print(f"   ❌ Unmatched: {len(unmatched_trans)} | (couldn't extract name)")
    
    if not DRY_RUN:
        print(f"\n6️⃣ LINKING ACTIONS (EXECUTING):")
        print("-" * 100)
        
        # We would create payment records here
        # For now, just show what would be done
        linked_count = 0
        linked_amount = 0
        
        for (trans, name, emp_id) in valid_transactions[:10]:  # Limit for safety
            # This is where we would create a payment record
            # and link banking_transactions.reconciled_payment_id
            linked_count += 1
            linked_amount += trans['amount']
        
        print(f"   Would link {linked_count} transactions | ${linked_amount:.2f}")
        print("   (Implementation: create payment record with notes, update banking_transactions)")
    
    # 6. Recommendations
    print(f"\n7️⃣ RECOMMENDATIONS:")
    print("-" * 100)
    print(f"""
    NEXT STEPS:
    1. If {total_valid} employee payments are acceptable:
       → Create script: create_employee_payments_from_banking.py
       → Create payment records with employee reserve numbers (EMP_PAUL_RICHARD, etc.)
       → Update banking_transactions.reconciled_payment_id for each
    
    2. Link to employee_pay_master:
       → Use employee_id to find related pay periods
       → Update notes in payments table to reference pay period
    
    3. Review NSF pairs ({len(nsf_pairs)} transactions):
       → These are legitimate failed payments (bank rejected)
       → Should NOT create payment records
       → Consider marking as "BOUNCED" or "NSF" in banking
    
    4. Investigate unmatched ({len(unmatched_trans)} transactions):
       → Check if name extraction needs improvement
       → May be vendor/insurance payments, not employees
    """)
    
    cur.close()
    conn.close()
    
    print("\n" + "="*100)

if __name__ == "__main__":
    try:
        link_employee_payments()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
