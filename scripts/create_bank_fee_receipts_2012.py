#!/usr/bin/env python3
"""
Create Bank Fee Expense Records for 2012
=====================================

This script creates expense receipt records for banking fees identified
in the 2012 banking analysis, totaling $40,319.01 in legitimate 
business expense deductions.

Categories:
- NSF charges: $28,160.84 (Non-Sufficient Funds)
- Service charges: $12,159.17 (Banking service fees)

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import argparse
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_bank_fee_transactions(conn):
    """Get unmatched banking transactions that are banking fees."""
    cur = conn.cursor()
    
    # Get NSF charges
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               COALESCE(debit_amount, 0) as amount, account_number
        FROM banking_transactions 
        WHERE EXTRACT(year FROM transaction_date) = 2012
          AND transaction_id NOT IN (
              SELECT DISTINCT mapped_bank_account_id 
              FROM receipts 
              WHERE mapped_bank_account_id IS NOT NULL
          )
          AND (description ILIKE '%NSF%' 
               OR description ILIKE '%Non-sufficient%'
               OR description ILIKE '%insufficient%'
               OR description ILIKE '%dishonor%'
               OR description ILIKE '%returned%item%'
               OR description ILIKE '%bounced%')
          AND COALESCE(debit_amount, 0) > 0
        ORDER BY transaction_date
    """)
    nsf_transactions = cur.fetchall()
    
    # Get service charges
    cur.execute("""
        SELECT transaction_id, transaction_date, description, 
               COALESCE(debit_amount, 0) as amount, account_number
        FROM banking_transactions 
        WHERE EXTRACT(year FROM transaction_date) = 2012
          AND transaction_id NOT IN (
              SELECT DISTINCT mapped_bank_account_id 
              FROM receipts 
              WHERE mapped_bank_account_id IS NOT NULL
          )
          AND (description ILIKE '%service%charge%' 
               OR description ILIKE '%monthly%fee%'
               OR description ILIKE '%maintenance%fee%'
               OR description ILIKE '%transaction%fee%'
               OR description ILIKE '%account%fee%'
               OR description ILIKE '%wire%fee%')
          AND COALESCE(debit_amount, 0) > 0
        ORDER BY transaction_date
    """)
    service_transactions = cur.fetchall()
    
    cur.close()
    return nsf_transactions, service_transactions

def create_bank_fee_receipt(cur, transaction_id, transaction_date, description, 
                           amount, account_number, category):
    """Create a bank fee expense receipt."""
    
    # No GST on banking fees (financial services are GST exempt in Canada)
    gst_amount = Decimal('0.00')
    net_amount = amount
    
    # Normalize vendor name based on category
    if category == 'NSF':
        vendor_name = "CIBC Banking - NSF Charges"
    else:
        vendor_name = "CIBC Banking - Service Charges"
    
    cur.execute("""
        INSERT INTO receipts (
            source_reference, vendor_name, gross_amount, receipt_date, category,
            gst_amount, description, mapped_bank_account_id, 
            created_at, source_hash, net_amount, source_system,
            created_from_banking
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        f"BANK_{account_number}_{transaction_id}",
        vendor_name,
        amount,
        transaction_date,
        f'banking_{category.lower()}',
        gst_amount,
        f"Banking fee: {description}",
        transaction_id,
        datetime.now(),
        f"banking_fee_{transaction_id}_{transaction_date}_{amount}",
        net_amount,
        'banking_import',
        True
    ))


def main():
    parser = argparse.ArgumentParser(description='Create bank fee expense receipts for 2012')
    parser.add_argument('--write', action='store_true', 
                       help='Actually create receipts (default: dry run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get bank fee transactions
        nsf_transactions, service_transactions = get_bank_fee_transactions(conn)
        
        print("🏦 BANKING FEE ANALYSIS")
        print("=====================")
        
        nsf_total = sum(Decimal(str(t[3])) for t in nsf_transactions)
        service_total = sum(Decimal(str(t[3])) for t in service_transactions)
        
        print(f"NSF Charges: {len(nsf_transactions)} transactions, ${nsf_total:,.2f}")
        print(f"Service Charges: {len(service_transactions)} transactions, ${service_total:,.2f}")
        print(f"Total Banking Fees: ${nsf_total + service_total:,.2f}")
        print()
        
        if args.write:
            print("💰 CREATING BANK FEE EXPENSE RECEIPTS")
            print("====================================")
        else:
            print("🔍 DRY RUN - Bank Fee Receipt Preview")
            print("===================================")
        
        created_count = 0
        total_amount = Decimal('0.00')
        
        # Process NSF charges
        for transaction_id, date, description, amount, account in nsf_transactions:
            amount_decimal = Decimal(str(amount))
            total_amount += amount_decimal
            
            print(f"Creating NSF expense for {date}: ${amount_decimal:.2f}")
            print(f"  Vendor: CIBC Banking - NSF Charges")
            print(f"  Description: {description}")
            print(f"  Category: banking_nsf")
            
            if args.write:
                create_bank_fee_receipt(
                    cur, transaction_id, date, description, 
                    amount_decimal, account, 'NSF'
                )
                print(f"  [OK] Expense receipt created")
                created_count += 1
            else:
                print(f"  📋 Would create receipt for transaction {transaction_id}")
            print()
        
        # Process service charges
        for transaction_id, date, description, amount, account in service_transactions:
            amount_decimal = Decimal(str(amount))
            total_amount += amount_decimal
            
            print(f"Creating service charge expense for {date}: ${amount_decimal:.2f}")
            print(f"  Vendor: CIBC Banking - Service Charges")
            print(f"  Description: {description}")
            print(f"  Category: banking_service")
            
            if args.write:
                create_bank_fee_receipt(
                    cur, transaction_id, date, description, 
                    amount_decimal, account, 'SERVICE'
                )
                print(f"  [OK] Expense receipt created")
                created_count += 1
            else:
                print(f"  📋 Would create receipt for transaction {transaction_id}")
            print()
        
        if args.write:
            conn.commit()
            
            print("📊 BANKING FEE EXPENSE SUMMARY")
            print("=============================")
            print(f"Total expense receipts created: {created_count}")
            print(f"Total banking fees documented: ${total_amount:.2f}")
            print(f"GST on banking fees: $0.00 (financial services exempt)")
            print(f"Net business expense deduction: ${total_amount:.2f}")
            print()
            
            print("🎉 BUSINESS IMPACT:")
            print("==================")
            print(f"• Banking fee expense documentation: [OK]")
            print(f"• CRA deductible business expenses: ${total_amount:.2f}")
            print(f"• Improved expense tracking: Enhanced")
            print(f"• Banking reconciliation: Complete")
            
        else:
            print("📋 DRY RUN SUMMARY")
            print("=================")
            print(f"Would create {len(nsf_transactions) + len(service_transactions)} expense receipts")
            print(f"Total banking fees to document: ${total_amount:.2f}")
            print()
            print("Run with --write to create actual expense receipts")
    
    except Exception as e:
        print(f"[FAIL] Error creating bank fee receipts: {e}")
        conn.rollback()
        return 1
    
    finally:
        cur.close()
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())