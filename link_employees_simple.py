#!/usr/bin/env python3
"""
COMPLETE EMPLOYEE PAYMENT LINKING - ULTRA-SIMPLE
- Just link banking transactions to existing payments or create minimal records
"""

import os
import psycopg2
import sys

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

DRY_RUN = "--dry-run" in sys.argv

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def extract_employee_name(desc):
    """Extract employee name from banking description."""
    if not desc:
        return None
    
    desc_upper = desc.upper()
    
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

def main():
    """Link employee payments - MINIMAL APPROACH."""
    conn = get_connection()
    cur = conn.cursor()
    
    mode = "DRY RUN" if DRY_RUN else "PRODUCTION"
    print("\n" + "=" * 100)
    print(f"COMPLETE EMPLOYEE PAYMENT LINKING - ULTRA-SIMPLE - {mode}")
    print("=" * 100)
    
    # Get employees
    print("\n1️⃣ LOADING EMPLOYEES:")
    cur.execute("SELECT employee_id, first_name, last_name FROM employees WHERE first_name IS NOT NULL")
    employees = {f"{f.upper()} {l.upper()}": emp_id for emp_id, f, l in cur.fetchall()}
    print(f"   Loaded {len(employees)} employees")
    
    # Get unmatched banking
    print("\n2️⃣ LOADING UNMATCHED BANKING:")
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
    """)
    all_trans = cur.fetchall()
    print(f"   Found {len(all_trans)} unmatched")
    
    # Extract employee transactions
    print("\n3️⃣ EXTRACTING EMPLOYEE TRANSACTIONS:")
    employee_trans = []
    for trans_id, date, credit, debit, desc in all_trans:
        emp_name = extract_employee_name(desc)
        if emp_name:
            amount = credit if credit else debit
            employee_trans.append((trans_id, date, amount, emp_name))
    
    print(f"   Extracted {len(employee_trans)} employee transactions")
    
    # Identify NSF pairs
    print("\n4️⃣ IDENTIFYING NSF PAIRS:")
    nsf_trans = set()
    for i in range(len(employee_trans)):
        for j in range(i + 1, len(employee_trans)):
            t1 = employee_trans[i]
            t2 = employee_trans[j]
            if (abs(t1[2] - t2[2]) < 0.01 and 
                abs((t1[1] - t2[1]).days) <= 3 and 
                t1[3] == t2[3]):
                nsf_trans.add(t1[0])
                nsf_trans.add(t2[0])
    
    print(f"   Found {len(nsf_trans)} NSF transactions")
    
    # Filter valid
    valid = [(t_id, date, amt, emp_name) for t_id, date, amt, emp_name in employee_trans if t_id not in nsf_trans]
    
    print(f"\n5️⃣ VALID EMPLOYEE PAYMENTS: {len(valid)} | ${sum(v[2] for v in valid):,.2f}")
    
    # Link them
    if not DRY_RUN:
        print(f"\n6️⃣ LINKING TRANSACTIONS:")
        linked = 0
        failed = 0
        
        for trans_id, date, amount, emp_name in valid:
            try:
                # Create payment record first
                emp_id = employees.get(emp_name, 9999)
                cur.execute("""
                    INSERT INTO payments
                    (reserve_number, amount, payment_date, payment_method, status, notes, created_at, updated_at)
                    VALUES ('EMP_' || %s, %s, %s, 'bank_transfer', 'paid', %s, NOW(), NOW())
                    RETURNING payment_id
                """, (emp_id, amount, date, f'Emp e-transfer: {emp_name}'))
                
                payment_id = cur.fetchone()[0]
                
                # Update banking transaction
                cur.execute("""
                    UPDATE banking_transactions
                    SET reconciled_payment_id = %s, updated_at = NOW()
                    WHERE transaction_id = %s
                """, (payment_id, trans_id))
                
                conn.commit()
                linked += 1
                
                if linked % 100 == 0:
                    print(f"   ... {linked} linked")
                    
            except Exception as e:
                failed += 1
                if failed <= 3:
                    print(f"   ❌ Trans {trans_id}: {str(e)[:60]}")
        
        print(f"   ✅ Linked: {linked} | Failed: {failed}")
    
    else:
        print(f"\n6️⃣ DRY RUN - Would link {len(valid)} transactions")
    
    # Verify
    print(f"\n7️⃣ VERIFICATION:")
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE reconciled_payment_id IS NULL")
    remaining = cur.fetchone()[0]
    print(f"   Remaining unmatched: {remaining}")
    if not DRY_RUN:
        print(f"   Reconciled: {len(all_trans) - remaining}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    main()
