#!/usr/bin/env python3
"""
Link non-customer banking transactions (employees, vendors, insurance) to existing infrastructure.

Key Discoveries:
1. Payments table uses: reserve_number, account_number (NOT client_id)
2. Charters table has: client_id (links to customers)
3. Non-customer payments need different handling:
   - Employee payments → Link to employee_pay_master by name
   - Heffner payments → Link to client_id=3980
   - Insurance payments → Link to vendor_account_ledger
   - Other vendors → Link to payables or vendor_account_ledger

CRITICAL: These are NOT charter payments - no reserve_number linking required
"""

import os
import psycopg2
import sys

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def analyze():
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("LINK NON-CUSTOMER BANKING TRANSACTIONS")
    print("="*100)
    
    # 1. Employee name patterns in banking
    print("\n1️⃣ EMPLOYEE PAYMENTS IN BANKING (Unmatched):")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount,
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE '%PAUL RICHARD%'
            OR description ILIKE '%SHERRI RYCKMAN%'
            OR description ILIKE '%SHERRI%'
            OR description ILIKE '%BARB PEACOCK%'
            OR description ILIKE '%DAVID RICHARD%'
            OR description ILIKE '%MATTHEW%'
            OR description ILIKE '%JERRY%'
            OR description ILIKE '%JEANNIE%'
            OR description ILIKE '%REMPEL%'
            OR description ILIKE '%JEMPSON%'
        )
        ORDER BY transaction_date DESC
        LIMIT 20
    """)
    
    employee_trans = cur.fetchall()
    employee_count = len(employee_trans)
    employee_total = sum([t[2] or t[3] for t in employee_trans])
    
    print(f"   Found {employee_count} employee transactions | Total: ${employee_total:.2f}")
    for trans in employee_trans[:10]:
        trans_id, date, credit, debit, desc, rec_id = trans
        amount = credit if credit else debit
        print(f"   Trans {trans_id:8d} | {date} | ${amount:10.2f} | {desc[:60]}")
    
    # 2. Check employee_pay_master for matching employees
    print(f"\n2️⃣ EXISTING EMPLOYEE PAY RECORDS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT employee_id, employee_name, COUNT(*) as entries, SUM(COALESCE(pay_amount, 0)) as total
        FROM employee_pay_master
        GROUP BY employee_id, employee_name
        ORDER BY total DESC
        LIMIT 15
    """)
    
    employees = cur.fetchall()
    print(f"   Found {len(employees)} employees in employee_pay_master")
    for emp_id, name, entries, total in employees:
        print(f"   Emp {emp_id:6d} | {name:30s} | {entries:4d} entries | ${total:12.2f}")
    
    # 3. Heffner payments
    print(f"\n3️⃣ HEFFNER PAYMENTS IN BANKING:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount,
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND description ILIKE '%HEFFNER%'
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    
    heffner_trans = cur.fetchall()
    heffner_total = sum([t[2] or t[3] for t in heffner_trans])
    print(f"   Found {len(heffner_trans)} Heffner transactions | Total: ${heffner_total:.2f}")
    for trans in heffner_trans[:5]:
        trans_id, date, credit, debit, desc, rec_id = trans
        amount = credit if credit else debit
        print(f"   Trans {trans_id:8d} | {date} | ${amount:10.2f} | {desc[:60]}")
    
    # 4. Insurance payments
    print(f"\n4️⃣ INSURANCE PAYMENTS IN BANKING:")
    print("-" * 100)
    
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount,
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE '%INSURANCE%'
            OR description ILIKE '%SWIFT%'
            OR description ILIKE '%CIBC%'
        )
        ORDER BY transaction_date DESC
        LIMIT 10
    """)
    
    insurance_trans = cur.fetchall()
    insurance_total = sum([t[2] or t[3] for t in insurance_trans])
    print(f"   Found {len(insurance_trans)} insurance transactions | Total: ${insurance_total:.2f}")
    for trans in insurance_trans[:5]:
        trans_id, date, credit, debit, desc, rec_id = trans
        amount = credit if credit else debit
        print(f"   Trans {trans_id:8d} | {date} | ${amount:10.2f} | {desc[:60]}")
    
    # 5. Check for payments already linked to special clients
    print(f"\n5️⃣ PAYMENTS LINKED TO SPECIAL CLIENTS:")
    print("-" * 100)
    
    special_client_ids = [
        5133,  # Alberta Insurance
        3980,  # Heffner
        3252,  # Express Employment
    ]
    
    placeholders = ','.join(['%s'] * len(special_client_ids))
    cur.execute(f"""
        SELECT c.client_id, c.client_name, COUNT(*)  as payment_count, SUM(COALESCE(p.amount, 0)) as total
        FROM payments p
        JOIN charters ch ON ch.account_number = p.account_number OR ch.client_id = p.account_number::int
        JOIN clients c ON c.client_id = ch.client_id
        WHERE ch.client_id IN ({placeholders})
        GROUP BY c.client_id, c.client_name
        ORDER BY total DESC
    """, special_client_ids)
    
    special_payments = cur.fetchall()
    print(f"   Found {len(special_payments)} payment patterns for special clients")
    for cid, cname, count, total in special_payments[:10]:
        print(f"   Client {cid:6d} | {cname:40s} | {count:6d} payments | ${total:12.2f}")
    
    # 6. Summary
    print(f"\n6️⃣ SUMMARY - NON-CUSTOMER UNMATCHED TRANSACTIONS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN description ILIKE ANY(ARRAY['%PAUL%', '%SHERRI%', '%BARB%', '%DAVID%', '%MATTHEW%', '%JERRY%', '%JEANNIE%', '%REMPEL%', '%JEMPSON%'])
                    THEN 'Employee'
                WHEN description ILIKE '%HEFFNER%' THEN 'Heffner'
                WHEN description ILIKE '%INSURANCE%' THEN 'Insurance'
                WHEN description ILIKE '%SWIFT%' THEN 'Swift'
                ELSE 'Other Vendor'
            END AS category,
            COUNT(*) as count,
            SUM(COALESCE(credit_amount, debit_amount, 0)) as total
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE '%PAUL%' OR description ILIKE '%SHERRI%' OR description ILIKE '%BARB%' OR description ILIKE '%DAVID%'
            OR description ILIKE '%MATTHEW%' OR description ILIKE '%JERRY%' OR description ILIKE '%JEANNIE%'
            OR description ILIKE '%REMPEL%' OR description ILIKE '%JEMPSON%'
            OR description ILIKE '%HEFFNER%' OR description ILIKE '%INSURANCE%'  OR description ILIKE '%SWIFT%'
        )
        GROUP BY category
        ORDER BY total DESC
    """)
    
    categories = cur.fetchall()
    total_all = sum([c[2] for c in categories])
    
    for cat, count, total in categories:
        pct = 100 * total / total_all if total_all > 0 else 0
        print(f"   {cat:20s} | {count:6d} trans | ${total:12.2f} ({pct:5.1f}%)")
    
    print(f"   {'TOTAL':20s} | {'':6s} | ${total_all:12.2f}")
    
    # 7. Strategy output
    print(f"\n7️⃣ LINKING STRATEGY:")
    print("-" * 100)
    print("""
    STEP 1: EMPLOYEES
    - Match: banking.description contains employee name
    - Action: Find employee in employee_pay_master, create/link payment
    - Target: Connect banking_transaction to employee_pay_calc/employee_pay_master
    
    STEP 2: HEFFNER
    - Match: banking.description contains "HEFFNER"
    - Action: Link to special client (client_id=3980)
    - Target: Create payment record OR link to existing vendor_account_ledger
    
    STEP 3: INSURANCE & VENDORS
    - Match: banking.description contains insurance/vendor keywords
    - Action: Link to vendor_account_ledger or payables
    - Target: Group by vendor, create summary payment records
    
    KEY: All non-customer payments should have NULL reserve_number
         (Not linked to charters, but to vendor/employee infrastructure)
    """)
    
    cur.close()
    conn.close()
    
    print("\n" + "="*100)

if __name__ == "__main__":
    try:
        analyze()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
