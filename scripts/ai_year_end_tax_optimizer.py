"""
AI Year-End CRA Audit & Tax Optimization Checker

One-click analysis to identify:
- Missing deductions and tax savings opportunities
- GST/HST optimization (unclaimed ITCs, collection gaps)
- Expense misclassifications
- Payroll remittance validation
- Capital Cost Allowance (CCA) opportunities
- Data completeness issues
- Audit risk flags
- Actionable recommendations with $ impact

Usage: python ai_year_end_tax_optimizer.py [year]
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from collections import defaultdict

import pandas as pd
import psycopg2


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

GST_RATE = Decimal("0.05")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


class TaxOptimizer:
    def __init__(self, year: int):
        self.year = year
        self.start_date = date(year, 1, 1)
        self.end_date = date(year, 12, 31)
        self.conn = get_conn()
        self.findings = []
        self.potential_savings = Decimal("0")
        
    def add_finding(self, category: str, severity: str, title: str, description: str, 
                    action: str, savings: Decimal = Decimal("0")):
        """Add a finding to the report."""
        self.findings.append({
            "category": category,
            "severity": severity,  # CRITICAL, HIGH, MEDIUM, LOW, INFO
            "title": title,
            "description": description,
            "action": action,
            "potential_savings": float(savings),
        })
        self.potential_savings += savings
    
    def check_missing_gst_itcs(self):
        """Check for receipts with missing GST amounts (unclaimed ITCs)."""
        print("🔍 Checking for missing GST Input Tax Credits...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as missing_count, 
                   SUM(amount) as total_amount
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (gst_amount IS NULL OR gst_amount = 0)
              AND amount > 0
              AND vendor_name NOT ILIKE '%%salary%%'
              AND vendor_name NOT ILIKE '%%payroll%%'
              AND vendor_name NOT ILIKE '%%wage%%'
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            missing_count = row[0]
            total_amount = to_decimal(row[1])
            # Estimate GST at 5% on tax-inclusive amount
            estimated_itc = total_amount * GST_RATE / (1 + GST_RATE)
            
            self.add_finding(
                category="GST/HST Optimization",
                severity="HIGH",
                title=f"{missing_count} receipts missing GST amounts",
                description=f"Found {missing_count} expense receipts (${total_amount:,.2f}) with no GST recorded. "
                           f"Estimated unclaimed ITCs: ${estimated_itc:,.2f}",
                action="Review receipts table, add gst_amount = amount * 0.05 / 1.05 for eligible expenses. "
                      "Exclude exempt items (salaries, rent on residential, insurance, bank fees).",
                savings=estimated_itc
            )
        
        cur.close()
    
    def check_uncollected_gst(self):
        """Check for charters with missing GST collection."""
        print("🔍 Checking for uncollected GST on charters...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as missing_count,
                   SUM(total_amount_due) as total_amount
            FROM charters
            WHERE charter_date BETWEEN %s AND %s
              AND (gst_amount IS NULL OR gst_amount = 0)
              AND total_amount_due > 0
              AND status != 'cancelled'
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            missing_count = row[0]
            total_amount = to_decimal(row[1])
            # Estimate GST at 5% on tax-inclusive amount
            estimated_gst = total_amount * GST_RATE / (1 + GST_RATE)
            
            self.add_finding(
                category="GST/HST Optimization",
                severity="CRITICAL",
                title=f"{missing_count} charters missing GST collection tracking",
                description=f"Found {missing_count} charters (${total_amount:,.2f}) with no GST recorded. "
                           f"Estimated GST collected but not tracked: ${estimated_gst:,.2f}",
                action="Update charters.gst_amount = total_amount_due * 0.05 / 1.05 for tax-inclusive pricing. "
                      "This doesn't increase what you owe (already collected), but ensures accurate GST reporting.",
                savings=Decimal("0")  # No savings, just compliance
            )
        
        cur.close()
    
    def check_vehicle_expenses(self):
        """Check vehicle expense optimization opportunities."""
        print("🔍 Analyzing vehicle expense deductions...")
        
        cur = self.conn.cursor()
        
        # Check for fuel receipts without vehicle assignment
        cur.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (vendor_name ILIKE '%%gas%%' OR vendor_name ILIKE '%%fuel%%' 
                   OR vendor_name ILIKE '%%petro%%' OR vendor_name ILIKE '%%shell%%'
                   OR vendor_name ILIKE '%%esso%%' OR vendor_name ILIKE '%%chevron%%')
              AND (vehicle_id IS NULL OR vehicle_id = 0)
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            count = row[0]
            total = to_decimal(row[1])
            
            self.add_finding(
                category="Vehicle Expenses",
                severity="MEDIUM",
                title=f"{count} fuel receipts not assigned to vehicles",
                description=f"Found ${total:,.2f} in fuel expenses without vehicle assignment. "
                           "Proper vehicle tracking supports CCA claims and business-use percentage.",
                action="Update receipts.vehicle_id for fuel purchases to track per-vehicle costs.",
                savings=Decimal("0")
            )
        
        # Check for maintenance without vehicle assignment
        cur.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (vendor_name ILIKE '%%repair%%' OR vendor_name ILIKE '%%maintenance%%'
                   OR vendor_name ILIKE '%%tire%%' OR vendor_name ILIKE '%%oil change%%'
                   OR vendor_name ILIKE '%%service%%' OR vendor_name ILIKE '%%auto%%')
              AND (vehicle_id IS NULL OR vehicle_id = 0)
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            count = row[0]
            total = to_decimal(row[1])
            
            self.add_finding(
                category="Vehicle Expenses",
                severity="MEDIUM",
                title=f"{count} maintenance receipts not assigned to vehicles",
                description=f"Found ${total:,.2f} in vehicle maintenance without vehicle assignment.",
                action="Update receipts.vehicle_id for maintenance expenses.",
                savings=Decimal("0")
            )
        
        cur.close()
    
    def check_cca_opportunities(self):
        """Check for Capital Cost Allowance opportunities."""
        print("🔍 Checking for CCA (depreciation) opportunities...")
        
        cur = self.conn.cursor()
        
        # Check for large equipment/vehicle purchases that could be CCA-eligible
        cur.execute("""
            SELECT vendor_name, amount, receipt_date, description
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND amount > 1000
              AND (vendor_name ILIKE '%%vehicle%%' OR vendor_name ILIKE '%%equipment%%'
                   OR vendor_name ILIKE '%%computer%%' OR vendor_name ILIKE '%%furniture%%'
                   OR description ILIKE '%%purchase%%' OR description ILIKE '%%equipment%%')
            ORDER BY amount DESC
            LIMIT 20
        """, (self.start_date, self.end_date))
        
        rows = cur.fetchall()
        if rows:
            total = sum(to_decimal(row[1]) for row in rows)
            count = len(rows)
            
            # Estimate tax savings from CCA (assuming 30% Class 10 for vehicles, 25% tax rate)
            # First year: half-year rule = 15% CCA
            estimated_cca = total * Decimal("0.15")
            tax_savings = estimated_cca * Decimal("0.25")
            
            self.add_finding(
                category="Capital Cost Allowance",
                severity="HIGH",
                title=f"{count} potential capital asset purchases found (${total:,.2f})",
                description=f"Found large purchases that may qualify for CCA deductions. "
                           f"Estimated first-year CCA: ${estimated_cca:,.2f} (15% half-year rule for vehicles). "
                           f"Estimated tax savings: ${tax_savings:,.2f}",
                action="Verify these are capitalized as assets, not expensed. Update chart_of_accounts with asset entries. "
                      "Claim CCA on T2: Class 10 (vehicles) 30%, Class 10.1 (luxury vehicles) 30%, Class 8 (equipment) 20%.",
                savings=tax_savings
            )
        
        cur.close()
    
    def check_meal_entertainment_limits(self):
        """Check meal and entertainment expense limits (50% deductible)."""
        print("🔍 Checking meal & entertainment expense limits...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT SUM(amount) as total, COUNT(*) as count
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (expense_account ILIKE '%%meal%%' OR expense_account ILIKE '%%food%%'
                   OR expense_account ILIKE '%%entertainment%%' OR expense_account ILIKE '%%restaurant%%'
                   OR vendor_name ILIKE '%%restaurant%%' OR vendor_name ILIKE '%%tim horton%%'
                   OR vendor_name ILIKE '%%starbucks%%' OR vendor_name ILIKE '%%mcdonald%%')
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[1] > 0:
            total = to_decimal(row[0])
            count = row[1]
            
            # Only 50% of meals/entertainment is deductible
            non_deductible = total * Decimal("0.50")
            
            self.add_finding(
                category="Expense Classification",
                severity="INFO",
                title=f"${total:,.2f} in meals/entertainment expenses ({count} receipts)",
                description=f"CRA allows only 50% deduction for meals and entertainment. "
                           f"Deductible: ${total * Decimal('0.50'):,.2f}, Non-deductible: ${non_deductible:,.2f}",
                action="Ensure these are coded to meal/entertainment accounts. No action needed if already classified correctly. "
                      "Your accountant will apply the 50% limitation on T2.",
                savings=Decimal("0")
            )
        
        cur.close()
    
    def check_payroll_remittance_accuracy(self):
        """Validate payroll remittances match payroll register."""
        print("🔍 Validating payroll remittance accuracy...")
        
        cur = self.conn.cursor()
        
        # Sum up payroll deductions from driver_payroll
        cur.execute("""
            SELECT 
                SUM(COALESCE(cpp_employee, 0)) as total_cpp_ee,
                SUM(COALESCE(cpp_employer, 0)) as total_cpp_er,
                SUM(COALESCE(ei_employee, 0)) as total_ei_ee,
                SUM(COALESCE(ei_employer, 0)) as total_ei_er,
                SUM(COALESCE(income_tax, 0)) as total_tax
            FROM driver_payroll
            WHERE pay_date BETWEEN %s AND %s
        """, (self.start_date, self.end_date))
        
        payroll_row = cur.fetchone()
        
        # Sum up actual remittances from receipts
        cur.execute("""
            SELECT SUM(amount) as total_remitted
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (vendor_name ILIKE '%%CRA%%' OR vendor_name ILIKE '%%receiver general%%'
                   OR expense_account ILIKE '%%payroll remittance%%')
        """, (self.start_date, self.end_date))
        
        remit_row = cur.fetchone()
        
        if payroll_row and payroll_row[0] is not None:
            cpp_ee = to_decimal(payroll_row[0])
            cpp_er = to_decimal(payroll_row[1])
            ei_ee = to_decimal(payroll_row[2])
            ei_er = to_decimal(payroll_row[3])
            tax = to_decimal(payroll_row[4])
            
            total_due = cpp_ee + cpp_er + ei_ee + ei_er + tax
            total_remitted = to_decimal(remit_row[0]) if remit_row and remit_row[0] else Decimal("0")
            
            variance = total_due - total_remitted
            
            if abs(variance) > Decimal("100"):  # More than $100 variance
                severity = "CRITICAL" if abs(variance) > Decimal("1000") else "HIGH"
                
                self.add_finding(
                    category="Payroll Remittances",
                    severity=severity,
                    title=f"Payroll remittance variance: ${abs(variance):,.2f}",
                    description=f"Expected remittances: ${total_due:,.2f} (CPP: ${cpp_ee + cpp_er:,.2f}, "
                               f"EI: ${ei_ee + ei_er:,.2f}, Tax: ${tax:,.2f}). "
                               f"Actual remittances recorded: ${total_remitted:,.2f}. "
                               f"Variance: ${variance:,.2f}",
                    action="Verify all PD7A remittances are recorded in receipts. Check for missed payments or recording errors. "
                          "CRA penalties apply for late/short remittances.",
                    savings=Decimal("0") if variance < 0 else abs(variance)  # If overpaid, potential recovery
                )
        
        cur.close()
    
    def check_expense_classification(self):
        """Check for expense misclassifications."""
        print("🔍 Checking expense account classifications...")
        
        cur = self.conn.cursor()
        
        # Check for receipts without expense_account
        cur.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (expense_account IS NULL OR expense_account = '' OR expense_account = 'UNKNOWN')
              AND amount > 0
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            count = row[0]
            total = to_decimal(row[1])
            
            self.add_finding(
                category="Expense Classification",
                severity="MEDIUM",
                title=f"{count} receipts without expense account classification",
                description=f"Found ${total:,.2f} in expenses without proper GL account assignment. "
                           "Proper classification ensures all deductions are claimed on T2.",
                action="Review receipts with NULL/UNKNOWN expense_account. Assign proper GL accounts from chart_of_accounts.",
                savings=Decimal("0")
            )
        
        # Check for generic "Office Expense" that might be better classified
        cur.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND expense_account ILIKE '%%office expense%%'
              AND amount > 200
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            count = row[0]
            total = to_decimal(row[1])
            
            self.add_finding(
                category="Expense Classification",
                severity="LOW",
                title=f"{count} large expenses in generic 'Office Expense' account",
                description=f"Found ${total:,.2f} in large expenses classified as 'Office Expense'. "
                           "Consider more specific accounts: Equipment, Software, Furniture, Supplies.",
                action="Review large office expense receipts. Reclassify to specific accounts or capitalize as assets if >$200.",
                savings=Decimal("0")
            )
        
        cur.close()
    
    def check_accounts_receivable_writeoffs(self):
        """Check for old receivables that could be written off as bad debts."""
        print("🔍 Checking for bad debt write-off opportunities...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                c.reserve_number,
                c.charter_date,
                c.total_amount_due,
                COALESCE(SUM(p.amount), 0) as paid,
                c.total_amount_due - COALESCE(SUM(p.amount), 0) as balance
            FROM charters c
            LEFT JOIN payments p ON p.reserve_number = c.reserve_number
            WHERE c.charter_date < %s - INTERVAL '2 years'
              AND c.status != 'cancelled'
            GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due
            HAVING c.total_amount_due - COALESCE(SUM(p.amount), 0) > 50
            ORDER BY c.charter_date
        """, (self.end_date,))
        
        rows = cur.fetchall()
        if rows:
            total_writeoff = sum(to_decimal(row[4]) for row in rows)
            count = len(rows)
            
            # Tax savings from bad debt deduction (assume 25% tax rate)
            tax_savings = total_writeoff * Decimal("0.25")
            
            self.add_finding(
                category="Bad Debt Deductions",
                severity="MEDIUM",
                title=f"{count} old receivables eligible for bad debt write-off",
                description=f"Found ${total_writeoff:,.2f} in uncollected receivables over 2 years old. "
                           f"CRA allows bad debt deductions for amounts previously included in income. "
                           f"Estimated tax savings: ${tax_savings:,.2f}",
                action="Review aging receivables. Write off uncollectible amounts: "
                      "1) Update charter status or create write-off entries in accounting system "
                      "2) Claim bad debt deduction on T2 "
                      "3) Document collection efforts made",
                savings=tax_savings
            )
        
        cur.close()
    
    def check_duplicate_expenses(self):
        """Check for potential duplicate expense entries."""
        print("🔍 Checking for duplicate expense entries...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                vendor_name,
                receipt_date,
                amount,
                COUNT(*) as dup_count,
                SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
            GROUP BY vendor_name, receipt_date, amount
            HAVING COUNT(*) > 1
            ORDER BY total DESC
            LIMIT 20
        """, (self.start_date, self.end_date))
        
        rows = cur.fetchall()
        if rows:
            total_duplicates = sum(to_decimal(row[4]) - to_decimal(row[2]) for row in rows)  # Total minus one original
            count = sum(row[3] - 1 for row in rows)  # Total duplicates minus originals
            
            self.add_finding(
                category="Data Quality",
                severity="CRITICAL",
                title=f"Potential {count} duplicate expense entries found",
                description=f"Found expenses with same vendor, date, and amount appearing multiple times. "
                           f"Potential duplicate expenses: ${total_duplicates:,.2f}. "
                           "This could inflate expenses and reduce taxable income incorrectly.",
                action="Review flagged receipts. Delete true duplicates. Keep legitimate recurring payments (e.g., monthly subscriptions).",
                savings=Decimal("0")  # Savings = avoiding over-deduction
            )
        
        cur.close()
    
    def check_missing_receipts(self):
        """Check for banking transactions without matching receipts."""
        print("🔍 Checking for expenses without receipt backup...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as count, SUM(ABS(amount)) as total
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s AND %s
              AND amount < 0
              AND ABS(amount) > 20
              AND banking_transaction_id NOT IN (
                  SELECT banking_transaction_id 
                  FROM receipts 
                  WHERE banking_transaction_id IS NOT NULL
              )
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[0] > 0:
            count = row[0]
            total = to_decimal(row[1])
            
            self.add_finding(
                category="Data Completeness",
                severity="HIGH",
                title=f"{count} bank withdrawals without receipts",
                description=f"Found ${total:,.2f} in bank withdrawals >$20 not matched to receipt records. "
                           "CRA requires documentation for expense deductions. Missing receipts = lost deductions.",
                action="Review banking_transactions with no matching receipts. Create receipt records or write off as "
                      "non-deductible if documentation unavailable.",
                savings=Decimal("0")
            )
        
        cur.close()
    
    def check_home_office_expenses(self):
        """Check if home office expenses are being claimed."""
        print("🔍 Checking for home office expense opportunities...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (expense_account ILIKE '%%home office%%' 
                   OR expense_account ILIKE '%%utilities%%'
                   OR expense_account ILIKE '%%rent%%'
                   OR expense_account ILIKE '%%mortgage%%'
                   OR expense_account ILIKE '%%property tax%%')
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        home_office_total = to_decimal(row[1]) if row and row[1] else Decimal("0")
        
        if home_office_total < Decimal("1000"):
            self.add_finding(
                category="Home Office Expenses",
                severity="LOW",
                title="Low/missing home office expense claims",
                description=f"Found only ${home_office_total:,.2f} in home office expenses. "
                           "If you use part of your home for business administration, you may claim a portion of: "
                           "rent/mortgage interest, utilities, property taxes, insurance, maintenance. "
                           "Based on square footage or % of home used for business.",
                action="If applicable, calculate home office percentage (business sq ft / total sq ft) and claim: "
                      "- Rent or mortgage interest (portion) "
                      "- Utilities (heat, electricity, water) "
                      "- Property taxes "
                      "- Home insurance "
                      "Estimated annual savings for 10% business use on $2000/month expenses: $2,400/year deduction.",
                savings=Decimal("600")  # Estimate: $2400 deduction * 25% tax rate
            )
        
        cur.close()
    
    def check_insurance_expenses(self):
        """Check for proper insurance expense tracking."""
        print("🔍 Checking insurance expense tracking...")
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as count, SUM(amount) as total
            FROM receipts
            WHERE receipt_date BETWEEN %s AND %s
              AND (expense_account ILIKE '%%insurance%%' 
                   OR vendor_name ILIKE '%%insurance%%')
        """, (self.start_date, self.end_date))
        
        row = cur.fetchone()
        if row and row[1]:
            total = to_decimal(row[1])
            count = row[0]
            
            self.add_finding(
                category="Insurance Expenses",
                severity="INFO",
                title=f"${total:,.2f} in insurance expenses tracked ({count} entries)",
                description="Business insurance is 100% deductible: commercial vehicle insurance, liability insurance, "
                           "business property insurance. Ensure all policies are recorded.",
                action="Verify all insurance policies are recorded: vehicle insurance, liability, business property. "
                      "Split personal/business portions if applicable (e.g., personal vehicle used for business).",
                savings=Decimal("0")
            )
        else:
            self.add_finding(
                category="Insurance Expenses",
                severity="MEDIUM",
                title="No insurance expenses found",
                description="No insurance expenses recorded. Commercial vehicles require insurance, which is fully deductible.",
                action="Verify insurance payments are recorded. Check if payments are coming from banking_transactions "
                      "and need to be added to receipts table.",
                savings=Decimal("0")
            )
        
        cur.close()
    
    def generate_report(self):
        """Run all checks and generate comprehensive report."""
        print(f"\n{'='*80}")
        print(f"AI YEAR-END TAX OPTIMIZATION ANALYSIS - {self.year}")
        print(f"{'='*80}\n")
        
        # Run all checks
        self.check_missing_gst_itcs()
        self.check_uncollected_gst()
        self.check_vehicle_expenses()
        self.check_cca_opportunities()
        self.check_meal_entertainment_limits()
        self.check_payroll_remittance_accuracy()
        self.check_expense_classification()
        self.check_accounts_receivable_writeoffs()
        self.check_duplicate_expenses()
        self.check_missing_receipts()
        self.check_home_office_expenses()
        self.check_insurance_expenses()
        
        # Sort findings by severity
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        self.findings.sort(key=lambda x: severity_order[x["severity"]])
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"EXECUTIVE SUMMARY")
        print(f"{'='*80}\n")
        
        print(f"Total Findings: {len(self.findings)}")
        print(f"Estimated Total Tax Savings Potential: ${self.potential_savings:,.2f}\n")
        
        # Count by severity
        severity_counts = defaultdict(int)
        for f in self.findings:
            severity_counts[f["severity"]] += 1
        
        print("Findings by Severity:")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            if severity_counts[sev] > 0:
                print(f"  {sev}: {severity_counts[sev]}")
        
        # Print detailed findings
        print(f"\n{'='*80}")
        print(f"DETAILED FINDINGS")
        print(f"{'='*80}\n")
        
        for i, finding in enumerate(self.findings, 1):
            print(f"\n[{i}] {finding['severity']} - {finding['category']}")
            print(f"    {finding['title']}")
            print(f"\n    {finding['description']}")
            print(f"\n    ACTION: {finding['action']}")
            if finding['potential_savings'] > 0:
                print(f"\n    💰 POTENTIAL SAVINGS: ${finding['potential_savings']:,.2f}")
            print(f"\n    {'-'*76}")
        
        # Export to CSV
        output_dir = Path("L:/limo/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        df = pd.DataFrame(self.findings)
        csv_path = output_dir / f"tax_optimization_{self.year}.csv"
        df.to_csv(csv_path, index=False)
        
        print(f"\n{'='*80}")
        print(f"Report saved to: {csv_path}")
        print(f"Total Estimated Tax Savings: ${self.potential_savings:,.2f}")
        print(f"{'='*80}\n")
        
        self.conn.close()


def main():
    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    else:
        year = datetime.now().year - 1  # Default to last year
    
    optimizer = TaxOptimizer(year)
    optimizer.generate_report()


if __name__ == "__main__":
    main()
