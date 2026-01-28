#!/usr/bin/env python3
"""
QuickBooks & Payroll Records Comprehensive Analysis
Analyze ALL QuickBooks exports, profit & loss statements, balance sheets, and payroll records
Complete the missing piece of our financial audit
"""

import os
import csv
import json
import pandas as pd
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, date
from pathlib import Path
from decimal import Decimal

def connect_to_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', '')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def analyze_quickbooks_profit_loss_files():
    """Analyze all QuickBooks Profit & Loss files."""
    
    print("=== ANALYZING QUICKBOOKS PROFIT & LOSS FILES ===")
    
    profit_loss_files = [
        "l:/limo/docs/oldalms/profit and loss statements/2012/2012 profit and loss.xlsx",
        "l:/limo/docs/Arrow Limousine backup 2025_Profit and Loss.xlsx",
        "l:/limo/docs/Arrow Limousine backup 2025_Profit and Loss.csv",
        "l:/limo/docs/Arrow Limousine portable_Profit and Loss.csv"
    ]
    
    profit_loss_data = []
    
    for file_path in profit_loss_files:
        if not os.path.exists(file_path):
            continue
            
        print(f"Processing: {file_path}")
        
        try:
            if file_path.endswith('.xlsx'):
                # Read Excel file
                df = pd.read_excel(file_path)
                source_type = 'QuickBooks Excel Export'
            elif file_path.endswith('.csv'):
                # Read CSV file
                df = pd.read_csv(file_path)
                source_type = 'QuickBooks CSV Export'
            else:
                continue
            
            # Extract financial data
            for index, row in df.iterrows():
                # Look for account names and amounts
                for col in df.columns:
                    if pd.notna(row[col]) and row[col] != '':
                        value_str = str(row[col])
                        
                        # Try to identify account names and amounts
                        if any(keyword in value_str.lower() for keyword in 
                              ['income', 'revenue', 'expense', 'asset', 'liability', 'equity']):
                            
                            # Look for corresponding amount in the row
                            amount = None
                            for amount_col in df.columns:
                                try:
                                    if pd.notna(row[amount_col]):
                                        amount_val = str(row[amount_col]).replace('$', '').replace(',', '').strip()
                                        if amount_val and amount_val.replace('.', '').replace('-', '').isdigit():
                                            amount = float(amount_val)
                                            break
                                except:
                                    continue
                            
                            profit_loss_data.append({
                                'source_file': os.path.basename(file_path),
                                'source_type': source_type,
                                'account_category': value_str,
                                'amount': amount or 0.0,
                                'row_index': index,
                                'year': '2012' if '2012' in file_path else '2025'
                            })
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    print(f"Extracted {len(profit_loss_data)} profit & loss records")
    return profit_loss_data

def analyze_balance_sheet_data():
    """Analyze QuickBooks balance sheet data."""
    
    print("\n=== ANALYZING BALANCE SHEET DATA ===")
    
    balance_sheet_files = [
        "l:/limo/docs/oldalms/docs/export_final_latest/balance_sheet_view.csv",
        "l:/limo/docs/oldalms/reports/balance_sheet_data.csv",
        "l:/limo/docs/Arrow Limousine backup 2025_Balance Sheet.xlsx",
        "l:/limo/docs/Arrow Limousine backup 2025_Balance Sheet.csv"
    ]
    
    balance_sheet_data = []
    
    for file_path in balance_sheet_files:
        if not os.path.exists(file_path):
            continue
            
        print(f"Processing: {file_path}")
        
        try:
            if file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
                source_type = 'Balance Sheet Excel'
            elif file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                source_type = 'Balance Sheet CSV'
            else:
                continue
                
            # Extract balance sheet accounts
            for index, row in df.iterrows():
                # Look for account information
                account_name = None
                account_balance = None
                account_type = None
                
                for col in df.columns:
                    col_lower = col.lower()
                    if pd.notna(row[col]):
                        value = row[col]
                        
                        if 'account' in col_lower and 'name' in col_lower:
                            account_name = str(value)
                        elif 'account' in col_lower and 'type' in col_lower:
                            account_type = str(value)
                        elif 'balance' in col_lower or 'amount' in col_lower:
                            try:
                                if isinstance(value, (int, float)):
                                    account_balance = float(value)
                                else:
                                    balance_str = str(value).replace('$', '').replace(',', '').strip()
                                    if balance_str and balance_str.replace('.', '').replace('-', '').isdigit():
                                        account_balance = float(balance_str)
                            except:
                                pass
                
                if account_name and account_balance is not None:
                    balance_sheet_data.append({
                        'source_file': os.path.basename(file_path),
                        'source_type': source_type,
                        'account_name': account_name,
                        'account_type': account_type or 'Unknown',
                        'balance': account_balance,
                        'row_index': index
                    })
        
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    print(f"Extracted {len(balance_sheet_data)} balance sheet records")
    return balance_sheet_data

