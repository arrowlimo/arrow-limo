"""
T4 and Payroll Entry API Routes

Handles:
1. T4 form entry and retrieval
2. Payroll period entry and calculations
3. Auto-calculation vs manual entry reconciliation
4. T4 PDF generation
"""

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["payroll-tax"])


# ============================================================================
# MODELS
# ============================================================================

class T4Entry(BaseModel):
    employee_id: int
    tax_year: int
    sin: str | None = None
    address: str | None = None
    city_province_zip: str | None = None
    box14: Decimal  # Employment Income
    box16: Decimal  # Employee CPP
    box18: Decimal  # Employee EI
    box22: Decimal  # Income Tax
    box24: Decimal  # EI Insurable
    box26: Decimal  # CPP Pensionable
    box44: Decimal  # Commissions
    box46: Decimal  # Other Remuneration
    box52: Decimal  # Union Dues
    notes: str | None = None


class PayrollEntry(BaseModel):
    employee_id: int
    year: int
    pay_period: str
    regular_hours: Decimal
    hourly_rate: Decimal
    ot_hours: Decimal
    ot_rate: Decimal
    base_salary: Decimal
    bonus: Decimal
    gratuity: Decimal
    other_benefits: Decimal
    cpp: Decimal
    ei: Decimal
    income_tax: Decimal
    sin: str | None = None
    hire_date: date | None = None
    emp_type: str
    notes: str | None = None


# ============================================================================
# T4 ENDPOINTS
# ============================================================================

@router.get("/t4/{employee_id}/{tax_year}")
async def get_t4_entry(employee_id: int, tax_year: int, conn=Depends(get_connection)):
    """Retrieve T4 entry with auto-calculated values"""
    try:
        cur = conn.cursor()
        
        # Get stored T4 data
        cur.execute("""
            SELECT 
                t4_box_14, t4_box_16, t4_box_18, t4_box_22, t4_box_24, 
                t4_box_26, t4_box_44, t4_box_46, t4_box_52, notes
            FROM t4_entries
            WHERE employee_id = %s AND tax_year = %s
        """, (employee_id, tax_year))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="T4 entry not found")
        
        # Get auto-calculated values from payroll
        cur.execute("""
            SELECT 
                COALESCE(SUM(gross_pay), 0) as box14,
                COALESCE(SUM(cpp), 0) as box16,
                COALESCE(SUM(ei), 0) as box18,
                COALESCE(SUM(tax_withheld), 0) as box22,
                COALESCE(SUM(ei_insurable), 0) as box24,
                COALESCE(SUM(cpp_pensionable), 0) as box26,
                COALESCE(SUM(commissions), 0) as box44,
                COALESCE(SUM(other_remuneration), 0) as box46,
                COALESCE(SUM(union_dues), 0) as box52
            FROM driver_payroll
            WHERE employee_id = %s AND year = %s
        """, (employee_id, tax_year))
        
        auto_result = cur.fetchone()
        
        return {
            "employee_id": employee_id,
            "tax_year": tax_year,
            "box14": float(result[0] or 0),
            "box16": float(result[1] or 0),
            "box18": float(result[2] or 0),
            "box22": float(result[3] or 0),
            "box24": float(result[4] or 0),
            "box26": float(result[5] or 0),
            "box44": float(result[6] or 0),
            "box46": float(result[7] or 0),
            "box52": float(result[8] or 0),
            "auto_box14": float(auto_result[0]) if auto_result else 0,
            "auto_box16": float(auto_result[1]) if auto_result else 0,
            "auto_box18": float(auto_result[2]) if auto_result else 0,
            "auto_box22": float(auto_result[3]) if auto_result else 0,
            "auto_box24": float(auto_result[4]) if auto_result else 0,
            "auto_box26": float(auto_result[5]) if auto_result else 0,
            "auto_box44": float(auto_result[6]) if auto_result else 0,
            "auto_box46": float(auto_result[7]) if auto_result else 0,
            "auto_box52": float(auto_result[8]) if auto_result else 0,
            "notes": result[9] or ""
        }
    
    except Exception as e:
        logger.error(f"Error retrieving T4: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/t4")
