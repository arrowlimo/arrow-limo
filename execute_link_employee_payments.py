#!/usr/bin/env python3
"""Execute: Create employee pay records and link e-transfers."""
import psycopg2
import os
from datetime import datetime, timedelta

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "=" * 140)
print("EXECUTE: Link Employee E-Transfers to Employee Pay/Reimbursement".center(140))
print("=" * 140)

EMPLOYEE_NAMES = ['PAUL RICHARD', 'SHERRI RYCKMAN', 'SHERRI', 'DAVID RICHARD', 'DAVID WILLIAM', 
                  'MICHAEL RICHARD', 'BARB', 'BARBARA', 'PEACOCK', 'JERRY', 'JEANNIE', 'MATTHEW']

try:
    # Step 1: Get or create Employee Pay charter
    print("\n1️⃣ Checking for Employee Pay charter...")
    
    cur.execute('''
        SELECT charter_id, reserve_number 
        FROM charters 
        WHERE reserve_number = 'EMP_PAY' 
        LIMIT 1;
    ''')
    
    emp_charter = cur.fetchone()
    
    if emp_charter:
        emp_charter_id, emp_reserve = emp_charter
        print(f"   ✅ Found existing: charter_id={emp_charter_id}, reserve_number={emp_reserve}")
    else:
        print("   Creating new Employee Pay charter...")
        
        # Create a special charter for employee payments
        cur.execute('''
            INSERT INTO charters 
            (charter_date, pickup_time, reserve_number, client_id, status, 
             total_amount_due, paid_amount, created_at, updated_at)
            VALUES 
            (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING charter_id;
        ''', (
            datetime.now().date(),
            datetime.now().time(),
            'EMP_PAY',
            1,  # Assuming client_id=1 or create a special employee client
            'active',
            0,  # No amount due
            0   # No paid amount
        ))
        
        emp_charter_id = cur.fetchone()[0]
        emp_reserve = 'EMP_PAY'
        conn.commit()
        print(f"   ✅ Created: charter_id={emp_charter_id}, reserve_number={emp_reserve}")
    
    # Step 2: Get employee banking transactions (excluding NSF pairs)
    print(f"\n2️⃣ Identifying {240} valid employee payments...")
    
    cur.execute('''
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.credit_amount,
            bt.description
        FROM banking_transactions bt
        WHERE bt.credit_amount > 0
          AND bt.reconciled_payment_id IS NULL
    ''')
    
    all_banking = cur.fetchall()
    
    # Filter for employees
    employee_payments = []
    for row in all_banking:
        trans_id, trans_date, amount, desc = row
        if any(name in desc.upper() for name in EMPLOYEE_NAMES):
            employee_payments.append(row)
    
    # Exclude NSF pairs
    valid_employee_payments = []
    for etransfer in employee_payments:
        trans_id, trans_date, amount, desc = etransfer
        
        # Check for NSF reversal
        cur.execute('''
            SELECT COUNT(*) FROM banking_transactions
            WHERE debit_amount > 0
              AND ABS(debit_amount - %s) < 0.01
              AND transaction_date BETWEEN %s AND %s
        ''', (amount, trans_date - timedelta(days=3), trans_date + timedelta(days=3)))
        
        if cur.fetchone()[0] == 0:
            # No NSF debit found - this is valid
            valid_employee_payments.append(etransfer)
    
    print(f"   ✅ Valid employee payments: {len(valid_employee_payments)}")
    print(f"      Total: ${sum(e[2] for e in valid_employee_payments):,.2f}")
    
    # Step 3: Create payment records and link to banking
    print(f"\n3️⃣ Creating {len(valid_employee_payments)} payment records...")
    
    created_count = 0
    for payment in valid_employee_payments:
        trans_id, trans_date, amount, desc = payment
        
        # Insert payment record
        cur.execute('''
            INSERT INTO payments 
            (reserve_number, amount, payment_date, payment_method, status, created_at, updated_at)
            VALUES 
            (%s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING payment_id;
        ''', (
            emp_reserve,
            amount,
            trans_date,
            'etransfer' if 'ETRANSFER' in desc.upper() or 'E-TRANSFER' in desc.upper() else 'check',
            'completed'
        ))
        
        payment_id = cur.fetchone()[0]
        
        # Link banking transaction
        cur.execute('''
            UPDATE banking_transactions
            SET reconciled_payment_id = %s,
                updated_at = NOW()
            WHERE transaction_id = %s;
        ''', (payment_id, trans_id))
        
        created_count += cur.rowcount
    
    conn.commit()
    
    print(f"   ✅ Created and linked {created_count} payment records")
    
    # Step 4: Verify
    print(f"\n4️⃣ Verification:")
    
    cur.execute('''
        SELECT COUNT(*), SUM(amount)
        FROM payments
        WHERE reserve_number = %s;
    ''', (emp_reserve,))
    
    pmt_count, pmt_total = cur.fetchone()
    print(f"   Payments for {emp_reserve}: {pmt_count} | ${pmt_total if pmt_total else 0:,.2f}")
    
    cur.execute('''
        SELECT COUNT(*), SUM(credit_amount)
        FROM banking_transactions
        WHERE reconciled_payment_id IS NOT NULL
          AND credit_amount > 0
          AND (description ILIKE '%PAUL RICHARD%' 
               OR description ILIKE '%SHERRI RYCKMAN%' 
               OR description ILIKE '%BARB PEACOCK%'
               OR description ILIKE '%DAVID RICHARD%'
               OR description ILIKE '%SHERRI%'
               OR description ILIKE '%MATTHEW%'
               OR description ILIKE '%JERRY%'
               OR description ILIKE '%JEANNIE%');
    ''')
    
    banking_linked = cur.fetchone()
    print(f"   Banking transactions linked: {banking_linked[0]} | ${banking_linked[1] if banking_linked[1] else 0:,.2f}")
    
    print(f"\n" + "=" * 140)
    print("✅ EMPLOYEE PAYMENT LINKING COMPLETE".center(140))
    print("=" * 140)
    print(f"""
Summary:
  ✅ Created employee pay charter: reserve_number = '{emp_reserve}'
  ✅ Created {created_count} payment records
  ✅ Linked {created_count} banking transactions
  ✅ Total amount: ${sum(e[2] for e in valid_employee_payments):,.2f}
  
Excluded:
  ⚠️  NSF pairs (reversals): {len(employee_payments) - len(valid_employee_payments)} transactions
  
These employee payments are now segregated from customer charter payments.
""")
    
    print("=" * 140 + "\n")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise

finally:
    cur.close()
    conn.close()
