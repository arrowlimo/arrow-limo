#!/usr/bin/env python3
"""
Categorize receipts by source type and add color coding flags.
- Banking: Matched to banking_transactions (GREEN)
- Cash: Cash payments, no banking match expected (YELLOW)
- Reimbursement: Employee reimbursements through cash box (ORANGE)
- Manual: Manually entered, may need matching (BLUE)
- Unmatched: Should have banking match but doesn't (RED)
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*80)
print('CATEGORIZING RECEIPT SOURCES WITH COLOR CODING')
print('='*80)
print(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# Step 1: Add receipt_source and display_color columns if not exist
print('STEP 1: Adding receipt_source and display_color columns')
print('-'*80)

# Check if columns exist
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'receipts' AND column_name IN ('receipt_source', 'display_color')
""")
existing_cols = {row[0] for row in cur.fetchall()}

if 'receipt_source' not in existing_cols:
    cur.execute("""
        ALTER TABLE receipts
        ADD COLUMN receipt_source VARCHAR(50)
    """)
    print('✅ Added receipt_source column')
else:
    print('✅ receipt_source column already exists')

if 'display_color' not in existing_cols:
    cur.execute("""
        ALTER TABLE receipts
        ADD COLUMN display_color VARCHAR(20)
    """)
    print('✅ Added display_color column')
else:
    print('✅ display_color column already exists')

conn.commit()
print()

# Step 2: Identify CASH receipts (no banking match expected)
print('STEP 2: Identifying CASH receipts')
print('-'*80)

CASH_KEYWORDS = ['CASH', 'PETTY CASH', 'CASH BOX', 'CASH PAYMENT']

cur.execute("""
    UPDATE receipts
    SET receipt_source = 'CASH',
        display_color = 'YELLOW'
    WHERE (
        vendor_name ILIKE ANY(ARRAY['%CASH%', '%PETTY CASH%', '%CASH BOX%'])
        OR description ILIKE ANY(ARRAY['%CASH PAYMENT%', '%PETTY CASH%', '%CASH BOX%'])
        OR category = 'cash_payment'
    )
    AND receipt_source IS NULL
""")

cash_count = cur.rowcount
print(f'Categorized: {cash_count:,} CASH receipts (YELLOW)')
print()

# Step 3: Identify REIMBURSEMENT receipts
print('STEP 3: Identifying REIMBURSEMENT receipts')
print('-'*80)

cur.execute("""
    UPDATE receipts
    SET receipt_source = 'REIMBURSEMENT',
        display_color = 'ORANGE'
    WHERE (
        vendor_name ILIKE ANY(ARRAY['%REIMBURSEMENT%', '%REIMBURSE%', '%EMPLOYEE EXPENSE%'])
        OR description ILIKE ANY(ARRAY['%REIMBURSEMENT%', '%REIMBURSE%', '%EMPLOYEE EXPENSE%'])
        OR category = 'employee_reimbursement'
    )
    AND receipt_source IS NULL
""")

reimburse_count = cur.rowcount
print(f'Categorized: {reimburse_count:,} REIMBURSEMENT receipts (ORANGE)')
print()

# Step 4: Mark receipts already matched to banking
print('STEP 4: Marking BANKING-matched receipts')
print('-'*80)

cur.execute("""
    UPDATE receipts
    SET receipt_source = 'BANKING',
        display_color = 'GREEN'
    WHERE banking_transaction_id IS NOT NULL
    AND receipt_source IS NULL
""")

banking_count = cur.rowcount
print(f'Categorized: {banking_count:,} BANKING receipts (GREEN)')
print()

# Step 5: Mark manually created receipts
print('STEP 5: Identifying MANUAL receipts')
print('-'*80)

cur.execute("""
    UPDATE receipts
    SET receipt_source = 'MANUAL',
        display_color = 'BLUE'
    WHERE (
        created_from_banking = FALSE
        OR created_from_banking IS NULL
    )
    AND banking_transaction_id IS NULL
    AND receipt_source IS NULL
    AND receipt_source NOT IN ('CASH', 'REIMBURSEMENT')
""")

manual_count = cur.rowcount
print(f'Categorized: {manual_count:,} MANUAL receipts (BLUE)')
print()

# Step 6: Remaining are UNMATCHED (should have banking but don't)
print('STEP 6: Marking UNMATCHED receipts (need attention)')
print('-'*80)

cur.execute("""
    UPDATE receipts
    SET receipt_source = 'UNMATCHED',
        display_color = 'RED'
    WHERE receipt_source IS NULL
    AND created_from_banking = TRUE
    AND banking_transaction_id IS NULL
""")

unmatched_count = cur.rowcount
print(f'Categorized: {unmatched_count:,} UNMATCHED receipts (RED - need review)')
print()

conn.commit()

# Step 7: Summary
print('='*80)
print('CATEGORIZATION SUMMARY')
print('='*80)

cur.execute("""
    SELECT 
        receipt_source,
        display_color,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    GROUP BY receipt_source, display_color
    ORDER BY 
        CASE receipt_source
            WHEN 'BANKING' THEN 1
            WHEN 'CASH' THEN 2
            WHEN 'REIMBURSEMENT' THEN 3
            WHEN 'MANUAL' THEN 4
            WHEN 'UNMATCHED' THEN 5
            ELSE 6
        END
""")

print(f"{'Source':20} | {'Color':10} | {'Count':>10} | {'Total Amount':>15}")
print('-'*70)
for source, color, count, amount in cur.fetchall():
    source_str = source if source else 'NULL'
    color_str = color if color else 'NULL'
    amount_val = float(amount) if amount else 0.0
    print(f'{source_str:20} | {color_str:10} | {count:>10,} | ${amount_val:>14,.2f}')

print()

# Step 8: Next actions
print('NEXT ACTIONS:')
print('-'*80)
print('✅ GREEN (BANKING): Already reconciled - no action needed')
print('✅ YELLOW (CASH): Cash box payments - handle through cash reconciliation')
print('✅ ORANGE (REIMBURSEMENT): Employee expenses - handle through payroll')
print('🔵 BLUE (MANUAL): May need matching - run intelligent matcher')
print('🔴 RED (UNMATCHED): Created from banking but link lost - needs investigation')
print()

cur.close()
conn.close()
