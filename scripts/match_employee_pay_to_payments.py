#!/usr/bin/env python3
"""
Match Employee Pay to Payment Records - 2012
===========================================

This script matches employee payroll records from driver_payroll table
to payment records to reconcile cash payments and employee compensation.

This is critical for understanding the $727K in cash payments discovered
and ensuring proper employee pay documentation.

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal
from datetime import datetime, timedelta
import re

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_employee_payroll_2012(conn):
    """Analyze employee payroll records for 2012."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            id, driver_id, year, month, charter_id, reserve_number,
            pay_date, gross_pay, cpp, ei, tax, total_deductions, 
            net_pay, expenses, wcb_payment, employee_id
        FROM driver_payroll 
        WHERE year = 2012
        ORDER BY pay_date, gross_pay DESC
    """)
    
    payroll_records = cur.fetchall()
    
    # Get payroll summary by month
    cur.execute("""
        SELECT 
            month,
            COUNT(*) as pay_entries,
            SUM(gross_pay) as total_gross,
            SUM(net_pay) as total_net,
            SUM(total_deductions) as total_deductions,
            COUNT(DISTINCT driver_id) as unique_drivers
        FROM driver_payroll 
        WHERE year = 2012
        GROUP BY month
        ORDER BY month
    """)
    
    monthly_summary = cur.fetchall()
    
    cur.close()
    return payroll_records, monthly_summary

def get_cash_payment_records_2012(conn):
    """Get all cash payment records for matching."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            payment_date, account_number, reserve_number, amount,
            payment_method, notes, client_id, payment_id
        FROM payments 
        WHERE EXTRACT(year FROM payment_date) = 2012
          AND (payment_method ILIKE '%cash%' OR notes ILIKE '%cash%')
        ORDER BY payment_date, amount DESC
    """)
    
    cash_payments = cur.fetchall()
    cur.close()
    return cash_payments

def match_payroll_to_payments(payroll_records, cash_payments):
    """Match payroll records to cash payment records."""
    matches = []
    unmatched_payroll = []
    unmatched_payments = list(cash_payments)
    
    for payroll in payroll_records:
        (payroll_id, driver_id, year, month, charter_id, reserve_number,
         pay_date, gross_pay, cpp, ei, tax, deductions, net_pay, 
         expenses, wcb_payment, employee_id) = payroll
        
        # Look for matching cash payments
        best_match = None
        best_score = 0
        
        for i, payment in enumerate(unmatched_payments):
            (payment_date, account_number, payment_reserve, amount,
             payment_method, notes, client_id, payment_id) = payment
            
            score = 0
            
            # Date proximity (within 7 days)
            if pay_date and payment_date:
                date_diff = abs((pay_date - payment_date).days)
                if date_diff <= 7:
                    score += 50 - (date_diff * 5)  # Closer dates get higher scores
            
            # Amount matching (exact or close)
            if gross_pay and amount:
                amount_diff = abs(float(gross_pay) - float(amount))
                if amount_diff == 0:
                    score += 100  # Exact match
                elif amount_diff <= 50:
                    score += 80 - amount_diff  # Close match
            
            # Net pay matching
            if net_pay and amount:
                net_diff = abs(float(net_pay) - float(amount))
                if net_diff == 0:
                    score += 100
                elif net_diff <= 50:
                    score += 80 - net_diff
            
            # Reserve number matching
            if reserve_number and payment_reserve:
                if str(reserve_number) == str(payment_reserve):
                    score += 75
            
            # Driver ID in notes or account number
            if driver_id and (notes or str(account_number)):
                search_text = f"{notes or ''} {account_number or ''}"
                if str(driver_id) in search_text:
                    score += 50
            
            if score > best_score and score > 50:  # Minimum threshold
                best_match = (i, payment, score)
                best_score = score
        
        if best_match:
            matches.append({
                'payroll': payroll,
                'payment': best_match[1],
                'match_score': best_match[2],
                'match_type': 'EXACT' if best_match[2] >= 100 else 'PROBABLE' if best_match[2] >= 75 else 'POSSIBLE'
            })
            # Remove matched payment from unmatched list
            unmatched_payments.pop(best_match[0])
        else:
            unmatched_payroll.append(payroll)
    
    return matches, unmatched_payroll, unmatched_payments

def analyze_employee_data(conn):
    """Analyze employee data to understand driver relationships."""
    cur = conn.cursor()
    
    # Get employee information
    cur.execute("""
        SELECT 
            employee_id, employee_number, full_name, first_name, last_name,
            position, is_chauffeur, status, hire_date, employment_status
        FROM employees 
        ORDER BY employee_id
    """)
    
    employees = cur.fetchall()
    
    # Get unique driver IDs from payroll
    cur.execute("""
        SELECT DISTINCT driver_id, COUNT(*) as pay_entries,
               SUM(gross_pay) as total_pay, MAX(pay_date) as last_pay
        FROM driver_payroll 
        WHERE year = 2012
        GROUP BY driver_id
        ORDER BY total_pay DESC
    """)
    
    payroll_drivers = cur.fetchall()
    
    cur.close()
    return employees, payroll_drivers

def main():
    conn = get_db_connection()
    
    try:
        print("👥 EMPLOYEE PAY TO PAYMENT MATCHING - 2012")
        print("=" * 50)
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Analyze employee data
        employees, payroll_drivers = analyze_employee_data(conn)
        
        print("👨‍💼 EMPLOYEE DATABASE ANALYSIS")
        print("==============================")
        print(f"Total employees in database: {len(employees)}")
        
        active_employees = [e for e in employees if e[7] and 'active' in str(e[7]).lower()]  # status field
        chauffeurs = [e for e in employees if e[6] == True]  # is_chauffeur field
        
        print(f"Active employees: {len(active_employees)}")
        print(f"Chauffeurs: {len(chauffeurs)}")
        print()
        
        print("💰 PAYROLL DRIVER ANALYSIS")
        print("=========================")
        print(f"Unique drivers in 2012 payroll: {len(payroll_drivers)}")
        
        if payroll_drivers:
            print(f"{'Driver ID':<12} {'Pay Entries':<12} {'Total Pay':<15} {'Last Pay Date':<15}")
            print("-" * 60)
            
            total_payroll_amount = Decimal('0')
            for driver_id, entries, total_pay, last_pay in payroll_drivers[:10]:  # Top 10
                total_pay_dec = Decimal(str(total_pay or 0))
                total_payroll_amount += total_pay_dec
                print(f"{driver_id:<12} {entries:<12} ${total_pay_dec:>13,.2f} {str(last_pay):<15}")
            
            if len(payroll_drivers) > 10:
                remaining_total = sum(Decimal(str(p[2] or 0)) for p in payroll_drivers[10:])
                total_payroll_amount += remaining_total
                print(f"... and {len(payroll_drivers) - 10} more drivers")
            
            print("-" * 60)
            print(f"TOTAL 2012 PAYROLL: ${total_payroll_amount:,.2f}")
        print()
        
        # Get payroll records
        payroll_records, monthly_summary = analyze_employee_payroll_2012(conn)
        
        print("📊 MONTHLY PAYROLL SUMMARY")
        print("=========================")
        print(f"{'Month':<8} {'Entries':<8} {'Gross Pay':<15} {'Net Pay':<15} {'Deductions':<15} {'Drivers':<8}")
        print("-" * 75)
        
        yearly_totals = {'entries': 0, 'gross': Decimal('0'), 'net': Decimal('0'), 'deductions': Decimal('0')}
        
        for month, entries, gross, net, deductions, drivers in monthly_summary:
            gross_dec = Decimal(str(gross or 0))
            net_dec = Decimal(str(net or 0))
            deduct_dec = Decimal(str(deductions or 0))
            
            yearly_totals['entries'] += entries
            yearly_totals['gross'] += gross_dec
            yearly_totals['net'] += net_dec
            yearly_totals['deductions'] += deduct_dec
            
            print(f"{month:<8} {entries:<8} ${gross_dec:>13,.2f} ${net_dec:>13,.2f} ${deduct_dec:>13,.2f} {drivers:<8}")
        
        print("-" * 75)
        print(f"{'TOTAL':<8} {yearly_totals['entries']:<8} ${yearly_totals['gross']:>13,.2f} "
              f"${yearly_totals['net']:>13,.2f} ${yearly_totals['deductions']:>13,.2f}")
        print()
        
        # Get cash payments
        cash_payments = get_cash_payment_records_2012(conn)
        
        print("💵 CASH PAYMENT RECORDS")
        print("======================")
        
        if cash_payments:
            cash_total = sum(Decimal(str(p[3])) for p in cash_payments)
            print(f"Total cash payments: {len(cash_payments)} records")
            print(f"Total cash amount: ${cash_total:,.2f}")
            print()
            
            print("Sample cash payments:")
            print(f"{'Date':<12} {'Amount':<12} {'Account':<12} {'Reserve#':<10} {'Method':<15}")
            print("-" * 65)
            
            for payment_date, account, reserve, amount, method, notes, client_id, payment_id in cash_payments[:10]:
                amount_dec = Decimal(str(amount))
                account_str = str(account or 'N/A')[:10]
                reserve_str = str(reserve or 'N/A')[:8]
                method_short = (method or 'N/A')[:13]
                print(f"{payment_date} ${amount_dec:>10.2f} {account_str:<12} {reserve_str:<10} {method_short}")
        
        print()
        
        # Match payroll to payments
        print("🔄 MATCHING PAYROLL TO CASH PAYMENTS")
        print("===================================")
        
        matches, unmatched_payroll, unmatched_payments = match_payroll_to_payments(payroll_records, cash_payments)
        
        print(f"Payroll records analyzed: {len(payroll_records)}")
        print(f"Cash payments analyzed: {len(cash_payments)}")
        print(f"Successful matches: {len(matches)}")
        print(f"Unmatched payroll: {len(unmatched_payroll)}")
        print(f"Unmatched cash payments: {len(unmatched_payments)}")
        print()
        
        if matches:
            print("💎 SUCCESSFUL MATCHES")
            print("====================")
            print(f"{'Pay Date':<12} {'Driver':<8} {'Pay Amount':<12} {'Cash Amount':<12} {'Match':<10} {'Score':<6}")
            print("-" * 70)
            
            matched_payroll_total = Decimal('0')
            matched_payment_total = Decimal('0')
            
            for match in matches[:15]:  # Show top 15 matches
                payroll = match['payroll']
                payment = match['payment']
                
                pay_date = payroll[6]
                driver_id = payroll[1]
                gross_pay = Decimal(str(payroll[7] or 0))
                net_pay = Decimal(str(payroll[12] or 0))
                
                payment_amount = Decimal(str(payment[3]))
                match_type = match['match_type']
                score = match['match_score']
                
                matched_payroll_total += gross_pay
                matched_payment_total += payment_amount
                
                print(f"{pay_date} {str(driver_id):<8} ${gross_pay:>10.2f} ${payment_amount:>10.2f} "
                      f"{match_type:<10} {score:<6.0f}")
            
            if len(matches) > 15:
                print(f"... and {len(matches) - 15} more matches")
            
            print("-" * 70)
            print(f"Matched payroll total: ${matched_payroll_total:,.2f}")
            print(f"Matched payment total: ${matched_payment_total:,.2f}")
            print(f"Match variance: ${matched_payment_total - matched_payroll_total:,.2f}")
        
        print()
        
        # Analyze unmatched records
        if unmatched_payroll:
            print("[WARN]  UNMATCHED PAYROLL RECORDS")
            print("============================")
            unmatched_pay_total = sum(Decimal(str(p[7] or 0)) for p in unmatched_payroll)
            print(f"Unmatched payroll amount: ${unmatched_pay_total:,.2f}")
            print(f"Unmatched payroll entries: {len(unmatched_payroll)}")
        
        if unmatched_payments:
            print()
            print("💸 UNMATCHED CASH PAYMENTS")
            print("=========================")
            unmatched_cash_total = sum(Decimal(str(p[3])) for p in unmatched_payments)
            print(f"Unmatched cash amount: ${unmatched_cash_total:,.2f}")
            print(f"Unmatched cash entries: {len(unmatched_payments)}")
            
            print("\nLargest unmatched cash payments:")
            sorted_unmatched = sorted(unmatched_payments, key=lambda x: float(x[3]), reverse=True)
            for payment_date, account, reserve, amount, method, notes, client_id, payment_id in sorted_unmatched[:10]:
                amount_dec = Decimal(str(amount))
                print(f"  {payment_date} ${amount_dec:>8.2f} - Account: {account}, Reserve: {reserve}")
        
        print()
        print("📋 RECONCILIATION ANALYSIS")
        print("=========================")
        
        total_payroll = yearly_totals['gross']
        total_cash_payments = sum(Decimal(str(p[3])) for p in cash_payments) if cash_payments else Decimal('0')
        
        print(f"Total 2012 Payroll (Gross): ${total_payroll:,.2f}")
        print(f"Total 2012 Cash Payments: ${total_cash_payments:,.2f}")
        print(f"Variance: ${total_cash_payments - total_payroll:,.2f}")
        
        if total_payroll > 0:
            cash_coverage = (total_cash_payments / total_payroll) * 100
            print(f"Cash Payment Coverage: {cash_coverage:.1f}% of payroll")
        
        print()
        print("🎯 RECOMMENDATIONS")
        print("==================")
        if len(matches) > 0:
            print(f"[OK] Successfully matched {len(matches)} payroll records to cash payments")
        
        if len(unmatched_payroll) > 0:
            print(f"[WARN]  {len(unmatched_payroll)} payroll records need cash payment documentation")
        
        if len(unmatched_payments) > 0:
            print(f"🔍 {len(unmatched_payments)} cash payments may not be employee pay")
            print("   - Review for other business expenses or revenue")
        
        if total_cash_payments > total_payroll * 2:
            print("[WARN]  Cash payments significantly exceed payroll - investigate non-payroll cash")
        
        print("📝 Consider creating formal employee pay vouchers for cash payments")
        print("🏛️  Ensure all employee cash payments have proper tax withholding documentation")
    
    except Exception as e:
        print(f"[FAIL] Error matching employee pay to payments: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())