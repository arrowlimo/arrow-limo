#!/usr/bin/env python3
"""
Link all non-customer banking transactions (employees, vendors, insurance, Heffner)
to existing employee/vendor/reconciliation infrastructure.

Strategy:
1. Identify all non-customer transaction names (employees, Heffner, insurance, vendors)
2. Match banking transactions by name to special clients
3. Create payment records linking to vendors/reconciliation (not charter-based)
4. Update banking_transactions.reconciled_payment_id

Key finding: 178 payments already exist with NULL reserve_number linked to special clients
This suggests these should be treated differently - not as charter payments but as
vendor/expense payments.
"""

import os
import psycopg2
import sys
from datetime import datetime

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

def analyze_noncustomer_transactions():
    """Analyze non-customer banking transactions and categorize them."""
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("ANALYZE NON-CUSTOMER BANKING TRANSACTIONS & EXISTING INFRASTRUCTURE")
    print("="*100)
    
    # 1. Special clients (non-customer)
    print("\n1️⃣ SPECIAL CLIENTS (Non-Customer):")
    print("-" * 100)
    
    cur.execute("""
        SELECT client_id, client_name, company_name 
        FROM clients 
        WHERE client_name IN (
            'Heffner Auto Sales & Leasing',
            'Alberta Insurance Council',
            'Swift Insurance & Financial',
            'Express Employment Professiona',
            'Rempel, Ainsley', 'Rempel, Becca', 'Rempel, Becky',
            'Remple, Brent', 'Remple, Johanna',
            'Jempson, Dawn', 'Jempson, Kelton',
            'Payne Stephen', 'Lagrange Payton', 'Louise Weisman',
            'Payzant Mullis, Cherilynn', 'Semple, Shaun'
        )
        ORDER BY client_name
    """)
    
    special_clients = cur.fetchall()
    special_client_ids = [row[0] for row in special_clients]
    
    for client_id, client_name, company_name in special_clients:
        print(f"   {client_id:6d} | {client_name:40s} | {company_name or 'N/A'}")
    
    # 2. Payments already linked to these special clients
    print(f"\n2️⃣ PAYMENTS ALREADY LINKED TO SPECIAL CLIENTS:")
    print("-" * 100)
    
    if special_client_ids:
        placeholders = ','.join(['%s'] * len(special_client_ids))
        cur.execute(f"""
            SELECT p.payment_id, p.reserve_number, p.amount, p.payment_date, 
                   p.payment_method, p.client_id, c.client_name, c.company_name
            FROM payments p
            LEFT JOIN clients c ON c.client_id = p.client_id
            WHERE p.client_id IN ({placeholders})
            ORDER BY c.client_name, p.payment_date DESC
            LIMIT 50
        """, special_client_ids)
        
        existing_payments = cur.fetchall()
        print(f"   Found {len(existing_payments)} payments linked to special clients")
        
        for payment in existing_payments[:10]:  # Show first 10
            payment_id, reserve_num, amount, date, method, cid, client_name, company_name = payment
            print(f"   Payment {payment_id:6d} | {reserve_num or 'NULL':8s} | ${amount:10.2f} | {date} | {client_name[:30]}")
    
    # 3. Banking transactions with non-customer names (employees, vendors)
    print(f"\n3️⃣ BANKING TRANSACTIONS WITH NON-CUSTOMER NAMES (Employee/Vendor/Insurance):")
    print("-" * 100)
    
    employee_names = [
        'PAUL RICHARD', 'SHERRI RYCKMAN', 'BARB PEACOCK', 'DAVID RICHARD',
        'SHERRI', 'MATTHEW', 'JERRY', 'JEANNIE',
        'REMPEL', 'JEMPSON', 'PAYNE', 'LAGRANGE', 'SEMPLE', 'WEISMAN'
    ]
    
    insurance_keywords = ['INSURANCE', 'SWIFT', 'HEFFNER', 'CIBC', 'TD', 'RBC', 'ROYAL BANK']
    vendor_keywords = ['FUEL', 'REPAIR', 'MAINTENANCE', 'TIRE', 'SERVICE', 'OIL', 'GAS']
    
    # Build search pattern
    name_pattern = ' | '.join(employee_names)
    
    cur.execute(f"""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount, 
               description, reconciled_payment_id
        FROM banking_transactions
        WHERE (
            description ILIKE ANY(ARRAY{employee_names})
            OR description ILIKE '%INSURANCE%'
            OR description ILIKE '%HEFFNER%'
            OR description ILIKE '%SWIFT%'
        )
        AND reconciled_payment_id IS NULL
        ORDER BY transaction_date DESC
        LIMIT 20
    """)
    
    unmatched_noncustomer = cur.fetchall()
    print(f"   Found {len(unmatched_noncustomer)} unmatched non-customer banking transactions")
    
    for trans in unmatched_noncustomer[:15]:  # Show first 15
        trans_id, date, credit, debit, desc, rec_id = trans
        amount = credit if credit else debit
        print(f"   Trans {trans_id:8d} | {date} | ${amount:10.2f} | {desc[:50]}")
    
    # 4. Summary of categorization
    print(f"\n4️⃣ CATEGORIZATION SUMMARY:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN description ILIKE ANY(ARRAY['PAUL', 'SHERRI', 'BARB', 'DAVID', 'MATTHEW', 'JERRY', 'JEANNIE', 'REMPEL', 'JEMPSON', 'PAYNE', 'LAGRANGE', 'SEMPLE', 'WEISMAN']) 
                    THEN 'Employee'
                WHEN description ILIKE '%INSURANCE%' THEN 'Insurance'
                WHEN description ILIKE '%HEFFNER%' THEN 'Heffner'
                WHEN description ILIKE '%SWIFT%' THEN 'Swift'
                WHEN description ILIKE ANY(ARRAY['FUEL', 'GAS', 'OIL', 'MAINTENANCE', 'REPAIR', 'TIRE', 'SERVICE'])
                    THEN 'Maintenance'
                ELSE 'Other'
            END AS category,
            COUNT(*) as count,
            SUM(COALESCE(credit_amount, 0) + COALESCE(debit_amount, 0)) as total_amount
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        AND (
            description ILIKE ANY(ARRAY['%PAUL%', '%SHERRI%', '%BARB%', '%DAVID%', '%MATTHEW%', '%JERRY%', '%JEANNIE%', '%REMPEL%', '%JEMPSON%', '%PAYNE%', '%LAGRANGE%', '%SEMPLE%', '%WEISMAN%', '%INSURANCE%', '%HEFFNER%', '%SWIFT%', '%FUEL%', '%GAS%', '%OIL%', '%MAINTENANCE%', '%REPAIR%', '%TIRE%', '%SERVICE%'])
        )
        GROUP BY category
        ORDER BY total_amount DESC
    """)
    
    categories = cur.fetchall()
    for cat, count, total in categories:
        print(f"   {cat:20s} | {count:6d} transactions | ${total:12.2f}")
    
    # 5. Existing vendor structure
    print(f"\n5️⃣ EXISTING VENDOR INFRASTRUCTURE:")
    print("-" * 100)
    
    cur.execute("""
        SELECT vendor_id, vendor_name, COUNT(*) as receipt_count, SUM(COALESCE(amount, 0)) as total
        FROM receipts
        WHERE vendor_name IN ('HEFFNER', 'INSURANCE', 'SWIFT', 'FUEL', 'GAS', 'OIL')
        GROUP BY vendor_id, vendor_name
        ORDER BY total DESC
    """)
    
    vendors = cur.fetchall()
    print(f"   Found {len(vendors)} vendors in receipts table")
    for vendor_id, name, count, total in vendors[:10]:
        print(f"   Vendor {vendor_id:6d} | {name:40s} | {count:6d} receipts | ${total:12.2f}")
    
    # 6. Employee pay structure
    print(f"\n6️⃣ EXISTING EMPLOYEE PAY STRUCTURE:")
    print("-" * 100)
    
    cur.execute("""
        SELECT employee_id, employee_name, COUNT(*) as pay_entries, SUM(COALESCE(pay_amount, 0)) as total_paid
        FROM employee_pay_master
        GROUP BY employee_id, employee_name
        ORDER BY total_paid DESC
        LIMIT 10
    """)
    
    employees = cur.fetchall()
    print(f"   Found {len(employees)} employees in employee_pay_master")
    for emp_id, name, entries, total in employees:
        print(f"   Employee {emp_id:6d} | {name:30s} | {entries:6d} pay entries | ${total:12.2f}")
    
    # 7. Link strategy
    print(f"\n7️⃣ LINKING STRATEGY:")
    print("-" * 100)
    print("""
   APPROACH:
   - Employee payments → Link to employee_pay_master (find by name match)
   - Heffner payments → Link to special client record (client_id=3980)
   - Insurance payments → Link to vendor_account_ledger (create vendor account)
   - Vendor/Maintenance → Link to business_expenses or create vendor record
   
   PROCESS:
   1. For each non-customer banking transaction:
      a. Match description to employee name → Find employee_id
      b. Match description to special client → Find client_id
      c. Create payment record (or find existing)
      d. Update banking_transactions.reconciled_payment_id
   
   2. Do NOT link to charters (reserve_number):
      - These are non-charter transactions
      - Should have NULL reserve_number
      - Should link to vendors/employees instead
   """)
    
    cur.close()
    conn.close()
    
    print("\n" + "="*100)
    print("ANALYSIS COMPLETE - Ready for linking phase")
    print("="*100)

if __name__ == "__main__":
    try:
        analyze_noncustomer_transactions()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