async def save_t4_entry(entry: T4Entry, conn=Depends(get_connection)):
    """Save or update T4 entry"""
    try:
        cur = conn.cursor()
        
        # Check if exists
        cur.execute(
            "SELECT correction_id FROM t4_entries WHERE employee_id = %s AND tax_year = %s",
            (entry.employee_id, entry.tax_year)
        )
        
        exists = cur.fetchone() is not None
        
        if exists:
            cur.execute("""
                UPDATE t4_entries SET
                    t4_box_14 = %s, t4_box_16 = %s, t4_box_18 = %s, t4_box_22 = %s,
                    t4_box_24 = %s, t4_box_26 = %s, t4_box_44 = %s, t4_box_46 = %s,
                    t4_box_52 = %s, notes = %s, updated_at = NOW()
                WHERE employee_id = %s AND tax_year = %s
            """, (
                entry.box14, entry.box16, entry.box18, entry.box22,
                entry.box24, entry.box26, entry.box44, entry.box46,
                entry.box52, entry.notes, entry.employee_id, entry.tax_year
            ))
        else:
            cur.execute("""
                INSERT INTO t4_entries (
                    employee_id, tax_year, t4_box_14, t4_box_16, t4_box_18, t4_box_22,
                    t4_box_24, t4_box_26, t4_box_44, t4_box_46, t4_box_52, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                entry.employee_id, entry.tax_year, entry.box14, entry.box16, entry.box18, entry.box22,
                entry.box24, entry.box26, entry.box44, entry.box46, entry.box52, entry.notes
            ))
        
        conn.commit()
        return {"status": "success", "message": "T4 saved"}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving T4: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/t4/{employee_id}/{tax_year}/pdf")
async def generate_t4_pdf(employee_id: int, tax_year: int, conn=Depends(get_connection)):
    """Generate T4 PDF"""
    try:
        from io import BytesIO

        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        cur = conn.cursor()
        
        # Get employee and T4 data
        cur.execute("""
            SELECT e.full_name, e.street_address, e.city, e.province, e.postal_code,
                   t4.t4_box_14, t4.t4_box_16, t4.t4_box_18, t4.t4_box_22,
                   t4.t4_box_24, t4.t4_box_26, t4.t4_box_44, t4.t4_box_46, t4.t4_box_52
            FROM employees e
            LEFT JOIN t4_entries t4 ON e.employee_id = t4.employee_id AND t4.tax_year = %s
            WHERE e.employee_id = %s
        """, (tax_year, employee_id))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Create PDF in memory
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "STATEMENT OF REMUNERATION PAID (T4)")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 70, f"Tax Year: {tax_year}")
        
        # Employee Info
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 100, "EMPLOYEE INFORMATION")
        c.setFont("Helvetica", 9)
        c.drawString(70, height - 120, f"Name: {result[0]}")
        c.drawString(70, height - 135, f"Address: {result[1]}, {result[2]}, {result[3]} {result[4]}")
        
        # T4 Boxes
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 165, "T4 BOXES")
        c.setFont("Helvetica", 9)
        
        boxes = [
            ("Box 14 - Employment Income", result[5]),
            ("Box 16 - Employee CPP", result[6]),
            ("Box 18 - Employee EI", result[7]),
            ("Box 22 - Income Tax", result[8]),
            ("Box 24 - EI Insurable Earnings", result[9]),
            ("Box 26 - CPP Pensionable Earnings", result[10]),
            ("Box 44 - Commissions", result[11]),
            ("Box 46 - Other Remuneration", result[12]),
            ("Box 52 - Union Dues", result[13]),
        ]
        
        y = height - 185
        for label, value in boxes:
            c.drawString(70, y, f"{label}: ${value or 0:.2f}")
            y -= 15
        
        c.save()
        buffer.seek(0)
        return buffer
    
    except Exception as e:
        logger.error(f"Error generating T4 PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PAYROLL ENDPOINTS
# ============================================================================

@router.get("/payroll/{employee_id}/{year}/{period}")
async def get_payroll_entry(employee_id: int, year: int, period: str, conn=Depends(get_connection)):
    """Retrieve payroll entry"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                regular_hours, hourly_rate, ot_hours, ot_rate, base_salary,
                bonus, gratuity, other_benefits, cpp, ei, income_tax,
                notes
            FROM payroll_entries
            WHERE employee_id = %s AND year = %s AND pay_period = %s
        """, (employee_id, year, period))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Payroll entry not found")
        
        return {
            "regularHours": float(result[0] or 0),
            "hourlyRate": float(result[1] or 0),
            "otHours": float(result[2] or 0),
            "otRate": float(result[3] or 0),
            "baseSalary": float(result[4] or 0),
            "bonus": float(result[5] or 0),
            "gratuity": float(result[6] or 0),
            "otherBenefits": float(result[7] or 0),
            "cpp": float(result[8] or 0),
            "ei": float(result[9] or 0),
            "incomeTax": float(result[10] or 0),
            "notes": result[11] or ""
        }
    
    except Exception as e:
        logger.error(f"Error retrieving payroll: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payroll")
async def save_payroll_entry(entry: PayrollEntry, conn=Depends(get_connection)):
    """Save or update payroll entry"""
    try:
        cur = conn.cursor()
        
        # Check if exists
        cur.execute(
            "SELECT id FROM payroll_entries WHERE employee_id = %s AND year = %s AND pay_period = %s",
            (entry.employee_id, entry.year, entry.pay_period)
        )
        
        exists = cur.fetchone() is not None
        
        if exists:
            cur.execute("""
                UPDATE payroll_entries SET
                    regular_hours = %s, hourly_rate = %s, ot_hours = %s, ot_rate = %s,
                    base_salary = %s, bonus = %s, gratuity = %s, other_benefits = %s,
                    cpp = %s, ei = %s, income_tax = %s, notes = %s, updated_at = NOW()
                WHERE employee_id = %s AND year = %s AND pay_period = %s
            """, (
                entry.regular_hours, entry.hourly_rate, entry.ot_hours, entry.ot_rate,
                entry.base_salary, entry.bonus, entry.gratuity, entry.other_benefits,
                entry.cpp, entry.ei, entry.income_tax, entry.notes,
                entry.employee_id, entry.year, entry.pay_period
            ))
        else:
            cur.execute("""
                INSERT INTO payroll_entries (
                    employee_id, year, pay_period, regular_hours, hourly_rate, ot_hours, ot_rate,
                    base_salary, bonus, gratuity, other_benefits, cpp, ei, income_tax, sin,
                    hire_date, employment_type, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                entry.employee_id, entry.year, entry.pay_period, entry.regular_hours, entry.hourly_rate,
                entry.ot_hours, entry.ot_rate, entry.base_salary, entry.bonus, entry.gratuity,
                entry.other_benefits, entry.cpp, entry.ei, entry.income_tax, entry.sin,
                entry.hire_date, entry.emp_type, entry.notes
            ))
        
        conn.commit()
        return {"status": "success", "message": "Payroll saved"}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving payroll: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@router.get("/employee-work-history/{employee_id}/{year}")
