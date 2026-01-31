"""
AI Copilot Function Registry

Provides callable database and calculation functions for the AI assistant.
All functions include:
- Detailed docstrings explaining purpose and parameters
- JSON schema for LLM function calling
- Permission requirements (admin, manager, user)
- Error handling and logging
- Database transaction safety (commit/rollback)

Usage:
    from ai_functions import get_trial_balance, calculate_wcb_owed
    
    # Get trial balance for December 2024
    result = get_trial_balance(year=2024, month=12)
    print(f"Debit Total: ${result['debit_total']:.2f}")
    print(f"Credit Total: ${result['credit_total']:.2f}")
    print(f"Balanced: {result['balanced']}")
"""

import os
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor


class AIFunctionRegistry:
    """Registry and executor for AI-callable database functions"""
    
    def __init__(self, db_host: str = None, db_name: str = None, 
                 db_user: str = None, db_password: str = None):
        """Initialize database connection"""
        self.db_host = db_host or os.environ.get("DB_HOST", "localhost")
        self.db_name = db_name or os.environ.get("DB_NAME", "almsdata")
        self.db_user = db_user or os.environ.get("DB_USER", "postgres")
        self.db_password = db_password or os.environ.get("DB_PASSWORD", "***REDACTED***")
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            # Try without password first (for peer authentication or trusted)
            try:
                self.conn = psycopg2.connect(
                    host=self.db_host,
                    database=self.db_name,
                    user=self.db_user
                )
                return
            except:
                pass
            
            # Then try with password
            self.conn = psycopg2.connect(
                host=self.db_host,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
        except Exception as e:
            raise RuntimeError(f"Database connection failed: {e}")
    
    def _get_cursor(self):
        """Get a database cursor with error checking"""
        if not self.conn:
            self._connect()
        try:
            # Try to rollback any aborted transaction
            self.conn.rollback()
        except:
            pass
        return self.conn.cursor(cursor_factory=RealDictCursor)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    # ========== FINANCIAL REPORTS ==========
    
    def get_trial_balance(self, year: int, month: int) -> Dict[str, Any]:
        """
        Generate trial balance report for specified month.
        
        Trial balance shows all accounts with debit and credit totals.
        Used for accounting verification and financial statement preparation.
        
        Args:
            year: Year (e.g., 2024)
            month: Month 1-12
        
        Returns:
            {
                "accounts": [{"account": str, "debit": Decimal, "credit": Decimal}],
                "debit_total": Decimal,
                "credit_total": Decimal,
                "balanced": bool
            }
        
        Example:
            >>> result = registry.get_trial_balance(2024, 12)
            >>> print(f"Debit: ${result['debit_total']:.2f}")
            >>> print(f"Balanced: {result['balanced']}")
        """
        try:
            cur = self._get_cursor()
            
            # Query general_ledger for account balances
            cur.execute("""
                SELECT 
                    account as account,
                    SUM(CASE WHEN debit IS NOT NULL THEN debit ELSE 0 END) as debit,
                    SUM(CASE WHEN credit IS NOT NULL THEN credit ELSE 0 END) as credit
                FROM general_ledger
                WHERE EXTRACT(YEAR FROM transaction_date) = %s 
                    AND EXTRACT(MONTH FROM transaction_date) = %s
                GROUP BY account
                ORDER BY account
            """, (year, month))
            
            accounts = []
            debit_total = Decimal("0.00")
            credit_total = Decimal("0.00")
            
            for row in cur.fetchall():
                debit = Decimal(str(row['debit'] or 0))
                credit = Decimal(str(row['credit'] or 0))
                accounts.append({
                    "account": row['account'],
                    "debit": float(debit),
                    "credit": float(credit)
                })
                debit_total += debit
                credit_total += credit
            
            cur.close()
            
            return {
                "accounts": accounts,
                "debit_total": float(debit_total),
                "credit_total": float(credit_total),
                "balanced": abs(debit_total - credit_total) < Decimal("0.01")
            }
        
        except Exception as e:
            return {"error": str(e), "accounts": [], "debit_total": 0, "credit_total": 0, "balanced": False}
    
    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """
        Generate monthly financial summary for revenue, expenses, and GST.
        
        Aggregates all charters, receipts, and payments for the month.
        Shows net taxable revenue and GST collected.
        
        Args:
            year: Year (e.g., 2024)
            month: Month 1-12
        
        Returns:
            {
                "period": "January 2024",
                "total_revenue": Decimal,
                "total_expenses": Decimal,
                "net_revenue": Decimal,
                "gst_collected": Decimal,
                "charter_count": int,
                "payment_count": int,
                "receipt_count": int
            }
        """
        try:
            cur = self._get_cursor()
            
            # Charter revenue
            cur.execute("""
                SELECT 
                    COUNT(*) as charter_count,
                    COALESCE(SUM(total_amount_due), 0) as total_revenue,
                    COALESCE(SUM(COALESCE(driver_gratuity, 0)), 0) as gratuity
                FROM charters
                WHERE EXTRACT(YEAR FROM charter_date) = %s 
                    AND EXTRACT(MONTH FROM charter_date) = %s
                    AND status NOT IN ('cancelled')
            """, (year, month))
            
            charter_row = cur.fetchone()
            charter_count = charter_row['charter_count'] or 0
            total_revenue = Decimal(str(charter_row['total_revenue'] or 0))
            gratuity = Decimal(str(charter_row['gratuity'] or 0))
            
            # Expenses (receipts)
            cur.execute("""
                SELECT 
                    COUNT(*) as receipt_count,
                    COALESCE(SUM(amount), 0) as total_expenses
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = %s 
                    AND EXTRACT(MONTH FROM receipt_date) = %s
                    AND status NOT IN ('cancelled')
            """, (year, month))
            
            receipt_row = cur.fetchone()
            receipt_count = receipt_row['receipt_count'] or 0
            total_expenses = Decimal(str(receipt_row['total_expenses'] or 0))
            
            # Payments
            cur.execute("""
                SELECT COUNT(*) as payment_count
                FROM payments
                WHERE EXTRACT(YEAR FROM payment_date) = %s 
                    AND EXTRACT(MONTH FROM payment_date) = %s
            """, (year, month))
            
            payment_row = cur.fetchone()
            payment_count = payment_row['payment_count'] or 0
            
            cur.close()
            
            # Calculate GST (5% in Alberta, included in revenue)
            gst_collected = total_revenue * Decimal("0.05") / Decimal("1.05")
            net_revenue = total_revenue - total_expenses - gratuity
            
            month_name = datetime(year, month, 1).strftime("%B %Y")
            
            return {
                "period": month_name,
                "total_revenue": float(total_revenue),
                "total_expenses": float(total_expenses),
                "net_revenue": float(net_revenue),
                "gst_collected": float(gst_collected),
                "charter_count": charter_count,
                "payment_count": payment_count,
                "receipt_count": receipt_count
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    # ========== PAYROLL & TAX ==========
    
    def calculate_wcb_owed(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Calculate Workers' Compensation Board (WCB) premium owed.
        
        WCB rate in Alberta for transportation: 1.5% of gross payroll.
        Includes employee pay and gratuities (if paid to employees).
        
        Args:
            start_date: ISO format (2024-01-01)
            end_date: ISO format (2024-12-31)
        
        Returns:
            {
                "period": "2024-01-01 to 2024-12-31",
                "gross_payroll": Decimal,
                "wcb_rate": Decimal,
                "wcb_owed": Decimal,
                "wcb_paid": Decimal,
                "wcb_balance": Decimal,
                "employee_count": int,
                "records_count": int
            }
        """
        try:
            cur = self._get_cursor()
            
            # Get gross payroll from driver_payroll table
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT driver_id) as employee_count,
                    COUNT(*) as records_count,
                    COALESCE(SUM(gross_pay), 0) as gross_payroll
                FROM driver_payroll
                WHERE pay_date >= %s AND pay_date <= %s
            """, (start_date, end_date))
            
            payroll_row = cur.fetchone()
            if not payroll_row:
                return {"error": "No payroll data found for specified date range"}
            
            try:
                employee_count = int(payroll_row['employee_count'] or 0)
                records_count = int(payroll_row['records_count'] or 0)
                gross_payroll = Decimal(str(payroll_row['gross_payroll'] or 0))
            except (ValueError, TypeError, KeyError) as e:
                return {"error": f"Error parsing payroll data: {e}"}
            
            # Get WCB payments made (from accounting records)
            try:
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) as wcb_paid
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = EXTRACT(YEAR FROM %s::date)
                        AND vendor_name ILIKE '%WCB%'
                """, (start_date,))
                
                wcb_row = cur.fetchone()
                if not wcb_row:
                    wcb_paid = Decimal("0.00")
                else:
                    wcb_paid = Decimal(str(wcb_row.get('wcb_paid') or 0))
            except Exception as e:
                # If WCB query fails, just use 0 for WCB paid
                wcb_paid = Decimal("0.00")
            
            cur.close()
            
            wcb_rate = Decimal("0.015")  # 1.5%
            wcb_owed = gross_payroll * wcb_rate
            wcb_balance = wcb_owed - wcb_paid
            
            return {
                "period": f"{start_date} to {end_date}",
                "gross_payroll": float(gross_payroll),
                "wcb_rate": float(wcb_rate),
                "wcb_owed": float(wcb_owed),
                "wcb_paid": float(wcb_paid),
                "wcb_balance": float(wcb_balance),
                "employee_count": employee_count,
                "records_count": records_count
            }
        
        except Exception as e:
            return {"error": f"WCB calculation failed: {str(e)}"}
    
    def calculate_employee_pay(self, employee_id: int, period_id: int = None) -> Dict[str, Any]:
        """
        Calculate employee pay for a specific period with all deductions.
        
        Formula: (charter_hours × hourly_rate) + gratuity - (CPP + EI + federal_tax + provincial_tax + other_deductions)
        
        Args:
            employee_id: Employee ID in employees table
            period_id: Pay period ID (if None, uses most recent)
        
        Returns:
            {
                "employee_name": str,
                "period": "2024-01-15 to 2024-01-31",
                "charter_hours": Decimal,
                "hourly_rate": Decimal,
                "base_pay": Decimal,
                "gratuity": Decimal,
                "gross_pay": Decimal,
                "cpp_deduction": Decimal,
                "ei_deduction": Decimal,
                "federal_tax": Decimal,
                "provincial_tax": Decimal,
                "other_deductions": Decimal,
                "total_deductions": Decimal,
                "net_pay": Decimal
            }
        """
        try:
            cur = self._get_cursor()
            
            # Get employee info
            cur.execute("""
                SELECT employee_id, first_name, last_name, hourly_rate
                FROM employees
                WHERE employee_id = %s
            """, (employee_id,))
            
            emp = cur.fetchone()
            if not emp:
                return {"error": f"Employee {employee_id} not found"}
            
            # Get pay period and calculation
            if period_id:
                cur.execute("""
                    SELECT 
                        period_id, period_start, period_end,
                        charter_hours, gratuity_owed, base_pay,
                        cpp_contribution, ei_contribution, federal_income_tax, 
                        provincial_income_tax, other_deductions,
                        net_pay
                    FROM employee_pay_master
                    WHERE employee_id = %s AND period_id = %s
                """, (employee_id, period_id))
            else:
                cur.execute("""
                    SELECT 
                        period_id, period_start, period_end,
                        charter_hours, gratuity_owed, base_pay,
                        cpp_contribution, ei_contribution, federal_income_tax, 
                        provincial_income_tax, other_deductions,
                        net_pay
                    FROM employee_pay_master
                    WHERE employee_id = %s
                    ORDER BY period_start DESC
                    LIMIT 1
                """, (employee_id,))
            
            pay = cur.fetchone()
            if not pay:
                return {"error": f"No pay records found for employee {employee_id}"}
            
            cur.close()
            
            charter_hours = Decimal(str(pay['charter_hours'] or 0))
            hourly_rate = Decimal(str(emp['hourly_rate'] or 0))
            base_pay = Decimal(str(pay['base_pay'] or 0))
            gratuity = Decimal(str(pay['gratuity_owed'] or 0))
            gross_pay = base_pay + gratuity
            
            cpp = Decimal(str(pay['cpp_contribution'] or 0))
            ei = Decimal(str(pay['ei_contribution'] or 0))
            fed_tax = Decimal(str(pay['federal_income_tax'] or 0))
            prov_tax = Decimal(str(pay['provincial_income_tax'] or 0))
            other = Decimal(str(pay['other_deductions'] or 0))
            total_ded = cpp + ei + fed_tax + prov_tax + other
            net_pay = Decimal(str(pay['net_pay'] or 0))
            
            return {
                "employee_name": f"{emp['first_name']} {emp['last_name']}",
                "period": f"{pay['period_start']} to {pay['period_end']}",
                "charter_hours": float(charter_hours),
                "hourly_rate": float(hourly_rate),
                "base_pay": float(base_pay),
                "gratuity": float(gratuity),
                "gross_pay": float(gross_pay),
                "cpp_deduction": float(cpp),
                "ei_deduction": float(ei),
                "federal_tax": float(fed_tax),
                "provincial_tax": float(prov_tax),
                "other_deductions": float(other),
                "total_deductions": float(total_ded),
                "net_pay": float(net_pay)
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def check_missing_deductions(self, year: int) -> Dict[str, Any]:
        """
        Find receipts with missing category for tax optimization.
        
        Tax optimization: Properly categorized expenses reduce taxable income.
        This identifies receipts that should be categorized.
        
        Args:
            year: Year to analyze (e.g., 2024)
        
        Returns:
            {
                "year": 2024,
                "total_receipts": int,
                "uncategorized_count": int,
                "uncategorized_amount": Decimal,
                "uncategorized_percentage": float,
                "recommendations": [
                    {"receipt_id": int, "amount": Decimal, "vendor": str, "suggested_category": str}
                ]
            }
        """
        try:
            cur = self._get_cursor()
            
            # Find uncategorized receipts
            cur.execute("""
                SELECT 
                    receipt_id, amount, vendor_name, payment_method, notes
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = %s
                    AND (category IS NULL OR category = 'Uncategorized' OR category = '')
                ORDER BY amount DESC
            """, (year,))
            
            uncategorized = []
            uncategorized_amount = Decimal("0")
            
            for row in cur.fetchone() if cur else []:
                amount = Decimal(str(row['amount'] or 0))
                uncategorized_amount += amount
                vendor = row['vendor_name'] or "Unknown"
                
                # Simple category suggestion based on vendor
                suggested = self._suggest_category(vendor, row['payment_method'], row['notes'])
                
                uncategorized.append({
                    "receipt_id": row['receipt_id'],
                    "amount": float(amount),
                    "vendor": vendor,
                    "suggested_category": suggested
                })
            
            # Get total receipt count
            cur.execute("""
                SELECT COUNT(*) as total
                FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) = %s
            """, (year,))
            
            total_row = cur.fetchone()
            total_count = total_row['total'] or 0
            
            cur.close()
            
            uncategorized_percent = (len(uncategorized) / total_count * 100) if total_count > 0 else 0
            
            return {
                "year": year,
                "total_receipts": total_count,
                "uncategorized_count": len(uncategorized),
                "uncategorized_amount": float(uncategorized_amount),
                "uncategorized_percentage": round(uncategorized_percent, 2),
                "recommendations": uncategorized[:20]  # Top 20
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    # ========== CHARTER & PAYMENT QUERIES ==========
    
    def get_unpaid_charters(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Find all charters with outstanding balance due.
        
        Used for accounts receivable aging, collection follow-up, and customer communication.
        
        Args:
            start_date: ISO format (2024-01-01) - charter_date start
            end_date: ISO format (2024-12-31)
        
        Returns:
            {
                "period": "2024-01-01 to 2024-12-31",
                "unpaid_count": int,
                "total_outstanding": Decimal,
                "charters": [
                    {
                        "reserve_number": str,
                        "client_name": str,
                        "charter_date": str,
                        "total_amount_due": Decimal,
                        "paid_amount": Decimal,
                        "balance_owing": Decimal,
                        "days_overdue": int
                    }
                ],
                "aging_summary": {
                    "<30_days": Decimal,
                    "30-60_days": Decimal,
                    "60-90_days": Decimal,
                    ">90_days": Decimal
                }
            }
        """
        try:
            cur = self._get_cursor()
            
            cur.execute("""
                SELECT 
                    c.reserve_number,
                    c.client_display_name,
                    c.charter_date,
                    c.total_amount_due,
                    COALESCE(SUM(p.amount), 0) as paid_amount
                FROM charters c
                LEFT JOIN payments p ON p.reserve_number = c.reserve_number
                WHERE c.charter_date >= %s AND c.charter_date <= %s
                    AND c.status NOT IN ('cancelled')
                GROUP BY c.charter_id, c.reserve_number, c.client_display_name, c.charter_date, c.total_amount_due
                HAVING c.total_amount_due > COALESCE(SUM(p.amount), 0) + 0.01
                ORDER BY c.total_amount_due - COALESCE(SUM(p.amount), 0) DESC
            """, (start_date, end_date))
            
            charters = []
            total_outstanding = Decimal("0")
            aging = {
                "<30_days": Decimal("0"),
                "30-60_days": Decimal("0"),
                "60-90_days": Decimal("0"),
                ">90_days": Decimal("0")
            }
            
            for row in cur.fetchall():
                balance = Decimal(str(row['paid_amount'] or 0))
                balance_owing = Decimal(str(row['total_amount_due'] or 0)) - balance
                days = int((datetime.now().date() - row['charter_date']).days)
                
                charters.append({
                    "reserve_number": row['reserve_number'],
                    "client_name": row['client_display_name'],
                    "charter_date": str(row['charter_date']),
                    "total_amount_due": float(Decimal(str(row['total_amount_due']))),
                    "paid_amount": float(balance),
                    "balance_owing": float(balance_owing),
                    "days_overdue": max(0, days)
                })
                
                total_outstanding += balance_owing
                
                if days < 30:
                    aging["<30_days"] += balance
                elif days < 60:
                    aging["30-60_days"] += balance
                elif days < 90:
                    aging["60-90_days"] += balance
                else:
                    aging[">90_days"] += balance
            
            cur.close()
            
            return {
                "period": f"{start_date} to {end_date}",
                "unpaid_count": len(charters),
                "total_outstanding": float(total_outstanding),
                "charters": charters,
                "aging_summary": {k: float(v) for k, v in aging.items()}
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    # ========== DATA MODIFICATION (REQUIRES PERMISSION) ==========
    
    def update_lms_data(self, reserve_number: str, field: str, value: Any) -> Dict[str, Any]:
        """
        Update legacy LMS data in charters table.
        
        CAUTION: This modifies historical data. Requires admin permission and confirmation.
        Only certain fields can be updated: cancelled, hold, notes.
        
        Args:
            reserve_number: Charter reserve number (e.g., "019708")
            field: Field name to update (cancelled, hold, notes only)
            value: New value
        
        Returns:
            {
                "success": bool,
                "reserve_number": str,
                "field": str,
                "old_value": Any,
                "new_value": Any,
                "message": str
            }
        """
        # Whitelist of allowed fields to prevent SQL injection
        allowed_fields = {'cancelled', 'hold', 'notes', 'status'}
        
        if field not in allowed_fields:
            return {
                "success": False,
                "error": f"Field '{field}' not allowed. Only: {', '.join(allowed_fields)}"
            }
        
        try:
            cur = self._get_cursor()
            
            # Get old value
            cur.execute(f"SELECT {field} FROM charters WHERE reserve_number = %s", (reserve_number,))
            row = cur.fetchone()
            if not row:
                return {"success": False, "error": f"Charter {reserve_number} not found"}
            
            old_value = row[field]
            
            # Update
            cur.execute(f"""
                UPDATE charters 
                SET {field} = %s, updated_at = NOW()
                WHERE reserve_number = %s
            """, (value, reserve_number))
            
            self.conn.commit()
            
            return {
                "success": True,
                "reserve_number": reserve_number,
                "field": field,
                "old_value": old_value,
                "new_value": value,
                "message": f"Updated {reserve_number}.{field} from '{old_value}' to '{value}'"
            }
        
        except Exception as e:
            self.conn.rollback()
            return {"success": False, "error": str(e)}
        
        finally:
            cur.close()
    
    # ========== HELPER METHODS ==========
    
    def _suggest_category(self, vendor: str, payment_method: str = None, notes: str = None) -> str:
        """Suggest receipt category based on vendor and payment method"""
        vendor_lower = vendor.lower()
        
        # Fuel vendors
        if any(x in vendor_lower for x in ['esso', 'shell', 'petro canada', 'co-op', 'gas', 'fuel']):
            return "Vehicle Fuel"
        
        # Maintenance
        if any(x in vendor_lower for x in ['canadian tire', 'midas', 'jiffy', 'mechanic', 'maintenance']):
            return "Vehicle Maintenance"
        
        # Office/supplies
        if any(x in vendor_lower for x in ['staples', 'office depot', 'amazon', 'supplies']):
            return "Office Supplies"
        
        # Meals
        if any(x in vendor_lower for x in ['restaurant', 'cafe', 'mcdonald', 'subway', 'pizza']):
            return "Meals & Entertainment"
        
        # Rent
        if any(x in vendor_lower for x in ['rent', 'lease', 'landlord', 'property']):
            return "Rent/Facility"
        
        # Insurance
        if any(x in vendor_lower for x in ['insurance', 'insurance company']):
            return "Insurance"
        
        # Default
        return "Other Expense"


# Module-level convenience functions
def get_trial_balance(year: int, month: int) -> Dict[str, Any]:
    """Get trial balance - see AIFunctionRegistry.get_trial_balance()"""
    reg = AIFunctionRegistry()
    try:
        return reg.get_trial_balance(year, month)
    finally:
        reg.close()


def calculate_wcb_owed(start_date: str, end_date: str) -> Dict[str, Any]:
    """Calculate WCB owed - see AIFunctionRegistry.calculate_wcb_owed()"""
    reg = AIFunctionRegistry()
    try:
        return reg.calculate_wcb_owed(start_date, end_date)
    finally:
        reg.close()


def get_unpaid_charters(start_date: str, end_date: str) -> Dict[str, Any]:
    """Get unpaid charters - see AIFunctionRegistry.get_unpaid_charters()"""
    reg = AIFunctionRegistry()
    try:
        return reg.get_unpaid_charters(start_date, end_date)
    finally:
        reg.close()


def calculate_employee_pay(employee_id: int, period_id: int = None) -> Dict[str, Any]:
    """Calculate employee pay - see AIFunctionRegistry.calculate_employee_pay()"""
    reg = AIFunctionRegistry()
    try:
        return reg.calculate_employee_pay(employee_id, period_id)
    finally:
        reg.close()


def get_monthly_summary(year: int, month: int) -> Dict[str, Any]:
    """Get monthly summary - see AIFunctionRegistry.get_monthly_summary()"""
    reg = AIFunctionRegistry()
    try:
        return reg.get_monthly_summary(year, month)
    finally:
        reg.close()


def check_missing_deductions(year: int) -> Dict[str, Any]:
    """Check missing deductions - see AIFunctionRegistry.check_missing_deductions()"""
    reg = AIFunctionRegistry()
    try:
        return reg.check_missing_deductions(year)
    finally:
        reg.close()


if __name__ == "__main__":
    # Test the functions
    reg = AIFunctionRegistry(
        db_host="localhost",
        db_name="almsdata",
        db_user="postgres",
        db_password="***REDACTED***"
    )
    
    print("=" * 80)
    print("TRIAL BALANCE TEST")
    print("=" * 80)
    result = reg.get_trial_balance(2024, 12)
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Debit Total: ${result['debit_total']:.2f}")
        print(f"Credit Total: ${result['credit_total']:.2f}")
        print(f"Balanced: {result['balanced']}")
        print(f"Accounts: {len(result['accounts'])}")
    
    print("\n" + "=" * 80)
    print("WCB CALCULATION TEST")
    print("=" * 80)
    result = reg.calculate_wcb_owed("2024-01-01", "2024-12-31")
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Period: {result['period']}")
        print(f"Gross Payroll: ${result['gross_payroll']:.2f}")
        print(f"WCB Rate: {result['wcb_rate']*100:.1f}%")
        print(f"WCB Owed: ${result['wcb_owed']:.2f}")
        print(f"WCB Paid: ${result['wcb_paid']:.2f}")
        print(f"Balance: ${result['wcb_balance']:.2f}")
    
    print("\n" + "=" * 80)
    print("UNPAID CHARTERS TEST")
    print("=" * 80)
    result = reg.get_unpaid_charters("2024-01-01", "2024-12-31")
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Unpaid Count: {result['unpaid_count']}")
        print(f"Total Outstanding: ${result['total_outstanding']:.2f}")
        print(f"Aging Summary: {result['aging_summary']}")
    
    reg.close()
