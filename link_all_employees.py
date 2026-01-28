#!/usr/bin/env python3
"""
COMPLETE EMPLOYEE PAYMENT LINKING
- Improve name extraction (catch all variations)
- Link banking transactions to employee payment accounts
- Exclude NSF pairs
- Target: Link all 600+ employee e-transfers
"""

import os
import psycopg2
import sys
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

DRY_RUN = "--dry-run" in sys.argv  # Use command line arg

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def extract_employee_name(desc):
    """Extract employee name from banking description - improved version."""
    if not desc:
        return None
    
    desc_upper = desc.upper()
    
    # Employee name patterns - map to DATABASE names (FIRSTNAME LASTNAME)
    # ORDER MATTERS: longer/more specific patterns first
    patterns = {
        'JEANNIE SHILLINGTON': ['JEANNIE SHILLINGTON', 'JEANNIE SHILLING', 'JEANNIE S'],
        'BRITTANY PEACOCK': ['BRITTANY PEACOCK', 'BRITTANY OSGU', 'BRITTANY O'],
        'MATTHEW RICHARD': ['MATTHEW RICHARD', 'MATTHEW MORRIS', 'MATTHEW M'],
        'MICHAEL RICHARD': ['MICHAEL RICHARD', 'MICHAEL R'],
        'PAUL RICHARD': ['PAUL RICHARD', 'PAUL R'],
        'DAVID RICHARD': ['DAVID RICHARD', 'DAVID R', 'DAVID W RICHARD'],
        'BARBARA PEACOCK': ['BARB PEACOCK', 'BARB P', 'BARBARA'],
    }
    
    for emp_name, keywords in patterns.items():
        for keyword in keywords:
            if keyword.upper() in desc_upper:
                return emp_name
    
    return None