async def get_employee_work_history(employee_id: int, year: int, conn=Depends(get_connection)):
    """Get all work history (charters) for an employee in a year"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                ch.charter_id, ch.charter_date, ch.charter_number, 
                ch.base_charge + ch.airport_fee + COALESCE(ch.additional_charges, 0) as gross,
                COALESCE(ch.gratuity_cash_amount, 0) as gratuity,
                COALESCE(dp.hours, 0) as hours,
                COALESCE(dp.hourly_rate, 0) as rate,
                ch.status
            FROM charters ch
            LEFT JOIN driver_payroll dp ON ch.charter_id = dp.charter_id AND dp.employee_id = %s
            WHERE ch.assigned_driver_id = %s OR dp.employee_id = %s
            AND EXTRACT(YEAR FROM ch.charter_date) = %s
            ORDER BY ch.charter_date DESC
        """, (employee_id, employee_id, employee_id, year))
        
        results = cur.fetchall()
        work_history = []
        
        for r in results:
            work_history.append({
                "id": r[0],
                "date": r[1].isoformat() if r[1] else None,
                "charterId": r[2],
                "gross": float(r[3] or 0),
                "gratuity": float(r[4] or 0),
                "hours": float(r[5] or 0),
                "hourlyRate": float(r[6] or 0),
                "status": r[7] or "completed"
            })
        
        cur.close()
        return work_history
    
    except Exception as e:
        logger.error(f"Error getting work history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employee-monthly-summary/{employee_id}/{year}")
