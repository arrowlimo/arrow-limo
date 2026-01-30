#!/usr/bin/env python3
"""
Find All Cash Purchases in 2012
===============================

This script identifies all cash transactions and purchases in 2012
from multiple data sources to ensure complete cash flow documentation.

Sources analyzed:
- Banking transactions (cash withdrawals)
- Receipt records (cash payments)
- Charter payments (cash bookings)
- QuickBooks records (cash expenses)
- Payment records (cash method)

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def find_cash_withdrawals_2012(conn):
    """Find all cash withdrawals from banking transactions."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, account_number, transaction_id
        FROM banking_transactions 
        WHERE EXTRACT(year FROM transaction_date) = 2012
          AND COALESCE(debit_amount, 0) > 0
          AND (description ILIKE '%cash%withdrawal%' 
               OR description ILIKE '%atm%withdrawal%'
               OR description ILIKE '%cash%advance%'
               OR description ILIKE '%withdrawal%cash%'
               OR description ILIKE '%teller%cash%'
               OR description ILIKE '%branch%cash%')
        ORDER BY transaction_date, debit_amount DESC
    """)
    
    cash_withdrawals = cur.fetchall()
    cur.close()
    
    return cash_withdrawals

def find_cash_receipts_2012(conn):
    """Find all cash expense receipts."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description, 
               category, source_system, source_reference
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND (payment_method ILIKE '%cash%'
               OR pay_method ILIKE '%cash%'
               OR canonical_pay_method ILIKE '%cash%'
               OR description ILIKE '%cash%purchase%'
               OR description ILIKE '%cash%payment%')
        ORDER BY receipt_date, gross_amount DESC
    """)
    
    cash_receipts = cur.fetchall()
    cur.close()
    
    return cash_receipts

def find_cash_charter_payments_2012(conn):
    """Find charter bookings paid with cash."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT charter_date, client_id, total_amount_due, payment_status,
               reserve_number, passenger_count, vehicle, driver_name
        FROM charters 
        WHERE EXTRACT(year FROM charter_date) = 2012
          AND (payment_instructions ILIKE '%cash%'
               OR booking_notes ILIKE '%cash%'
               OR notes ILIKE '%cash%'
               OR client_notes ILIKE '%cash%')
        ORDER BY charter_date, total_amount_due DESC
    """)
    
    cash_charters = cur.fetchall()
    cur.close()
    
    return cash_charters

def find_cash_payments_2012(conn):
    """Find payment records marked as cash."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT payment_date, account_number, reserve_number, amount,
               payment_method, notes, client_id
        FROM payments 
        WHERE EXTRACT(year FROM payment_date) = 2012
          AND (payment_method ILIKE '%cash%'
               OR notes ILIKE '%cash%')
        ORDER BY payment_date, amount DESC
    """)
    
    cash_payments = cur.fetchall()
    cur.close()
    
    return cash_payments

def find_petty_cash_expenses_2012(conn):
    """Find small cash expenses and petty cash transactions."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description,
               category, source_system
        FROM receipts 
        WHERE EXTRACT(year FROM receipt_date) = 2012
          AND gross_amount BETWEEN 0.01 AND 100.00
          AND (vendor_name ILIKE '%petty%cash%'
               OR description ILIKE '%petty%cash%'
               OR description ILIKE '%small%purchase%'
               OR category ILIKE '%petty%'
               OR category ILIKE '%miscellaneous%')
        ORDER BY receipt_date, gross_amount
    """)
    
    petty_cash = cur.fetchall()
    cur.close()
    
    return petty_cash

def analyze_cash_flow_patterns_2012(conn):
    """Analyze cash flow patterns and potential cash purchases."""
    cur = conn.cursor()
    
    # Large cash withdrawals that might indicate major cash purchases
    cur.execute("""
        SELECT transaction_date, description, debit_amount,
               CASE 
                 WHEN debit_amount >= 1000 THEN 'Large Cash Withdrawal'
                 WHEN debit_amount >= 500 THEN 'Medium Cash Withdrawal'
                 ELSE 'Small Cash Withdrawal'
               END as withdrawal_category
        FROM banking_transactions 
        WHERE EXTRACT(year FROM transaction_date) = 2012
          AND COALESCE(debit_amount, 0) > 0
          AND (description ILIKE '%withdrawal%'
               OR description ILIKE '%cash%'
               OR description ILIKE '%atm%')
          AND debit_amount >= 100
        ORDER BY debit_amount DESC
    """)
    
    large_withdrawals = cur.fetchall()
    
    # Unmatched banking transactions that could be cash purchases
    cur.execute("""
        SELECT transaction_date, description, debit_amount, account_number
        FROM banking_transactions 
        WHERE EXTRACT(year FROM transaction_date) = 2012
          AND COALESCE(debit_amount, 0) > 0
          AND transaction_id NOT IN (
              SELECT DISTINCT mapped_bank_account_id 
              FROM receipts 
              WHERE mapped_bank_account_id IS NOT NULL
          )
          AND debit_amount < 1000  -- Potential cash purchases
          AND NOT (description ILIKE '%transfer%'
                  OR description ILIKE '%loan%'
                  OR description ILIKE '%nsf%')
        ORDER BY transaction_date, debit_amount DESC
    """)
    
    unmatched_debits = cur.fetchall()
    
    cur.close()
    
    return large_withdrawals, unmatched_debits

def main():
    conn = get_db_connection()
    
    try:
        print("💵 CASH PURCHASES ANALYSIS - 2012")
        print("=" * 40)
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Find cash withdrawals
        cash_withdrawals = find_cash_withdrawals_2012(conn)
        
        print("🏧 CASH WITHDRAWALS FROM BANKING")
        print("==============================")
        total_withdrawals = Decimal('0')
        
        if cash_withdrawals:
            print(f"{'Date':<12} {'Amount':<12} {'Description':<50}")
            print("-" * 75)
            
            for date, desc, amount, account, trans_id in cash_withdrawals:
                amount_dec = Decimal(str(amount))
                total_withdrawals += amount_dec
                print(f"{date} ${amount_dec:>10.2f} {desc[:47]}")
            
            print("-" * 75)
            print(f"Total Cash Withdrawals: ${total_withdrawals:,.2f} ({len(cash_withdrawals)} transactions)")
        else:
            print("No explicit cash withdrawals found in banking records")
        print()
        
        # Find cash receipts
        cash_receipts = find_cash_receipts_2012(conn)
        
        print("🧾 CASH EXPENSE RECEIPTS")
        print("=======================")
        total_cash_expenses = Decimal('0')
        
        if cash_receipts:
            print(f"{'Date':<12} {'Amount':<12} {'Vendor':<25} {'Category':<15}")
            print("-" * 70)
            
            for date, vendor, amount, desc, category, source, ref in cash_receipts:
                amount_dec = Decimal(str(amount))
                total_cash_expenses += amount_dec
                vendor_short = (vendor or 'Unknown')[:23]
                category_short = (category or 'N/A')[:13]
                print(f"{date} ${amount_dec:>10.2f} {vendor_short:<25} {category_short}")
            
            print("-" * 70)
            print(f"Total Cash Expenses: ${total_cash_expenses:,.2f} ({len(cash_receipts)} receipts)")
        else:
            print("No cash payment receipts found")
        print()
        
        # Find cash charter payments
        cash_charters = find_cash_charter_payments_2012(conn)
        
        print("🚗 CASH CHARTER BOOKINGS")
        print("=======================")
        total_cash_charters = Decimal('0')
        
        if cash_charters:
            print(f"{'Date':<12} {'Amount':<12} {'Reserve#':<10} {'Passengers':<10} {'Vehicle':<15}")
            print("-" * 65)
            
            for date, client, amount, status, reserve, passengers, vehicle, driver in cash_charters:
                amount_dec = Decimal(str(amount or 0))
                total_cash_charters += amount_dec
                reserve_str = str(reserve or 'N/A')[:8]
                passengers_str = str(passengers or 0)
                vehicle_short = (vehicle or 'N/A')[:13]
                print(f"{date} ${amount_dec:>10.2f} {reserve_str:<10} {passengers_str:<10} {vehicle_short}")
            
            print("-" * 65)
            print(f"Total Cash Charter Revenue: ${total_cash_charters:,.2f} ({len(cash_charters)} bookings)")
        else:
            print("No cash charter bookings found")
        print()
        
        # Find payment records
        cash_payments = find_cash_payments_2012(conn)
        
        print("💰 CASH PAYMENT RECORDS")
        print("======================")
        total_cash_payment_records = Decimal('0')
        
        if cash_payments:
            print(f"{'Date':<12} {'Amount':<12} {'Account':<12} {'Reserve#':<10} {'Method':<15}")
            print("-" * 65)
            
            for date, account, reserve, amount, method, notes, client in cash_payments:
                amount_dec = Decimal(str(amount))
                total_cash_payment_records += amount_dec
                account_str = str(account or 'N/A')[:10]
                reserve_str = str(reserve or 'N/A')[:8]
                method_short = (method or 'N/A')[:13]
                print(f"{date} ${amount_dec:>10.2f} {account_str:<12} {reserve_str:<10} {method_short}")
            
            print("-" * 65)
            print(f"Total Cash Payment Records: ${total_cash_payment_records:,.2f} ({len(cash_payments)} payments)")
        else:
            print("No cash payment records found")
        print()
        
        # Find petty cash expenses
        petty_cash = find_petty_cash_expenses_2012(conn)
        
        print("🪙 PETTY CASH & SMALL PURCHASES")
        print("==============================")
        total_petty_cash = Decimal('0')
        
        if petty_cash:
            print(f"{'Date':<12} {'Amount':<10} {'Vendor':<25} {'Description':<30}")
            print("-" * 80)
            
            for date, vendor, amount, desc, category, source in petty_cash:
                amount_dec = Decimal(str(amount))
                total_petty_cash += amount_dec
                vendor_short = (vendor or 'Unknown')[:23]
                desc_short = (desc or 'N/A')[:28]
                print(f"{date} ${amount_dec:>8.2f} {vendor_short:<25} {desc_short}")
            
            print("-" * 80)
            print(f"Total Petty Cash: ${total_petty_cash:,.2f} ({len(petty_cash)} transactions)")
        else:
            print("No petty cash transactions found")
        print()
        
        # Analyze cash flow patterns
        large_withdrawals, unmatched_debits = analyze_cash_flow_patterns_2012(conn)
        
        print("📊 CASH FLOW PATTERN ANALYSIS")
        print("=============================")
        
        print("Large Cash Withdrawals (Potential Cash Purchases):")
        if large_withdrawals:
            withdrawal_total = Decimal('0')
            for date, desc, amount, category in large_withdrawals[:10]:  # Top 10
                amount_dec = Decimal(str(amount))
                withdrawal_total += amount_dec
                print(f"  {date} ${amount_dec:>8.2f} - {desc[:40]} ({category})")
            print(f"  Total Large Withdrawals: ${withdrawal_total:,.2f}")
        else:
            print("  No large cash withdrawals identified")
        print()
        
        print("Unmatched Banking Debits (Potential Unrecorded Cash Purchases):")
        if unmatched_debits:
            unmatched_total = Decimal('0')
            for date, desc, amount, account in unmatched_debits[:10]:  # Top 10
                amount_dec = Decimal(str(amount))
                unmatched_total += amount_dec
                print(f"  {date} ${amount_dec:>8.2f} - {desc[:40]}")
            print(f"  Total Unmatched Debits: ${unmatched_total:,.2f}")
            if len(unmatched_debits) > 10:
                print(f"  ... and {len(unmatched_debits) - 10} more transactions")
        else:
            print("  No unmatched banking debits found")
        print()
        
        # Summary
        print("📋 CASH TRANSACTION SUMMARY - 2012")
        print("==================================")
        print(f"Cash Withdrawals (Banking): ${total_withdrawals:,.2f}")
        print(f"Cash Expense Receipts: ${total_cash_expenses:,.2f}")
        print(f"Cash Charter Revenue: ${total_cash_charters:,.2f}")
        print(f"Cash Payment Records: ${total_cash_payment_records:,.2f}")
        print(f"Petty Cash Expenses: ${total_petty_cash:,.2f}")
        print("-" * 40)
        
        total_documented_cash = (total_cash_expenses + total_petty_cash)
        cash_variance = total_withdrawals - total_documented_cash
        
        print(f"Total Documented Cash Expenses: ${total_documented_cash:,.2f}")
        print(f"Cash Variance (Withdrawals vs Expenses): ${cash_variance:,.2f}")
        
        if cash_variance > 100:
            print(f"[WARN]  Potential undocumented cash purchases: ${cash_variance:,.2f}")
        elif cash_variance < -100:
            print(f"ℹ️  Cash expenses exceed recorded withdrawals by ${abs(cash_variance):,.2f}")
        else:
            print("[OK] Cash withdrawals and expenses reasonably balanced")
        
        print()
        print("🔍 RECOMMENDATIONS:")
        print("==================")
        if len(unmatched_debits) > 0:
            print("• Review unmatched banking debits for potential cash purchases")
        if cash_variance > 100:
            print("• Investigate cash variance - may indicate missing expense receipts")
        if total_petty_cash > 0:
            print("• Ensure petty cash expenses have proper business justification")
        if total_cash_charters > 0:
            print("• Verify cash charter payments are properly recorded for tax purposes")
        
        print("• Consider implementing petty cash log for better cash tracking")
        print("• Review cash handling procedures for audit compliance")
    
    except Exception as e:
        print(f"[FAIL] Error analyzing cash purchases: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())