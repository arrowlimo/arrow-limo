"""
Create missing receipts for CHQ 203 - both Scotia (Doug Redmond) and CIBC (Carla Metuier).

These are two different cheques with the same number from different bank accounts.
"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("CREATE MISSING CHQ 203 RECEIPTS")
print("=" * 80)

# 1. Doug Redmond - Scotia Bank CHQ 203
print("\n1. SCOTIA BANK - CHQ 203 Doug Redmond $2,095.04")
print("-" * 80)

# Check if already exists
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE description LIKE '%CHQ 203%' 
      AND vendor_name LIKE '%REDMOND%'
      AND mapped_bank_account_id = 2
""")
existing = cur.fetchone()
if existing:
    print(f"✅ Receipt already exists: {existing[0]} | {existing[1]} | {existing[2]} | ${existing[3]:,.2f}")
else:
    print("Creating receipt for Scotia CHQ 203 Doug Redmond...")
    cur.execute("""
        INSERT INTO receipts (
            receipt_date,
            vendor_name,
            canonical_vendor,
            description,
            gross_amount,
            net_amount,
            gst_amount,
            payment_method,
            canonical_pay_method,
            mapped_bank_account_id,
            banking_transaction_id,
            created_from_banking,
            currency,
            source_system,
            receipt_source,
            created_at
        ) VALUES (
            '2013-06-24',
            'REDMOND, DOUG',
            'REDMOND, DOUG',
            'CHQ 203 Doug Redmond',
            2095.04,
            1995.28,  -- Net = 2095.04 / 1.05
            99.76,     -- GST = 2095.04 * 0.05 / 1.05
            'CHEQUE',
            'CHEQUE',
            2,  -- Scotia Bank
            78511,  -- Banking transaction ID
            true,
            'C',
            'BANKING',
            'Manual creation - missing cheque receipt',
            NOW()
        )
        RETURNING receipt_id
    """)
    receipt_id = cur.fetchone()[0]
    print(f"✅ Created receipt {receipt_id} for Scotia CHQ 203 Doug Redmond $2,095.04")

# 2. Carla Metuier - CIBC CHQ 203
print("\n2. CIBC BANK - CHQ 203 Carla Metuier $1,771.12")
print("-" * 80)

# Check if already exists
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE description LIKE '%CHQ 203%' 
      AND (vendor_name LIKE '%METUI%' OR vendor_name LIKE '%METIRI%')
      AND mapped_bank_account_id = 1
""")
existing = cur.fetchone()
if existing:
    print(f"✅ Receipt already exists: {existing[0]} | {existing[1]} | {existing[2]} | ${existing[3]:,.2f}")
else:
    print("Creating receipt for CIBC CHQ 203 Carla Metuier...")
    cur.execute("""
        INSERT INTO receipts (
            receipt_date,
            vendor_name,
            canonical_vendor,
            description,
            gross_amount,
            net_amount,
            gst_amount,
            payment_method,
            canonical_pay_method,
            mapped_bank_account_id,
            banking_transaction_id,
            created_from_banking,
            currency,
            source_system,
            receipt_source,
            created_at
        ) VALUES (
            '2012-01-04',
            'METUIER, CARLA',
            'METUIER, CARLA',
            'CHQ 203 Metuier, Carla',
            1771.12,
            1686.78,  -- Net = 1771.12 / 1.05
            84.34,     -- GST = 1771.12 * 0.05 / 1.05
            'CHEQUE',
            'CHEQUE',
            1,  -- CIBC
            81373,  -- Banking transaction ID
            true,
            'C',
            'BANKING',
            'Manual creation - missing cheque receipt',
            NOW()
        )
        RETURNING receipt_id
    """)
    receipt_id = cur.fetchone()[0]
    print(f"✅ Created receipt {receipt_id} for CIBC CHQ 203 Carla Metuier $1,771.12")

# 3. Verify banking transaction links
print("\n\n3. VERIFYING BANKING TRANSACTION LINKS")
print("-" * 80)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        COALESCE(bt.debit_amount, 0) as amount,
        bt.description,
        r.receipt_id,
        r.vendor_name
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE (bt.description LIKE '%CHQ 203%' OR bt.description LIKE '%CHEQUE 203%')
      AND bt.debit_amount IS NOT NULL
    ORDER BY bt.transaction_date
""")

print("\nCHQ 203 Banking Transactions:")
for tx_id, date, bank, amount, desc, receipt_id, vendor in cur.fetchall():
    receipt_status = f"✅ Receipt {receipt_id} ({vendor})" if receipt_id else "❌ NO RECEIPT"
    print(f"  TX {tx_id} | {date} | {bank:7} | ${amount:>10,.2f} | {desc[:50]:50} | {receipt_status}")

# Commit changes
conn.commit()
print("\n" + "=" * 80)
print("✅ ALL CHANGES COMMITTED")
print("=" * 80)

cur.close()
conn.close()