async def get_employee_monthly_summary(employee_id: int, year: int, conn=Depends(get_connection)):
    """Get monthly payroll summary for employee"""
    try:
        cur = conn.cursor()
        
        monthly_data = []
        
        for month in range(1, 13):
            cur.execute("""
                SELECT 
                    COALESCE(SUM(hours), 0) as hours,
                    COALESCE(SUM(salary), 0) as salary,
                    COALESCE(SUM(bonus), 0) as bonus,
                    COALESCE(SUM(gratuity), 0) as gratuity,
                    COALESCE(SUM(base_salary + bonus + gratuity + 
                        regular_hours * hourly_rate + ot_hours * ot_rate), 0) as gross,
                    COALESCE(SUM(cpp), 0) as cpp,
                    COALESCE(SUM(ei), 0) as ei,
                    COALESCE(SUM(income_tax), 0) as tax
                FROM payroll_entries
                WHERE employee_id = %s AND year = %s AND EXTRACT(MONTH FROM created_at) = %s
            """, (employee_id, year, month))
            
            result = cur.fetchone()
            
            if result:
                hours = float(result[0] or 0)
                salary = float(result[1] or 0)
                bonus = float(result[2] or 0)
                gratuity = float(result[3] or 0)
                gross = float(result[4] or 0)
                cpp = float(result[5] or 0)
                ei = float(result[6] or 0)
                tax = float(result[7] or 0)
            else:
                hours = salary = bonus = gratuity = gross = cpp = ei = tax = 0
            
            deductions = cpp + ei + tax
            net = gross - deductions
            
            monthly_data.append({
                "period": f"{year}-{month:02d}",
                "hours": hours,
                "salary": salary,
                "bonus": bonus,
                "gratuity": gratuity,
                "gross": gross,
                "cpp": cpp,
                "ei": ei,
                "tax": tax,
                "deductions": deductions,
                "net": net
            })
        
        cur.close()
        return monthly_data
    
    except Exception as e:
        logger.error(f"Error getting monthly summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-periods/{employee_id}/{year}")
async def get_available_periods(employee_id: int, year: int, conn=Depends(get_connection)):
    """Get list of available pay periods"""
    try:
        cur = conn.cursor()
        
        # Generate standard biweekly periods for the year
        periods = []
        start_date = f"{year}-01-01"
        
        # You can customize this logic based on your actual pay period structure
        for week_num in range(1, 27):  # 26 biweekly periods
            period_str = f"P{week_num:02d} - {year}"
            periods.append(period_str)
        
        cur.close()
        return periods
    
    except Exception as e:
        logger.error(f"Error getting periods: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-match-charters")
async def auto_match_charters(payload: dict, conn=Depends(get_connection)):
    """Auto-match all unmatched charters for the employee in a period"""
    try:
        cur = conn.cursor()
        employee_id = payload.get("employee_id")
        period = payload.get("period")
        
        if not employee_id or not period:
            raise HTTPException(status_code=400, detail="Missing employee_id or period")
        
        # Find unmatched charters for employee in period
        cur.execute("""
            SELECT charter_id, charter_date, base_charge + airport_fee + COALESCE(additional_charges, 0)
            FROM charters
            WHERE assigned_driver_id = %s AND NOT EXISTS (
                SELECT 1 FROM driver_payroll 
                WHERE charter_id = charters.charter_id AND employee_id = %s
            )
            AND EXTRACT(YEAR FROM charter_date) = %s
        """, (employee_id, employee_id, int(period[:4])))
        
        charters = cur.fetchall()
        matched_count = 0
        
        for charter_id, charter_date, amount in charters:
            # Create payroll entry linking charter
            cur.execute("""
                INSERT INTO driver_payroll (
                    employee_id, charter_id, hours, gross_pay, created_at
                ) VALUES (%s, %s, 0, %s, NOW())
                ON CONFLICT DO NOTHING
            """, (employee_id, charter_id, amount))
            matched_count += 1
        
        conn.commit()
        cur.close()
        
        return {"status": "success", "matched": matched_count}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error autom matching charters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/match-charter/{charter_id}/{employee_id}")
async def match_single_charter(charter_id: int, employee_id: int, conn=Depends(get_connection)):
    """Link a single charter to an employee"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO driver_payroll (employee_id, charter_id, gross_pay, created_at)
            SELECT %s, charter_id, base_charge + airport_fee + COALESCE(additional_charges, 0), NOW()
            FROM charters WHERE charter_id = %s
            ON CONFLICT DO NOTHING
        """, (employee_id, charter_id))
        
        conn.commit()
        cur.close()
        
        return {"status": "success"}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error matching charter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/month-end-balance")
