#!/usr/bin/env python3
"""
Find banking transactions (especially Square, e-transfers) without matching receipts.
This checks for potential missing revenue or expense recording.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("BANKING TRANSACTIONS WITHOUT RECEIPTS - MISSING REVENUE/EXPENSE CHECK")
print("=" * 120)

# Find banking transactions without receipts
cur.execute("""
    SELECT 
        b.transaction_id,
        b.transaction_date,
        b.description,
        b.debit_amount,
        b.credit_amount,
        b.balance
    FROM banking_transactions b
    LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
    WHERE r.receipt_id IS NULL
    AND b.transaction_date IS NOT NULL
    ORDER BY b.transaction_date DESC, ABS(COALESCE(b.debit_amount, 0) + COALESCE(b.credit_amount, 0)) DESC
""")

unmatched = cur.fetchall()

print(f"\nFound {len(unmatched)} banking transactions WITHOUT receipts\n")

if len(unmatched) > 0:
    # Categorize by type
    square_deposits = []
    etransfers = []
    cash_deposits = []
    cheque_deposits = []
    other_credits = []
    debits = []
    
    for tx in unmatched:
        tx_id, date, desc, debit, credit, balance = tx
        desc_upper = (desc or '').upper()
        
        if credit and credit > 0:  # Money IN
            if 'SQUARE' in desc_upper:
                square_deposits.append(tx)
            elif 'EMAIL TRANSFER' in desc_upper or 'INTERAC E-TRANSFER' in desc_upper:
                etransfers.append(tx)
            elif 'CASH DEPOSIT' in desc_upper or 'ATM DEPOSIT' in desc_upper:
                cash_deposits.append(tx)
            elif 'CHEQUE' in desc_upper or 'CHQ' in desc_upper:
                cheque_deposits.append(tx)
            else:
                other_credits.append(tx)
        elif debit and debit > 0:  # Money OUT
            debits.append(tx)
    
    # Display Square deposits without receipts
    if square_deposits:
        print("=" * 120)
        print(f"SQUARE DEPOSITS WITHOUT RECEIPTS ({len(square_deposits)} transactions)")
        print("=" * 120)
        total_square = sum(tx[4] for tx in square_deposits)  # credit_amount
        print(f"\nTotal missing Square revenue: ${total_square:,.2f}\n")
        
        for tx_id, date, desc, debit, credit, balance in square_deposits[:20]:
            print(f"  {date} | ${credit:>10,.2f}")
            print(f"    TX #{tx_id}: {desc[:100]}")
            print()
        
        if len(square_deposits) > 20:
            print(f"  ... and {len(square_deposits) - 20} more Square deposits\n")
    
    # Display e-transfers without receipts
    if etransfers:
        print("=" * 120)
        print(f"E-TRANSFERS WITHOUT RECEIPTS ({len(etransfers)} transactions)")
        print("=" * 120)
        total_etransfer = sum(tx[4] for tx in etransfers if tx[4])
        print(f"\nTotal missing e-transfer revenue: ${total_etransfer:,.2f}\n")
        
        for tx_id, date, desc, debit, credit, balance in etransfers[:20]:
            print(f"  {date} | ${credit:>10,.2f}")
            print(f"    TX #{tx_id}: {desc[:100]}")
            print()
        
        if len(etransfers) > 20:
            print(f"  ... and {len(etransfers) - 20} more e-transfers\n")
    
    # Display cash deposits without receipts
    if cash_deposits:
        print("=" * 120)
        print(f"CASH DEPOSITS WITHOUT RECEIPTS ({len(cash_deposits)} transactions)")
        print("=" * 120)
        total_cash = sum(tx[4] for tx in cash_deposits)
        print(f"\nTotal missing cash deposits: ${total_cash:,.2f}\n")
        
        for tx_id, date, desc, debit, credit, balance in cash_deposits[:10]:
            print(f"  {date} | ${credit:>10,.2f}")
            print(f"    TX #{tx_id}: {desc[:100]}")
            print()
    
    # Display other credits (potential revenue)
    if other_credits:
        print("=" * 120)
        print(f"OTHER CREDITS WITHOUT RECEIPTS ({len(other_credits)} transactions)")
        print("=" * 120)
        total_other = sum(tx[4] for tx in other_credits)
        print(f"\nTotal other credits: ${total_other:,.2f}\n")
        
        for tx_id, date, desc, debit, credit, balance in other_credits[:10]:
            print(f"  {date} | ${credit:>10,.2f}")
            print(f"    TX #{tx_id}: {desc[:100]}")
            print()
        
        if len(other_credits) > 10:
            print(f"  ... and {len(other_credits) - 10} more credit transactions\n")
    
    # Display debits (expenses) without receipts
    if debits:
        print("=" * 120)
        print(f"DEBITS (EXPENSES) WITHOUT RECEIPTS ({len(debits)} transactions)")
        print("=" * 120)
        total_debits = sum(tx[3] for tx in debits)  # debit_amount
        print(f"\nTotal expenses without receipts: ${total_debits:,.2f}\n")
        
        for tx_id, date, desc, debit, credit, balance in debits[:10]:
            print(f"  {date} | ${debit:>10,.2f}")
            print(f"    TX #{tx_id}: {desc[:100]}")
            print()
        
        if len(debits) > 10:
            print(f"  ... and {len(debits) - 10} more expense transactions\n")

# Summary by category
print("=" * 120)
print("SUMMARY - UNMATCHED BANKING TRANSACTIONS")
print("=" * 120)

cur.execute("""
    SELECT 
        CASE 
            WHEN b.credit_amount > 0 AND b.description ILIKE '%square%' THEN 'Square Deposits'
            WHEN b.credit_amount > 0 AND (b.description ILIKE '%email transfer%' OR b.description ILIKE '%interac e-transfer%') THEN 'E-Transfers (In)'
            WHEN b.credit_amount > 0 AND b.description ILIKE '%cash deposit%' THEN 'Cash Deposits'
            WHEN b.credit_amount > 0 AND b.description ILIKE '%cheque%' THEN 'Cheque Deposits'
            WHEN b.credit_amount > 0 THEN 'Other Credits'
            WHEN b.debit_amount > 0 THEN 'Debits (Expenses)'
            ELSE 'Unknown'
        END as category,
        COUNT(*) as count,
        SUM(COALESCE(b.credit_amount, 0)) as total_credits,
        SUM(COALESCE(b.debit_amount, 0)) as total_debits
    FROM banking_transactions b
    LEFT JOIN receipts r ON r.banking_transaction_id = b.transaction_id
    WHERE r.receipt_id IS NULL
    AND b.transaction_date IS NOT NULL
    GROUP BY category
    ORDER BY SUM(COALESCE(b.credit_amount, 0) + COALESCE(b.debit_amount, 0)) DESC
