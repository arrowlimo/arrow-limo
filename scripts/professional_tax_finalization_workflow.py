"""
Professional Tax Finalization Workflow

For professional accountants preparing corporate (T2/AT1) and personal tax returns.
This script:
1. Runs AI optimization analysis
2. Generates accountant's checklist with priority fixes
3. Exports all CRA-required data packages
4. Creates submission-ready reports
5. Validates data completeness

Usage: python professional_tax_finalization_workflow.py [year]
"""

import os
import sys
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import shutil

import pandas as pd
import psycopg2


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


class TaxFinalizationWorkflow:
    def __init__(self, year: int):
        self.year = year
        self.start_date = date(year, 1, 1)
        self.end_date = date(year, 12, 31)
        self.conn = get_conn()
        self.output_dir = Path(f"L:/limo/reports/tax_finalization_{year}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def step1_run_ai_optimizer(self):
        """Run AI tax optimization analysis."""
        print("\n" + "="*80)
        print("STEP 1: AI TAX OPTIMIZATION ANALYSIS")
        print("="*80 + "\n")
        
        script_path = Path("L:/limo/scripts/ai_year_end_tax_optimizer.py")
        if script_path.exists():
            print(f"Running AI optimizer for {self.year}...")
            result = subprocess.run(
                [sys.executable, str(script_path), str(self.year)],
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.stderr:
                print("Warnings:", result.stderr)
        else:
            print(f"⚠️ AI optimizer not found at {script_path}")
        
        print("\n✅ Step 1 Complete: Review tax_optimization_{}.csv for findings\n".format(self.year))
    
    def step2_generate_cra_reports(self):
        """Generate all CRA-required reports."""
        print("\n" + "="*80)
        print("STEP 2: GENERATE CRA AUDIT REPORTS PACKAGE")
        print("="*80 + "\n")
        
        script_path = Path("L:/limo/scripts/generate_cra_audit_reports.py")
        if script_path.exists():
            print(f"Generating comprehensive CRA reports for {self.year}...")
            result = subprocess.run(
                [sys.executable, str(script_path), str(self.year)],
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.stderr:
                print("Warnings:", result.stderr)
        else:
            print(f"⚠️ CRA report generator not found at {script_path}")
        
        print("\n✅ Step 2 Complete: CRA audit package generated\n")
    
    def step3_accountant_checklist(self):
        """Generate professional accountant's checklist."""
        print("\n" + "="*80)
        print("STEP 3: ACCOUNTANT'S PRE-FILING CHECKLIST")
        print("="*80 + "\n")
        
        checklist = []
        
        # Corporate Tax (T2/AT1) Checklist
        print("📋 CORPORATE TAX RETURN (T2 & AT1) CHECKLIST:\n")
        
        checklist.append({
            "category": "Corporate Tax",
            "item": "1. Financial Statements Finalized",
            "description": "Balance Sheet, Income Statement, Cash Flow Statement reconciled",
            "data_source": "Balance_Sheet.csv, Income_Statement.csv, Cash_Flow_Statement.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Corporate Tax",
            "item": "2. General Ledger Reviewed",
            "description": "All GL entries classified correctly, no suspense accounts",
            "data_source": "General_Ledger_Detail.csv, Trial_Balance.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Corporate Tax",
            "item": "3. GIFI Mapping Complete",
            "description": "Chart of accounts mapped to GIFI codes for T2",
            "data_source": "gifi_mapping_placeholder.txt (manual entry required)",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Corporate Tax",
            "item": "4. CCA Schedule Prepared",
            "description": "Capital Cost Allowance calculated for all asset classes",
            "data_source": "Asset_Register.csv + manual CCA calculation",
            "priority": "HIGH"
        })
        
        checklist.append({
            "category": "Corporate Tax",
            "item": "5. Accounts Receivable/Payable Confirmed",
            "description": "AR/AP aging accurate, bad debts written off",
            "data_source": "AR_Aging.csv, AP_Aging.csv",
            "priority": "HIGH"
        })
        
        # GST/HST Checklist
        print("📋 GST/HST FILING (GST34) CHECKLIST:\n")
        
        checklist.append({
            "category": "GST/HST",
            "item": "6. GST Collected Reconciled",
            "description": "GST on all taxable supplies calculated and recorded",
            "data_source": "GST_Collected_Detail.csv, GST34_Return.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "GST/HST",
            "item": "7. Input Tax Credits Verified",
            "description": "ITCs claimed only on eligible expenses with proper documentation",
            "data_source": "GST_ITC_Detail.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "GST/HST",
            "item": "8. GST Return Summary Balanced",
            "description": "GST collected - ITCs = Net GST due/refund",
            "data_source": "GST_Return_Summary.csv",
            "priority": "CRITICAL"
        })
        
        # Payroll Checklist
        print("📋 PAYROLL REMITTANCES (PD7A) CHECKLIST:\n")
        
        checklist.append({
            "category": "Payroll",
            "item": "9. Payroll Register Complete",
            "description": "All employee wages, CPP, EI, tax deductions recorded",
            "data_source": "Payroll_Register.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Payroll",
            "item": "10. T4 Slips Prepared",
            "description": "T4 boxes 14, 16, 18, 22, 24, 26 calculated per employee",
            "data_source": "T4_Summary.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Payroll",
            "item": "11. Remittances Reconciled",
            "description": "PD7A remittances match payroll deductions",
            "data_source": "PD7A_Remittance.csv, Remittance_Summary.csv",
            "priority": "HIGH"
        })
        
        checklist.append({
            "category": "Payroll",
            "item": "12. T4A for Contractors",
            "description": "Contractor payments >$500 reported on T4A",
            "data_source": "t4a_placeholder.txt (check Expense_Ledger.csv)",
            "priority": "MEDIUM"
        })
        
        # Banking & Reconciliation
        print("📋 BANKING & RECONCILIATION CHECKLIST:\n")
        
        checklist.append({
            "category": "Banking",
            "item": "13. Bank Reconciliation Complete",
            "description": "All bank accounts reconciled to Dec 31",
            "data_source": "Bank_Reconciliation.csv",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Banking",
            "item": "14. Credit Card Reconciliation",
            "description": "All business credit card expenses matched to receipts",
            "data_source": "Credit_Card_Recon.csv",
            "priority": "HIGH"
        })
        
        checklist.append({
            "category": "Banking",
            "item": "15. Cash Reconciliation",
            "description": "Petty cash and cash receipts accounted for",
            "data_source": "Cash_Recon.csv, Petty_Cash_Log.csv",
            "priority": "MEDIUM"
        })
        
        # Supporting Documentation
        print("📋 SUPPORTING DOCUMENTATION CHECKLIST:\n")
        
        checklist.append({
            "category": "Documentation",
            "item": "16. Vehicle Logs",
            "description": "Mileage logs for business use percentage",
            "data_source": "Vehicle_Expense_Log.csv",
            "priority": "HIGH"
        })
        
        checklist.append({
            "category": "Documentation",
            "item": "17. Receipt Backup",
            "description": "All receipts scanned/filed, no missing documentation",
            "data_source": "Review Expense_Ledger.csv for completeness",
            "priority": "HIGH"
        })
        
        checklist.append({
            "category": "Documentation",
            "item": "18. Notes to Financial Statements",
            "description": "Significant accounting policies, contingencies disclosed",
            "data_source": "notes_to_financial_statements.txt",
            "priority": "MEDIUM"
        })
        
        # Alberta-Specific
        print("📋 ALBERTA CORPORATE REGISTRY:\n")
        
        checklist.append({
            "category": "Alberta Registry",
            "item": "19. REG3062 Annual Return",
            "description": "Corporate registry annual filing (directors, shares, address)",
            "data_source": "reg3062_alberta_registry_placeholder.txt",
            "priority": "HIGH"
        })
        
        # Personal Tax (if owner-manager)
        print("📋 PERSONAL TAX RETURN (OWNER-MANAGER):\n")
        
        checklist.append({
            "category": "Personal Tax",
            "item": "20. T4 from Corporation",
            "description": "Owner's T4 employment income from corporation",
            "data_source": "T4_Summary.csv (owner's record)",
            "priority": "CRITICAL"
        })
        
        checklist.append({
            "category": "Personal Tax",
            "item": "21. Dividends Declared",
            "description": "T5 for dividends paid to shareholders",
            "data_source": "Manual review - not in current system",
            "priority": "HIGH"
        })
        
        checklist.append({
            "category": "Personal Tax",
            "item": "22. Shareholder Loans",
            "description": "Review shareholder loan account, section 15(2) implications",
            "data_source": "Balance_Sheet.csv (Due to/from shareholders)",
            "priority": "HIGH"
        })
        
        # Save checklist
        df_checklist = pd.DataFrame(checklist)
        checklist_path = self.output_dir / "accountant_pre_filing_checklist.csv"
        df_checklist.to_csv(checklist_path, index=False)
        
        # Print checklist
        for i, item in enumerate(checklist, 1):
            print(f"\n[{item['priority']}] {item['item']}")
            print(f"    {item['description']}")
            print(f"    📁 Data: {item['data_source']}")
        
        print(f"\n✅ Step 3 Complete: Checklist saved to {checklist_path}\n")
    
    def step4_data_validation(self):
        """Validate data completeness and accuracy."""
        print("\n" + "="*80)
        print("STEP 4: DATA VALIDATION & QUALITY CHECKS")
        print("="*80 + "\n")
        
        issues = []
        
        cur = self.conn.cursor()
        
        # Check 1: Orphan payments
        cur.execute("""
            SELECT COUNT(*) 
            FROM payments p
            LEFT JOIN charters c ON c.reserve_number = p.reserve_number
            WHERE p.payment_date BETWEEN %s AND %s
              AND c.charter_id IS NULL
        """, (self.start_date, self.end_date))
        orphan_count = cur.fetchone()[0]
        if orphan_count > 0:
            issues.append(f"⚠️ {orphan_count} payments without matching charters (orphan payments)")
        
        # Check 2: Negative balances
        cur.execute("""
            SELECT COUNT(*)
            FROM charters c
            LEFT JOIN (
                SELECT reserve_number, SUM(amount) as total_paid
                FROM payments
                GROUP BY reserve_number
            ) p ON p.reserve_number = c.reserve_number
            WHERE c.charter_date BETWEEN %s AND %s
              AND COALESCE(p.total_paid, 0) > c.total_amount_due
        """, (self.start_date, self.end_date))
        overpaid_count = cur.fetchone()[0]
        if overpaid_count > 0:
            issues.append(f"⚠️ {overpaid_count} charters with overpayments (negative balances)")
        
        # Check 3: Missing expense accounts
        cur.execute("""
            SELECT COUNT(*)
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (expense_account IS NULL OR expense_account = '' OR expense_account = 'UNKNOWN')
              AND amount > 0
        """, (self.start_date, self.end_date))
        unclassified_count = cur.fetchone()[0]
        if unclassified_count > 0:
            issues.append(f"⚠️ {unclassified_count} receipts without expense account classification")
        
        # Check 4: Missing GST on charters
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE charter_date BETWEEN %s AND %s
              AND (gst_amount IS NULL OR gst_amount = 0)
              AND total_amount_due > 0
              AND status != 'cancelled'
        """, (self.start_date, self.end_date))
        missing_gst_count = cur.fetchone()[0]
        if missing_gst_count > 0:
            issues.append(f"⚠️ {missing_gst_count} charters missing GST calculation")
        
        # Check 5: Future-dated transactions
        cur.execute("""
            SELECT COUNT(*)
            FROM receipts
            WHERE receipt_date > CURRENT_DATE
        """)
        future_receipts = cur.fetchone()[0]
        if future_receipts > 0:
            issues.append(f"⚠️ {future_receipts} receipts with future dates (data entry error)")
        
        # Check 6: Payroll without T4 boxes
        cur.execute("""
            SELECT COUNT(*)
            FROM driver_payroll
            WHERE pay_date BETWEEN %s AND %s
              AND (t4_box_14_employment_income IS NULL OR t4_box_14_employment_income = 0)
              AND gross_pay > 0
        """, (self.start_date, self.end_date))
        missing_t4_count = cur.fetchone()[0]
        if missing_t4_count > 0:
            issues.append(f"⚠️ {missing_t4_count} payroll entries missing T4 box calculations")
        
        cur.close()
        
        if issues:
            print("🔴 DATA QUALITY ISSUES FOUND:\n")
            for issue in issues:
                print(f"  {issue}")
            print("\n⚠️ RESOLVE THESE BEFORE FILING")
        else:
            print("✅ NO CRITICAL DATA ISSUES FOUND")
        
        # Save validation report
        validation_report = self.output_dir / "data_validation_report.txt"
        with open(validation_report, "w") as f:
            f.write(f"DATA VALIDATION REPORT - {self.year}\n")
            f.write("="*80 + "\n\n")
            if issues:
                f.write("ISSUES FOUND:\n\n")
                for issue in issues:
                    f.write(f"{issue}\n")
            else:
                f.write("✅ All validation checks passed\n")
        
        print(f"\n✅ Step 4 Complete: Validation report saved\n")
    
    def step5_export_packages(self):
        """Create organized export packages for accountant."""
        print("\n" + "="*80)
        print("STEP 5: EXPORT CRA FILING PACKAGES")
        print("="*80 + "\n")
        
        # Create organized folder structure
        cra_reports_dir = Path(f"L:/limo/reports/cra_audit_{self.year}")
        
        packages = {
            "T2_Corporate_Tax": [
                "Balance_Sheet.csv",
                "Income_Statement.csv",
                "Trial_Balance.csv",
                "General_Ledger_Detail.csv",
                "gifi_mapping_placeholder.txt",
                "Asset_Register.csv",
                "notes_to_financial_statements.txt",
            ],
            "AT1_Alberta_Tax": [
                "at1_alberta_tax_placeholder.txt",
                "Income_Statement.csv",
                "Balance_Sheet.csv",
            ],
            "GST34_Return": [
                "GST34_Return.csv",
                "GST_Return_Summary.csv",
                "GST_Collected_Detail.csv",
                "GST_ITC_Detail.csv",
                "gst34_return_placeholder.txt",
            ],
            "PD7A_Payroll_Remittance": [
                "PD7A_Remittance.csv",
                "Remittance_Summary.csv",
                "Payroll_Register.csv",
                "pd7a_remittance_placeholder.txt",
            ],
            "T4_T4A_Slips": [
                "T4_Summary.csv",
                "Payroll_Register.csv",
                "t4a_placeholder.txt",
            ],
            "Supporting_Documents": [
                "Bank_Reconciliation.csv",
                "AR_Aging.csv",
                "AP_Aging.csv",
                "Sales_Ledger.csv",
                "Expense_Ledger.csv",
                "Vehicle_Expense_Log.csv",
                "Cash_Flow_Statement.csv",
            ],
            "Alberta_Registry": [
                "reg3062_alberta_registry_placeholder.txt",
            ],
        }
        
        print("📦 Creating organized filing packages...\n")
        
        for package_name, files in packages.items():
            package_dir = self.output_dir / package_name
            package_dir.mkdir(exist_ok=True)
            
            copied_count = 0
            for filename in files:
                source = cra_reports_dir / filename
                if source.exists():
                    dest = package_dir / filename
                    shutil.copy2(source, dest)
                    copied_count += 1
            
            print(f"✅ {package_name}: {copied_count}/{len(files)} files")
        
        # Create master index
        index_path = self.output_dir / "FILING_PACKAGE_INDEX.txt"
        with open(index_path, "w") as f:
            f.write(f"CRA TAX FILING PACKAGES - {self.year}\n")
            f.write("="*80 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("FILING DEADLINES:\n")
            f.write(f"  T2 Corporate Tax: 6 months after year-end\n")
            f.write(f"  GST34 Return: Due 1 month after period end (check filing frequency)\n")
            f.write(f"  PD7A Remittance: Due 15th of month following pay period\n")
            f.write(f"  T4/T4A Slips: Last day of February {self.year + 1}\n")
            f.write(f"  REG3062 Alberta: Within 60 days of anniversary date\n\n")
            
            f.write("PACKAGE CONTENTS:\n\n")
            for package_name, files in packages.items():
                f.write(f"{package_name}:\n")
                for filename in files:
                    f.write(f"  - {filename}\n")
                f.write("\n")
            
            f.write("\nNOTE: Review AI optimization report (tax_optimization_{}.csv) for savings opportunities.\n".format(self.year))
        
        print(f"\n📋 Master index created: {index_path}")
        print(f"\n✅ Step 5 Complete: All packages exported to {self.output_dir}\n")
    
    def step6_final_summary(self):
        """Generate executive summary for accountant."""
        print("\n" + "="*80)
        print("STEP 6: EXECUTIVE SUMMARY & CRA BALANCE")
        print("="*80 + "\n")
        
        cur = self.conn.cursor()
        
        # Key financial metrics
        cur.execute("""
            SELECT 
                COUNT(*) as charter_count,
                SUM(total_amount_due) as total_revenue,
                SUM(COALESCE(gst_amount, total_amount_due * 0.05 / 1.05)) as gst_collected
            FROM charters
            WHERE charter_date BETWEEN %s AND %s
              AND status != 'cancelled'
        """, (self.start_date, self.end_date))
        charter_row = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as receipt_count,
                SUM(amount) as total_expenses,
                SUM(COALESCE(gst_amount, 0)) as gst_itcs
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
        """, (self.start_date, self.end_date))
        receipt_row = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(DISTINCT employee_id) as employee_count,
                SUM(gross_pay) as total_wages,
                SUM(COALESCE(cpp_employee, 0) + COALESCE(cpp_employer, 0)) as total_cpp,
                SUM(COALESCE(ei_employee, 0) + COALESCE(ei_employer, 0)) as total_ei,
                SUM(COALESCE(income_tax, 0)) as total_tax
            FROM driver_payroll
            WHERE pay_date BETWEEN %s AND %s
        """, (self.start_date, self.end_date))
        payroll_row = cur.fetchone()
        
        # Get actual remittances paid to CRA
        cur.execute("""
            SELECT SUM(amount) as total_remitted
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (vendor_name ILIKE '%%CRA%%' OR vendor_name ILIKE '%%receiver general%%'
                   OR expense_account ILIKE '%%payroll remittance%%'
                   OR expense_account ILIKE '%%source deduction%%')
        """, (self.start_date, self.end_date))
        remittance_row = cur.fetchone()
        
        # Get GST remittances paid
        cur.execute("""
            SELECT SUM(amount) as gst_remitted
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (vendor_name ILIKE '%%GST%%remit%%' OR vendor_name ILIKE '%%HST%%remit%%'
                   OR expense_account ILIKE '%%gst%%remit%%' OR expense_account ILIKE '%%hst%%remit%%'
                   OR description ILIKE '%%gst%%return%%')
        """, (self.start_date, self.end_date))
        gst_remit_row = cur.fetchone()
        
        cur.close()
        
        # Calculate CRA balances
        gst_collected = Decimal(charter_row[2] or 0)
        gst_itcs = Decimal(receipt_row[2] or 0)
        net_gst = gst_collected - gst_itcs
        gst_remitted = Decimal(gst_remit_row[0] or 0) if gst_remit_row else Decimal("0")
        gst_balance = net_gst - gst_remitted
        
        payroll_cpp = Decimal(payroll_row[2] or 0)
        payroll_ei = Decimal(payroll_row[3] or 0)
        payroll_tax = Decimal(payroll_row[4] or 0)
        payroll_due = payroll_cpp + payroll_ei + payroll_tax
        payroll_remitted = Decimal(remittance_row[0] or 0) if remittance_row else Decimal("0")
        payroll_balance = payroll_due - payroll_remitted
        
        gross_revenue = Decimal(charter_row[1] or 0)
        total_expenses = Decimal(receipt_row[1] or 0)
        net_income = gross_revenue - total_expenses
        
        # Estimate corporate tax (simplified: 11.5% federal small business rate + 8% Alberta = 19.5% on first $500K)
        corporate_tax_rate = Decimal("0.195")  # Combined federal + Alberta small business rate
        estimated_corporate_tax = net_income * corporate_tax_rate if net_income > 0 else Decimal("0")
        
        # Total CRA position
        total_cra_balance = gst_balance + payroll_balance + estimated_corporate_tax
        
        # Print summary
        summary_lines = []
        summary_lines.append(f"PROFESSIONAL TAX FINALIZATION SUMMARY - {self.year}")
        summary_lines.append("="*80)
        summary_lines.append("")
        summary_lines.append("REVENUE & SALES:")
        summary_lines.append(f"  Total Charters: {charter_row[0]:,}")
        summary_lines.append(f"  Gross Revenue: ${gross_revenue:,.2f}")
        summary_lines.append(f"  GST Collected: ${gst_collected:,.2f}")
        summary_lines.append("")
        summary_lines.append("EXPENSES:")
        summary_lines.append(f"  Total Receipts: {receipt_row[0]:,}")
        summary_lines.append(f"  Total Expenses: ${total_expenses:,.2f}")
        summary_lines.append(f"  Input Tax Credits: ${gst_itcs:,.2f}")
        summary_lines.append("")
        summary_lines.append(f"NET INCOME (Before Tax): ${net_income:,.2f}")
        summary_lines.append("")
        summary_lines.append("="*80)
        summary_lines.append("CRA BALANCE SUMMARY (WHAT YOU OWE/REFUND)")
        summary_lines.append("="*80)
        summary_lines.append("")
        summary_lines.append("1. GST/HST POSITION:")
        summary_lines.append(f"   GST Collected:        ${gst_collected:>15,.2f}")
        summary_lines.append(f"   Less: ITCs Claimed:   ${gst_itcs:>15,.2f}")
        summary_lines.append(f"   Net GST Due:          ${net_gst:>15,.2f}")
        summary_lines.append(f"   Less: Remitted:       ${gst_remitted:>15,.2f}")
        summary_lines.append(f"   " + ("-" * 50))
        if gst_balance > 0:
            summary_lines.append(f"   GST OWING:            ${gst_balance:>15,.2f} ❌")
        elif gst_balance < 0:
            summary_lines.append(f"   GST REFUND:           ${abs(gst_balance):>15,.2f} ✅")
        else:
            summary_lines.append(f"   GST BALANCE:          ${gst_balance:>15,.2f} ✅ (Balanced)")
        summary_lines.append("")
        summary_lines.append("2. PAYROLL REMITTANCES (PD7A):")
        summary_lines.append(f"   CPP (Employee+Employer): ${payroll_cpp:>12,.2f}")
        summary_lines.append(f"   EI (Employee+Employer):  ${payroll_ei:>12,.2f}")
        summary_lines.append(f"   Income Tax Withheld:     ${payroll_tax:>12,.2f}")
        summary_lines.append(f"   Total Due:               ${payroll_due:>12,.2f}")
        summary_lines.append(f"   Less: Remitted:          ${payroll_remitted:>12,.2f}")
        summary_lines.append(f"   " + ("-" * 50))
        if payroll_balance > 0:
            summary_lines.append(f"   PAYROLL OWING:           ${payroll_balance:>12,.2f} ❌")
        elif payroll_balance < 0: & CRA balance")
        print("\n✅ REFRESHABLE: Re-run anytime after making fixes")
        print("   All reports regenerate with current data")
        print("\n" + "="*80 + "\n")
        
        input("Press ENTER to begin workflow (or Ctrl+C to cancel)L BALANCE:         ${payroll_balance:>12,.2f} ✅ (Balanced)")
        summary_lines.append("")
        summary_lines.append("3. CORPORATE TAX (T2 + AT1 ESTIMATE):")
        summary_lines.append(f"   Net Income:              ${net_income:>12,.2f}")
        summary_lines.append(f"   Tax Rate (Est.):         {corporate_tax_rate * 100:.1f}%")
        summary_lines.append(f"   " + ("-" * 50))
        summary_lines.append(f"   ESTIMATED TAX OWING:     ${estimated_corporate_tax:>12,.2f}")
        summary_lines.append("   (Federal 11.5% + Alberta 8% small business rate)")
        summary_lines.append("   Note: Actual may differ after CCA, dividends, other adjustments")
        summary_lines.append("")
        summary_lines.append("="*80)
        summary_lines.append("TOTAL CRA POSITION:")
        summary_lines.append("="*80)
        if total_cra_balance > 0:
            summary_lines.append(f"TOTAL ESTIMATED AMOUNT OWING TO CRA: ${total_cra_balance:,.2f} ❌")
        elif total_cra_balance < 0:
            summary_lines.append(f"TOTAL ESTIMATED REFUND FROM CRA: ${abs(total_cra_balance):,.2f} ✅")
        else:
            summary_lines.append(f"TOTAL CRA BALANCE: ${total_cra_balance:,.2f} ✅ (Balanced)")
        summary_lines.append("")
        summary_lines.append("BREAKDOWN:")
        summary_lines.append(f"  GST/HST:          ${gst_balance:>15,.2f}")
        summary_lines.append(f"  Payroll:          ${payroll_balance:>15,.2f}")
        summary_lines.append(f"  Corporate Tax:    ${estimated_corporate_tax:>15,.2f}")
        summary_lines.append("="*80)
        summary_lines.append("")
        summary_lines.append("PAYROLL SUMMARY:")
        summary_lines.append(f"  Employees: {payroll_row[0]}")
        summary_lines.append(f"  Gross Wages: ${Decimal(payroll_row[1] or 0):,.2f}")
        summary_lines.append("")
        
        summary_lines.append("ACCOUNTANT ACTION ITEMS:")
        summary_lines.append("  1. Review AI optimization report for tax savings opportunities")
        summary_lines.append("  2. Complete pre-filing checklist (accountant_pre_filing_checklist.csv)")
        summary_lines.append("  3. Resolve data validation issues (data_validation_report.txt)")
        summary_lines.append("  4. File T2/AT1 using exported financial statements")
        summary_lines.append("  5. File GST34 using GST return summary")
        summary_lines.append("  6. Submit T4 slips by February 28")
        summary_lines.append("  7. File REG3062 annual return with Alberta registry")
        summary_lines.append("")
        summary_lines.append(f"All filing packages exported to: {self.output_dir}")
        summary_lines.append("="*80)
        
        summary_text = "\n".join(summary_lines)
        print(summary_text)
        
        # Save summary
        summary_path = self.output_dir / "EXECUTIVE_SUMMARY.txt"
        with open(summary_path, "w") as f:
            f.write(summary_text)
        
        print(f"\n✅ Step 6 Complete: Summary saved to {summary_path}\n")
    
    def run_complete_workflow(self):
        """Execute full tax finalization workflow."""
        print("\n" + "="*80)
        print(f"PROFESSIONAL TAX FINALIZATION WORKFLOW - {self.year}")
        print("="*80)
        print("\nThis workflow will:")
        print("  1. Run AI tax optimization analysis")
        print("  2. Generate all CRA-required reports")
        print("  3. Create accountant's pre-filing checklist")
        print("  4. Validate data quality")
        print("  5. Export organized filing packages")
        print("  6. Generate executive summary")
        print("\n" + "="*80 + "\n")
        
        input("Press ENTER to begin workflow...")
        
        self.step1_run_ai_optimizer()
        self.step2_generate_cra_reports()
        self.step3_accountant_checklist()
        self.step4_data_validation()
        self.step5_export_packages()
        self.step6_final_summary()
        
        print("\n" + "="*80)
        print("🎉 TAX FINALIZATION WORKFLOW COMPLETE!")
        print("="*80)
        print(f"\n📁 All reports exported to: {self.output_dir}")
        print("\n📋 NEXT STEPS:")
        print("  1. Review EXECUTIVE_SUMMARY.txt")
        print("  2. Review tax_optimization_{}.csv for savings".format(self.year))
        print("  3. Work through accountant_pre_filing_checklist.csv")
        print("  4. Fix issues in data_validation_report.txt")
        print("  5. Use filing packages in subdirectories for CRA submission")
        print("\n" + "="*80 + "\n")
        
        self.conn.close()


def main():
    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    else:
        year = datetime.now().year - 1  # Default to last year
    
    workflow = TaxFinalizationWorkflow(year)
    workflow.run_complete_workflow()


if __name__ == "__main__":
    main()