async def month_end_balance(payload: dict, conn=Depends(get_connection)):
    """Generate month-end balance report"""
    try:
        cur = conn.cursor()
        employee_id = payload.get("employee_id")
        period = payload.get("period")  # format: "2026-01"
        
        if not employee_id or not period:
            raise HTTPException(status_code=400, detail="Missing employee_id or period")
        
        year, month = period.split("-")
        
        # Get payroll data for the month
        cur.execute("""
            SELECT 
                COALESCE(SUM(hours), 0),
                COALESCE(SUM(hourly_rate * hours), 0),
                COALESCE(SUM(bonus), 0),
                COALESCE(SUM(gratuity), 0),
                COALESCE(SUM(cpp), 0),
                COALESCE(SUM(ei), 0),
                COALESCE(SUM(income_tax), 0)
            FROM payroll_entries
            WHERE employee_id = %s AND year = %s 
            AND EXTRACT(MONTH FROM created_at) = %s
        """, (employee_id, int(year), int(month)))
        
        result = cur.fetchone()
        
        charter_hours = float(result[0] or 0) if result else 0
        charter_income = float(result[1] or 0) if result else 0
        bonus = float(result[2] or 0) if result else 0
        gratuity = float(result[3] or 0) if result else 0
        cpp = float(result[4] or 0) if result else 0
        ei = float(result[5] or 0) if result else 0
        income_tax = float(result[6] or 0) if result else 0
        
        total_gross = charter_income + bonus + gratuity
        total_deductions = cpp + ei + income_tax
        net_pay = total_gross - total_deductions
        
        issues = []
        if charter_hours == 0:
            issues.append("No charters recorded for this period")
        if total_deductions > total_gross:
            issues.append("⚠️ Deductions exceed gross income")
        
        balanced = len(issues) == 0
        
        cur.close()
        
        return {
            "period": period,
            "charterHours": charter_hours,
            "charterIncome": charter_income,
            "bonus": bonus,
            "gratuity": gratuity,
            "totalGross": total_gross,
            "cpp": cpp,
            "ei": ei,
            "incomeTax": income_tax,
            "totalDeductions": total_deductions,
            "netPay": net_pay,
            "variance": 0,  # Can be calculated based on expected vs actual
            "balanced": balanced,
            "issues": issues
        }
    
    except Exception as e:
        logger.error(f"Error generating month-end balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-paystub/{employee_id}/{period}")
async def generate_paystub(employee_id: int, period: str, conn=Depends(get_connection)):
    """Generate a pay stub for an employee for a period"""
    try:
        cur = conn.cursor()
        
        # Get employee info
        cur.execute("""
            SELECT full_name, employee_id, t4_sin
            FROM employees WHERE employee_id = %s
        """, (employee_id,))
        
        emp = cur.fetchone()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Get payroll data for period
        year, month = period.split("-") if "-" in period else (period[:4], period[4:6])
        
        cur.execute("""
            SELECT 
                regular_hours, hourly_rate, bonus, gratuity,
                base_salary, cpp, ei, income_tax, pay_period
            FROM payroll_entries
            WHERE employee_id = %s AND year = %s 
            AND EXTRACT(MONTH FROM created_at) = %s
            LIMIT 1
        """, (employee_id, int(year), int(month)))
        
        payroll = cur.fetchone()
        
        if not payroll:
            raise HTTPException(status_code=404, detail="Payroll entry not found")
        
        hours = float(payroll[0] or 0)
        hourly_rate = float(payroll[1] or 0)
        bonus = float(payroll[2] or 0)
        gratuity = float(payroll[3] or 0)
        cpp = float(payroll[5] or 0)
        ei = float(payroll[6] or 0)
        income_tax = float(payroll[7] or 0)
        
        salary = hours * hourly_rate
        gross = salary + bonus + gratuity
        deductions = cpp + ei + income_tax
        net = gross - deductions
        
        cur.close()
        
        from datetime import datetime
        
        return {
            "employeeId": employee_id,
            "employeeName": emp[0],
            "sin": emp[2],
            "period": f"{year}-{month:0>2}",
            "payDate": datetime.now().date().isoformat(),
            "hours": hours,
            "hourlyRate": hourly_rate,
            "bonus": bonus,
            "gratuity": gratuity,
            "gross": gross,
            "cpp": cpp,
            "ei": ei,
            "incomeTax": income_tax,
            "deductions": deductions,
            "netPay": net
        }
    
    except Exception as e:
        logger.error(f"Error generating pay stub: {e}")
        raise HTTPException(status_code=500, detail=str(e))