""")

summary = cur.fetchall()

if summary:
    print(f"\n{'Category':<25} {'Count':<10} {'Credits (In)':<18} {'Debits (Out)':<18}")
    print("-" * 120)
    for category, count, credits, debits in summary:
        credit_str = f"${credits:,.2f}" if credits else "-"
        debit_str = f"${debits:,.2f}" if debits else "-"
        print(f"{category:<25} {count:<10} {credit_str:<18} {debit_str:<18}")
    
    total_unmatched_credits = sum(row[2] for row in summary if row[2])
    total_unmatched_debits = sum(row[3] for row in summary if row[3])
    
    print("-" * 120)
    print(f"{'TOTAL':<25} {len(unmatched):<10} ${total_unmatched_credits:>15,.2f}  ${total_unmatched_debits:>15,.2f}")
    
    print("\n" + "=" * 120)
    print("INTERPRETATION")
    print("=" * 120)
    print("\nPotential Issues:")
    if total_unmatched_credits > 0:
        print(f"  ⚠️  ${total_unmatched_credits:,.2f} in REVENUE without receipts (missing income recording)")
    if total_unmatched_debits > 0:
        print(f"  ⚠️  ${total_unmatched_debits:,.2f} in EXPENSES without receipts (missing expense recording)")
    
    print("\nLegitimate reasons for unmatched banking:")
    print("  - Bank fees (recorded as receipts, not linked)")
    print("  - Transfers between accounts (not revenue/expense)")
    print("  - NSF/returned payments (may not need receipts)")
    print("  - Payroll deposits (recorded in payroll system)")
    print("  - Loan payments (principal portion)")
    
else:
    print("\n✅ ALL banking transactions have matching receipts!")

cur.close()
conn.close()

print("\n" + "=" * 120)