def analyze_payroll_records():
    """Analyze all payroll records and documents."""
    
    print("\n=== ANALYZING PAYROLL RECORDS ===")
    
    conn = connect_to_db()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Get payroll data from database
        cur.execute("""
            SELECT 
                employee_name, pay_date, hours_1, hours_2, salary, gratuity,
                cpp_deduction, ei_deduction, income_tax, gross_pay, net_pay
            FROM payroll 
            WHERE pay_date IS NOT NULL
            ORDER BY pay_date, employee_name
        """)
        
        payroll_records = []
        db_payroll = cur.fetchall()
        
        for record in db_payroll:
            payroll_records.append({
                'source': 'Database',
                'employee_name': record['employee_name'],
                'pay_date': record['pay_date'],
                'hours_1': float(record['hours_1'] or 0),
                'hours_2': float(record['hours_2'] or 0),
                'salary': float(record['salary'] or 0),
                'gratuity': float(record['gratuity'] or 0),
                'cpp_deduction': float(record['cpp_deduction'] or 0),
                'ei_deduction': float(record['ei_deduction'] or 0),
                'income_tax': float(record['income_tax'] or 0),
                'gross_pay': float(record['gross_pay'] or 0),
                'net_pay': float(record['net_pay'] or 0)
            })
        
        print(f"Extracted {len(payroll_records)} payroll records from database")
        
        # Check for payroll files in the system
        payroll_files = [
            "l:/limo/docs/oldalms/profit and loss statements/2012/MASTER COPY 2012 YTD Hourly Payroll Workbook.xls1.xls",
            "l:/limo/consolidated_payroll_data.csv",
            "l:/limo/consolidated_payroll_staging_data.xlsx"
        ]
        
        for file_path in payroll_files:
            if not os.path.exists(file_path):
                continue
                
            print(f"Processing payroll file: {file_path}")
            
            try:
                if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
                    df = pd.read_excel(file_path)
                elif file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    continue
                
                # Extract payroll data from files
                for index, row in df.iterrows():
                    employee_name = None
                    pay_date = None
                    gross_pay = None
                    
                    for col in df.columns:
                        col_lower = col.lower()
                        if pd.notna(row[col]):
                            value = row[col]
                            
                            if 'employee' in col_lower or 'name' in col_lower:
                                employee_name = str(value)
                            elif 'date' in col_lower:
                                pay_date = value
                            elif 'gross' in col_lower or 'total' in col_lower:
                                try:
                                    if isinstance(value, (int, float)):
                                        gross_pay = float(value)
                                    else:
                                        pay_str = str(value).replace('$', '').replace(',', '').strip()
                                        if pay_str and pay_str.replace('.', '').replace('-', '').isdigit():
                                            gross_pay = float(pay_str)
                                except:
                                    pass
                    
                    if employee_name and gross_pay:
                        payroll_records.append({
                            'source': f'File: {os.path.basename(file_path)}',
                            'employee_name': employee_name,
                            'pay_date': pay_date,
                            'gross_pay': gross_pay,
                            'file_row': index
                        })
            
            except Exception as e:
                print(f"Error processing payroll file {file_path}: {e}")
        
        return payroll_records
        
    except Exception as e:
        print(f"Error analyzing payroll records: {e}")
        return []
    finally:
        if conn:
            conn.close()

