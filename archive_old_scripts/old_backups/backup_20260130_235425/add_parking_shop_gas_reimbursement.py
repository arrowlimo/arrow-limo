#!/usr/bin/env python3
"""
Record $310 gas bill reimbursement to Mike Woodrow (parking/shop landlord).

This is a pass-through expense: we paid the gas bill for the parking/shop
space, then reimbursed the landlord. The bill includes late fees.

Date: 2025-07-03
Amount: $310.00
Recipient: Mike Woodrow (landlord - parking and shop space)
Description: Gas bill reimbursement (includes late fees)
"""

import os
import psycopg2
from datetime import date

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

TRANSACTION_DATE = date(2025, 7, 3)
AMOUNT = 310.00
RECIPIENT = 'Mike Woodrow'
DESCRIPTION = 'Gas bill reimbursement for parking/shop space (includes late fees)'

def main():
    print("RECORDING PARKING/SHOP GAS BILL REIMBURSEMENT")
    print("=" * 80)
    
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            # Find the banking transaction
            cur.execute("""
                SELECT transaction_id, transaction_date, description, debit_amount
                FROM banking_transactions
                WHERE transaction_date = %s
                  AND description ILIKE %s
                  AND debit_amount = %s
            """, (TRANSACTION_DATE, '%Mike Woodrow%', AMOUNT))
            
            banking_row = cur.fetchone()
            if not banking_row:
                print(f"[FAIL] Banking transaction not found for {TRANSACTION_DATE} ${AMOUNT} to {RECIPIENT}")
                print("Searching for similar transactions...")
                cur.execute("""
                    SELECT transaction_id, transaction_date, description, debit_amount
                    FROM banking_transactions
                    WHERE transaction_date BETWEEN %s AND %s
                      AND debit_amount BETWEEN %s AND %s
                    ORDER BY transaction_date
                """, (date(2025, 7, 1), date(2025, 7, 31), 309.0, 311.0))
                similar = cur.fetchall()
                if similar:
                    print("\nSimilar transactions in July 2025:")
                    for row in similar:
                        print(f"  ID {row[0]} | {row[1]} | ${row[3]:.2f} | {row[2]}")
                return
            
            bank_id, bank_date, bank_desc, bank_amt = banking_row
            print(f"[OK] Found banking transaction:")
            print(f"   ID: {bank_id}")
            print(f"   Date: {bank_date}")
            print(f"   Amount: ${bank_amt:.2f}")
            print(f"   Description: {bank_desc}")
            
            # Check if receipt already exists
            cur.execute("""
                SELECT id FROM receipts
                WHERE source_system = %s
                  AND source_reference = %s
            """, ('BANKING_MANUAL', f'PARKING_SHOP_GAS_{TRANSACTION_DATE.strftime("%Y%m%d")}'))
            
            existing = cur.fetchone()
            if existing:
                print(f"\n[WARN]  Receipt already exists: ID {existing[0]}")
                return
            
            # Calculate GST (included in price)
            gst_amount = round(AMOUNT * 0.05 / 1.05, 2)
            net_amount = AMOUNT - gst_amount
            
            # Generate unique hash for dedup
            import hashlib
            hash_input = f"{TRANSACTION_DATE}|{RECIPIENT}|{AMOUNT}|{DESCRIPTION}"
            source_hash = hashlib.sha256(hash_input.encode()).hexdigest()
            
            print(f"\nGST Calculation (Alberta 5% included):")
            print(f"  Gross: ${AMOUNT:.2f}")
            print(f"  GST:   ${gst_amount:.2f}")
            print(f"  Net:   ${net_amount:.2f}")
            
            # Insert receipt (net_amount is auto-calculated)
            cur.execute("""
                INSERT INTO receipts (
                    vendor_name,
                    receipt_date,
                    category,
                    description,
                    source_system,
                    source_reference,
                    source_hash,
                    gross_amount,
                    gst_amount,
                    expense_account,
                    deductible_status,
                    business_personal,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
                RETURNING id
            """, (
                RECIPIENT,
                TRANSACTION_DATE,
                '6820 - Utilities',
                DESCRIPTION,
                'BANKING_MANUAL',
                f'PARKING_SHOP_GAS_{TRANSACTION_DATE.strftime("%Y%m%d")}',
                source_hash,
                AMOUNT,
                gst_amount,
                '6820',  # Utilities expense account
                'pass_through',  # Not tax deductible - reimbursement to landlord
                'landlord_reimbursement'
            ))
            
            receipt_id = cur.fetchone()[0]
            conn.commit()
            
            print(f"\n[OK] Receipt created: ID {receipt_id}")
            print(f"\nCategory: 6820 - Utilities (pass-through expense)")
            print(f"Note: This is a reimbursement to landlord for gas bill")
            print(f"      Not deductible as our business expense")


if __name__ == '__main__':
    main()
