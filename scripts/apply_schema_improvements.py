#!/usr/bin/env python3
"""
Apply schema improvements for invoice-banking matching
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*70)
print("APPLYING SCHEMA IMPROVEMENTS")
print("="*70)

try:
    # 1. Add fiscal_year to receipts
    print("\n1. Adding fiscal_year column to receipts...")
    cur.execute("""
        ALTER TABLE receipts 
        ADD COLUMN IF NOT EXISTS fiscal_year INTEGER
    """)
    print("   ✓ Column added")
    
    # Populate fiscal_year from receipt_date
    cur.execute("""
        UPDATE receipts 
        SET fiscal_year = EXTRACT(YEAR FROM receipt_date)
        WHERE fiscal_year IS NULL AND receipt_date IS NOT NULL
    """)
    print(f"   ✓ Populated {cur.rowcount} records with fiscal_year")
    
    # Set Receipt 145296 to 2011 (prior-year settlement)
    cur.execute("""
        UPDATE receipts 
        SET fiscal_year = 2011
        WHERE receipt_id = 145296
    """)
    print(f"   ✓ Set Receipt 145296 to fiscal_year = 2011")
    
    # 2. Add invoice tracking columns
    print("\n2. Adding invoice tracking columns to receipts...")
    cur.execute("""
        ALTER TABLE receipts 
        ADD COLUMN IF NOT EXISTS invoice_date DATE,
        ADD COLUMN IF NOT EXISTS due_date DATE,
        ADD COLUMN IF NOT EXISTS period_start DATE,
        ADD COLUMN IF NOT EXISTS period_end DATE
    """)
    print("   ✓ Columns added: invoice_date, due_date, period_start, period_end")
    
    # Set invoice_date = receipt_date for existing records
    cur.execute("""
        UPDATE receipts 
        SET invoice_date = receipt_date
        WHERE invoice_date IS NULL 
          AND receipt_date IS NOT NULL
          AND gross_amount > 0
    """)
    print(f"   ✓ Set invoice_date for {cur.rowcount} existing invoices")
    
    # 3. Add amount_allocated to ledger
    print("\n3. Adding amount_allocated to banking_receipt_matching_ledger...")
    cur.execute("""
        ALTER TABLE banking_receipt_matching_ledger 
        ADD COLUMN IF NOT EXISTS amount_allocated NUMERIC(10,2),
        ADD COLUMN IF NOT EXISTS allocation_date TIMESTAMP DEFAULT NOW(),
        ADD COLUMN IF NOT EXISTS allocation_type VARCHAR(50) DEFAULT 'payment'
    """)
    print("   ✓ Columns added: amount_allocated, allocation_date, allocation_type")
    
    # Populate amount_allocated from receipts
    cur.execute("""
        UPDATE banking_receipt_matching_ledger brml
        SET amount_allocated = r.gross_amount
        FROM receipts r
        WHERE brml.receipt_id = r.receipt_id
          AND brml.amount_allocated IS NULL
    """)
    print(f"   ✓ Populated amount_allocated for {cur.rowcount} existing links")
    
    # 4. Create index for fiscal_year queries
    print("\n4. Creating indexes for performance...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_receipts_fiscal_year 
        ON receipts(fiscal_year)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_receipts_invoice_date 
        ON receipts(invoice_date)
    """)
    print("   ✓ Indexes created")
    
    conn.commit()
    print("\n" + "="*70)
    print("✅ ALL SCHEMA CHANGES COMMITTED SUCCESSFULLY")
    print("="*70)
    
    # Verify the changes
    print("\n5. Verification:")
    print("-" * 70)
    
    # Check 2012 WCB balance excluding 2011
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = 'WCB'
          AND gross_amount > 0
          AND fiscal_year = 2012
    """)
    count, total = cur.fetchone()
    print(f"\n2012 WCB Invoices (fiscal_year = 2012):")
    print(f"  Count: {count}")
    print(f"  Total: ${total:,.2f}")
    
    # Check 2011 records
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = 'WCB'
          AND gross_amount > 0
          AND fiscal_year = 2011
    """)
    count, total = cur.fetchone()
    print(f"\n2011 WCB Invoices (fiscal_year = 2011):")
    print(f"  Count: {count}")
    print(f"  Total: ${total:,.2f}")
    
    # Calculate new 2012 balance
    cur.execute("""
        SELECT COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = 'WCB'
          AND gross_amount > 0
          AND fiscal_year = 2012
    """)
    invoices_2012 = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COALESCE(SUM(debit_amount), 0)
        FROM banking_transactions
        WHERE transaction_id IN (69282, 69587)
    """)
    banking_payments = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE receipt_id IN (145297, 145305) 
          AND vendor_name = 'WCB'
    """)
    receipt_payments = cur.fetchone()[0]
    
    total_payments = banking_payments + receipt_payments
    balance = invoices_2012 - total_payments
    
    print(f"\n2012 Balance Calculation:")
    print(f"  Invoices (fiscal 2012): ${invoices_2012:>10,.2f}")
    print(f"  Payments:               ${total_payments:>10,.2f}")
    print(f"  Balance:                ${balance:>10,.2f}")
    print(f"  Target:                 $   3,593.83")
    
    from decimal import Decimal
    diff = balance - Decimal('3593.83')
    if abs(diff) < Decimal('0.01'):
        print(f"\n  ✅ PERFECT MATCH!")
    else:
        print(f"  Difference:             ${diff:>10,.2f}")

except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