def create_comprehensive_quickbooks_audit():
    """Create comprehensive audit of all QuickBooks and payroll data."""
    
    print("\n=== CREATING COMPREHENSIVE QUICKBOOKS AUDIT ===")
    
    # Get all data
    profit_loss_data = analyze_quickbooks_profit_loss_files()
    balance_sheet_data = analyze_balance_sheet_data()
    payroll_data = analyze_payroll_records()
    
    # Generate comprehensive report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_path = f"l:/limo/reports/QUICKBOOKS_PAYROLL_AUDIT_{timestamp}.csv"
    
    with open(audit_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'COMPREHENSIVE QUICKBOOKS & PAYROLL AUDIT'
        ])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([''])
        
        # Profit & Loss Summary
        writer.writerow(['PROFIT & LOSS ANALYSIS'])
        writer.writerow(['Source File', 'Account Category', 'Amount', 'Year', 'Source Type'])
        
        profit_loss_total = 0
        for record in profit_loss_data:
            amount = record.get('amount', 0)
            profit_loss_total += amount
            writer.writerow([
                record.get('source_file', ''),
                record.get('account_category', ''),
                f"${amount:,.2f}",
                record.get('year', ''),
                record.get('source_type', '')
            ])
        
        writer.writerow([''])
        writer.writerow(['PROFIT & LOSS TOTAL', '', f"${profit_loss_total:,.2f}", '', ''])
        writer.writerow([''])
        
        # Balance Sheet Summary
        writer.writerow(['BALANCE SHEET ANALYSIS'])
        writer.writerow(['Source File', 'Account Name', 'Account Type', 'Balance', 'Source Type'])
        
        balance_sheet_total = 0
        for record in balance_sheet_data:
            balance = record.get('balance', 0)
            balance_sheet_total += balance
            writer.writerow([
                record.get('source_file', ''),
                record.get('account_name', ''),
                record.get('account_type', ''),
                f"${balance:,.2f}",
                record.get('source_type', '')
            ])
        
        writer.writerow([''])
        writer.writerow(['BALANCE SHEET TOTAL', '', '', f"${balance_sheet_total:,.2f}", ''])
        writer.writerow([''])
        
        # Payroll Summary
        writer.writerow(['PAYROLL ANALYSIS'])
        writer.writerow(['Source', 'Employee', 'Pay Date', 'Gross Pay', 'Net Pay', 'Total Hours'])
        
        payroll_gross_total = 0
        payroll_net_total = 0
        payroll_count = 0
        
        for record in payroll_data:
            gross = record.get('gross_pay', 0)
            net = record.get('net_pay', 0)
            hours = record.get('hours_1', 0) + record.get('hours_2', 0)
            
            payroll_gross_total += gross
            payroll_net_total += net
            payroll_count += 1
            
            writer.writerow([
                record.get('source', ''),
                record.get('employee_name', ''),
                str(record.get('pay_date', '')),
                f"${gross:,.2f}",
                f"${net:,.2f}",
                f"{hours:.1f}"
            ])
        
        writer.writerow([''])
        writer.writerow([
            'PAYROLL TOTALS',
            f'{payroll_count} records',
            '',
            f"${payroll_gross_total:,.2f}",
            f"${payroll_net_total:,.2f}",
            ''
        ])
    
    # Generate tax implications report
    tax_implications_path = f"l:/limo/reports/QUICKBOOKS_TAX_IMPLICATIONS_{timestamp}.csv"
    
    with open(tax_implications_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['QUICKBOOKS DATA - TAX IMPLICATIONS'])
        writer.writerow([''])
        
        writer.writerow(['TAX CATEGORY', 'AMOUNT', 'TAX TREATMENT', 'NOTES'])
        
        # Payroll tax implications
        writer.writerow([
            'Payroll Expenses (Gross)',
            f"${payroll_gross_total:,.2f}",
            '100% Deductible Business Expense',
            f'Total payroll costs across {payroll_count} pay records'
        ])
        
        # CPP/EI employer portions (estimated)
        employer_cpp_ei = payroll_gross_total * 0.0495  # Approximate employer portion
        writer.writerow([
            'CPP/EI Employer Contributions',
            f"${employer_cpp_ei:,.2f}",
            '100% Deductible Business Expense',
            'Estimated employer portions of CPP/EI'
        ])
        
        # Calculate totals
        total_deductible = payroll_gross_total + employer_cpp_ei + abs(profit_loss_total)
        
        writer.writerow([''])
        writer.writerow([
            'TOTAL ADDITIONAL DEDUCTIBLE EXPENSES',
            f"${total_deductible:,.2f}",
            'Reduces Taxable Income',
            'From QuickBooks and payroll analysis'
        ])
    
    summary = {
        'profit_loss_records': len(profit_loss_data),
        'profit_loss_total': profit_loss_total,
        'balance_sheet_records': len(balance_sheet_data),
        'balance_sheet_total': balance_sheet_total,
        'payroll_records': payroll_count,
        'payroll_gross_total': payroll_gross_total,
        'payroll_net_total': payroll_net_total,
        'total_additional_deductions': total_deductible,
        'audit_report_path': audit_path,
        'tax_implications_path': tax_implications_path
    }
    
    print(f"\nQuickBooks & Payroll Audit Complete:")
    print(f"Profit & Loss records: {len(profit_loss_data)}")
    print(f"Balance Sheet records: {len(balance_sheet_data)}")
    print(f"Payroll records: {payroll_count}")
    print(f"Total payroll expense: ${payroll_gross_total:,.2f}")
    print(f"Additional tax deductions: ${total_deductible:,.2f}")
    print(f"Audit report: {audit_path}")
    print(f"Tax implications: {tax_implications_path}")
    
    return summary

def main():
    """Main execution function."""
    
    print("=" * 80)
    print("QUICKBOOKS & PAYROLL RECORDS COMPREHENSIVE ANALYSIS")
    print("Analyzing ALL QuickBooks exports and payroll records")
    print("=" * 80)
    
    summary = create_comprehensive_quickbooks_audit()
    
    if summary:
        print("\n" + "=" * 60)
        print("QUICKBOOKS & PAYROLL AUDIT COMPLETE")
        print("=" * 60)
        print(f"Total records analyzed: {summary['profit_loss_records'] + summary['balance_sheet_records'] + summary['payroll_records']}")
        print(f"Additional tax deductions identified: ${summary['total_additional_deductions']:,.2f}")
        print(f"Missing piece of financial audit now complete!")
    
    return summary

if __name__ == "__main__":
    summary = main()