def link_all_employees():
    """Link all employee payments - improved version."""
    conn = get_connection()
    cur = conn.cursor()
    
    mode = "DRY RUN" if DRY_RUN else "PRODUCTION"
    print("\n" + "=" * 100)
    print(f"COMPLETE EMPLOYEE PAYMENT LINKING - {mode}")
    print("=" * 100)
    
    # 1. Get all employees
    print("\n1️⃣ LOADING EMPLOYEES:")
    print("-" * 100)
    
    cur.execute("""
        SELECT employee_id, first_name, last_name
        FROM employees
        WHERE first_name IS NOT NULL AND last_name IS NOT NULL
        ORDER BY employee_id
    """)
    
    employees = {}
    for emp_id, fname, lname in cur.fetchall():
        full_name = f"{fname.upper()} {lname.upper()}".strip()
        employees[full_name] = emp_id
    
    print(f"   Loaded {len(employees)} employees")
    
    # 2. Get unmatched banking transactions
    print("\n2️⃣ SCANNING UNMATCHED BANKING TRANSACTIONS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount,
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        ORDER BY transaction_date DESC
    """)
    
    all_trans = cur.fetchall()
    print(f"   Found {len(all_trans)} total unmatched transactions")
    
    # Extract employee transactions
    employee_trans = []
    for trans_id, date, credit, debit, desc, rec_id in all_trans:
        emp_name = extract_employee_name(desc)
        if emp_name:
            amount = credit if credit else debit
            employee_trans.append({
                'trans_id': trans_id,
                'date': date,
                'amount': amount,
                'desc': desc,
                'emp_name': emp_name,
                'emp_id': employees.get(emp_name, None)
            })
    
    print(f"   ✅ Extracted {len(employee_trans)} employee transactions")
    
    # 3. Identify NSF pairs
    print("\n3️⃣ IDENTIFYING NSF PAIRS (Bounced E-Transfers):")
    print("-" * 100)
    
    nsf_pairs = set()
    for i, t1 in enumerate(employee_trans):
        for t2 in employee_trans[i+1:]:
            if (abs(t1['amount'] - t2['amount']) < 0.01 and
                abs((t1['date'] - t2['date']).days) <= 3 and
                t1['emp_name'] == t2['emp_name']):
                nsf_pairs.add(t1['trans_id'])
                nsf_pairs.add(t2['trans_id'])
    
    print(f"   Found {len(nsf_pairs)} NSF transactions (excluded)")
    
    # 4. Filter valid transactions
    valid_trans = [t for t in employee_trans if t['trans_id'] not in nsf_pairs]
    
    print(f"\n4️⃣ SUMMARY - EMPLOYEE PAYMENTS TO LINK:")
    print("-" * 100)
    
    # Group by employee
    by_employee = {}
    for t in valid_trans:
        emp_name = t['emp_name']
        if emp_name not in by_employee:
            by_employee[emp_name] = []
        by_employee[emp_name].append(t)
    
    total_amount = sum(t['amount'] for t in valid_trans)
    
    for emp_name in sorted(by_employee.keys()):
        trans_list = by_employee[emp_name]
        amount = sum(t['amount'] for t in trans_list)
        emp_id = trans_list[0]['emp_id']
        if emp_id:
            print(f"   {emp_name:30s} (ID: {emp_id:6d}) | {len(trans_list):4d} trans | ${amount:12.2f}")
        else:
            print(f"   {emp_name:30s} (ID: {'?':>6s}) | {len(trans_list):4d} trans | ${amount:12.2f}")
    
    print(f"   {'TOTAL':30s}                  | {len(valid_trans):4d} trans | ${total_amount:12.2f}")
    
    # 5. Create payment records with employee account linking
    if not DRY_RUN:
        print(f"\n5️⃣ LINKING BANKING TRANSACTIONS TO EMPLOYEE ACCOUNTS:")
        print("-" * 100)
        
        linked_count = 0
        failed_count = 0
        skipped_count = 0
        
        for emp_name in sorted(by_employee.keys()):
            trans_list = by_employee[emp_name]
            emp_id = trans_list[0]['emp_id']
            
            if not emp_id:
                print(f"   ⚠️ SKIP {emp_name}: Not in employees table")
                skipped_count += len(trans_list)
                continue
            
            for trans in trans_list:
                try:
                    # Check if employee already has a payment record from this transaction
                    cur.execute("""
                        SELECT payment_id FROM payments
                        WHERE reconciled_payment_id IS NULL
                        AND payment_method IN ('bank_transfer', 'e_transfer')
                        AND amount = %s
                        AND DATE(payment_date) = %s
                        LIMIT 1
                    """, (trans['amount'], trans['date']))
                    
                    existing_payment = cur.fetchone()
                    
                    if existing_payment:
                        payment_id = existing_payment[0]
                    else:
                        # Create new payment record for employee
                        cur.execute("""
                            INSERT INTO payments
                            (reserve_number, amount, payment_date, payment_method, status, notes, created_at, updated_at)
                            VALUES ('EMP_' || %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            RETURNING payment_id
                        """, (
                            str(emp_id),
                            trans['amount'],
                            trans['date'],
                            'bank_transfer',
                            'completed',
                            f'Employee payment - banking trans {trans["trans_id"]}'
                        ))
                        
                        result = cur.fetchone()
                        if result:
                            payment_id = result[0]
                        else:
                            failed_count += 1
                            continue
                    
                    # Link banking transaction
                    cur.execute("""
                        UPDATE banking_transactions
                        SET reconciled_payment_id = %s, updated_at = NOW()
                        WHERE transaction_id = %s
                    """, (payment_id, trans['trans_id']))
                    
                    linked_count += 1
                
                except Exception as e:
                    print(f"   ⚠️ Error processing {emp_name} trans {trans['trans_id']}: {str(e)[:50]}")
                    failed_count += 1
        
        conn.commit()
        
        print(f"   ✅ Linked {linked_count} banking transactions")
        if failed_count > 0:
            print(f"   ⚠️ Failed: {failed_count} transactions")
        if skipped_count > 0:
            print(f"   ⏭️ Skipped: {skipped_count} transactions (not in employee table)")
    
    else:
        print(f"\n5️⃣ DRY RUN - No changes made")
        print(f"   Would link {len(valid_trans)} banking transactions")
    
    # 6. Verification
    print(f"\n6️⃣ VERIFICATION:")
    print("-" * 100)
    
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
    """)
    
    remaining = cur.fetchone()[0]
    print(f"   Total unmatched e-transfers remaining: {remaining}")
    if not DRY_RUN:
        print(f"   Expected after linking: {remaining - len(valid_trans)}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print(f"✅ EMPLOYEE LINKING {'PREVIEW' if DRY_RUN else 'COMPLETE'}")
    print("=" * 100)

if __name__ == "__main__":
    try:
        link_all_employees()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
