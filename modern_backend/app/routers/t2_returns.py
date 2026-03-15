"""
T2 Corporate Tax Return API Router
Endpoints for T2 return management, schedule data entry, and tax calculations
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_connection

router = APIRouter(prefix="/api/t2", tags=["T2 Corporate Tax"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TaxRatesResponse(BaseModel):
    tax_year: int
    federal_small_business_rate: float
    federal_general_rate: float
    alberta_small_business_rate: float
    alberta_general_rate: float
    small_business_limit: float
    gst_rate: float
    notes: str | None = None


class T2ReturnCreate(BaseModel):
    tax_year: int = Field(..., ge=2007, le=2030)
    corporation_name: str = Field(default="Arrow Limousine Ltd.")
    business_number: str | None = None
    fiscal_year_end: date


class T2ReturnMetadata(BaseModel):
    return_id: int
    tax_year: int
    corporation_name: str
    business_number: str | None
    fiscal_year_end: date
    status: str
    total_revenue: float | None
    total_expenses: float | None
    net_income: float | None
    taxable_income: float | None
    federal_tax: float | None
    provincial_tax: float | None
    total_tax: float | None
    created_at: datetime
    updated_at: datetime | None


class ScheduleLineItem(BaseModel):
    line_number: str
    line_description:str
    amount: float


class ScheduleDataSave(BaseModel):
    return_id: int
    schedule_number: str
    lines: list[ScheduleLineItem]


class Schedule125Data(BaseModel):
    return_id: int
    charter_revenue: float = 0
    other_revenue: float = 0
    cost_of_sales: float = 0
    salaries: float = 0
    benefits: float = 0
    rent: float = 0
    repairs: float = 0
    bad_debts: float = 0
    interest: float = 0
    insurance: float = 0
    office: float = 0
    professional_fees: float = 0
    property_tax: float = 0
    travel: float = 0
    vehicle: float = 0
    other_expenses: float = 0


class Schedule100Data(BaseModel):
    return_id: int
    cash_begin: float = 0
    cash_end: float = 0
    ar_begin: float = 0
    ar_end: float = 0
    inventory_begin: float = 0
    inventory_end: float = 0
    ppe_begin: float = 0
    ppe_end: float = 0
    ap_begin: float = 0
    ap_end: float = 0
    loans_begin: float = 0
    loans_end: float = 0
    retained_earnings_begin: float = 0
    retained_earnings_end: float = 0


class TaxCalculation(BaseModel):
    return_id: int
    taxable_income: float
    small_business_income: float


class T2ReturnUpdate(BaseModel):
    status: str | None = None
    filed_date: date | None = None
    notes: str | None = None


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/tax-rates", response_model=list[TaxRatesResponse])
async def get_tax_rates(conn=Depends(get_connection)):
    """Get corporate tax rates for all years (2007-2025)"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT tax_year, federal_small_business_rate, federal_general_rate,
                   alberta_small_business_rate, alberta_general_rate,
                   small_business_limit, gst_rate, notes
            FROM corporate_tax_rates
            ORDER BY tax_year DESC
        """)
        
        rates = []
        for row in cur.fetchall():
            rates.append(TaxRatesResponse(
                tax_year=row[0],
                federal_small_business_rate=float(row[1]),
                federal_general_rate=float(row[2]),
                alberta_small_business_rate=float(row[3]),
                alberta_general_rate=float(row[4]),
                small_business_limit=float(row[5]),
                gst_rate=float(row[6]),
                notes=row[7]
            ))
        
        return rates
    finally:
        cur.close()


@router.get("/tax-rates/{tax_year}", response_model=TaxRatesResponse)
async def get_tax_rate_by_year(tax_year: int, conn=Depends(get_connection)):
    """Get tax rates for a specific year"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT tax_year, federal_small_business_rate, federal_general_rate,
                   alberta_small_business_rate, alberta_general_rate,
                   small_business_limit, gst_rate, notes
            FROM corporate_tax_rates
            WHERE tax_year = %s
        """, (tax_year,))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Tax rates not found for {tax_year}")
        
        return TaxRatesResponse(
            tax_year=row[0],
            federal_small_business_rate=float(row[1]),
            federal_general_rate=float(row[2]),
            alberta_small_business_rate=float(row[3]),
            alberta_general_rate=float(row[4]),
            small_business_limit=float(row[5]),
            gst_rate=float(row[6]),
            notes=row[7]
        )
    finally:
        cur.close()


@router.post("/returns", response_model=T2ReturnMetadata)
async def create_t2_return(data: T2ReturnCreate, conn=Depends(get_connection)):
    """Create a new T2 return for a tax year"""
    cur = conn.cursor()
    try:
        # Check if return already exists
        cur.execute("SELECT return_id FROM t2_return_metadata WHERE tax_year = %s", (data.tax_year,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail=f"T2 return for {data.tax_year} already exists")
        
        # Create new return
        cur.execute("""
            INSERT INTO t2_return_metadata (
                tax_year, corporation_name, business_number, fiscal_year_end,
                status, created_by, created_at
            )
            VALUES (%s, %s, %s, %s, 'draft', 'web_app', NOW())
            RETURNING return_id, tax_year, corporation_name, business_number, fiscal_year_end,
                      status, total_revenue, total_expenses, net_income, taxable_income,
                      federal_tax, provincial_tax, total_tax, created_at, updated_at
        """, (data.tax_year, data.corporation_name, data.business_number, data.fiscal_year_end))
        
        row = cur.fetchone()
        conn.commit()
        
        return T2ReturnMetadata(
            return_id=row[0],
            tax_year=row[1],
            corporation_name=row[2],
            business_number=row[3],
            fiscal_year_end=row[4],
            status=row[5],
            total_revenue=float(row[6]) if row[6] else None,
            total_expenses=float(row[7]) if row[7] else None,
            net_income=float(row[8]) if row[8] else None,
            taxable_income=float(row[9]) if row[9] else None,
            federal_tax=float(row[10]) if row[10] else None,
            provincial_tax=float(row[11]) if row[11] else None,
            total_tax=float(row[12]) if row[12] else None,
            created_at=row[13],
            updated_at=row[14]
        )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()


@router.get("/returns/{tax_year}", response_model=Optional[T2ReturnMetadata])
async def get_t2_return(tax_year: int, conn=Depends(get_connection)):
    """Get T2 return for a specific tax year"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT return_id, tax_year, corporation_name, business_number, fiscal_year_end,
                   status, total_revenue, total_expenses, net_income, taxable_income,
                   federal_tax, provincial_tax, total_tax, created_at, updated_at
            FROM t2_return_metadata
            WHERE tax_year = %s
        """, (tax_year,))
        
        row = cur.fetchone()
        if not row:
            return None
        
        return T2ReturnMetadata(
            return_id=row[0],
            tax_year=row[1],
            corporation_name=row[2],
            business_number=row[3],
            fiscal_year_end=row[4],
            status=row[5],
            total_revenue=float(row[6]) if row[6] else None,
            total_expenses=float(row[7]) if row[7] else None,
            net_income=float(row[8]) if row[8] else None,
            taxable_income=float(row[9]) if row[9] else None,
            federal_tax=float(row[10]) if row[10] else None,
            provincial_tax=float(row[11]) if row[11] else None,
            total_tax=float(row[12]) if row[12] else None,
            created_at=row[13],
            updated_at=row[14]
        )
    finally:
        cur.close()


@router.post("/schedule125")
async def save_schedule_125(data: Schedule125Data, conn=Depends(get_connection)):
    """Save Schedule 125 (Income Statement) data"""
    cur = conn.cursor()
    try:
        # Calculate totals
        total_revenue = data.charter_revenue + data.other_revenue
        total_expenses = (data.cost_of_sales + data.salaries + data.benefits + 
                         data.rent + data.repairs + data.bad_debts + data.interest +
                         data.insurance + data.office + data.professional_fees +
                         data.property_tax + data.travel + data.vehicle + data.other_expenses)
        net_income = total_revenue - total_expenses
        
        # Save as schedule line items
        lines = [
            ("125", "8000", "Charter revenue", data.charter_revenue),
            ("125", "8299", "Other revenue", data.other_revenue),
            ("125", "8518", "Cost of sales", data.cost_of_sales),
            ("125", "8513", "Salaries, wages, benefits", data.salaries),
            ("125", "8523", "Employee benefits", data.benefits),
            ("125", "8690-1", "Rent", data.rent),
            ("125", "8690-2", "Repairs and maintenance", data.repairs),
            ("125", "8590", "Bad debts", data.bad_debts),
            ("125", "8711", "Interest and bank charges", data.interest),
            ("125", "9270", "Insurance", data.insurance),
            ("125", "8810", "Office expenses", data.office),
            ("125", "8860", "Professional fees", data.professional_fees),
            ("125", "9180", "Property taxes", data.property_tax),
            ("125", "9200", "Travel", data.travel),
            ("125", "9281", "Vehicle expenses", data.vehicle),
            ("125", "9923", "Other expenses", data.other_expenses),
        ]
        
        for schedule, line_num, desc, amount in lines:
            cur.execute("""
                INSERT INTO t2_schedule_data (return_id, schedule_number, line_number, line_description, amount)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (return_id, schedule_number, line_number)
                DO UPDATE SET amount = EXCLUDED.amount, updated_at = NOW()
            """, (data.return_id, schedule, line_num, desc, amount))
        
        # Update metadata
        cur.execute("""
            UPDATE t2_return_metadata
            SET total_revenue = %s, total_expenses = %s, net_income = %s,
                updated_at = NOW()
            WHERE return_id = %s
        """, (total_revenue, total_expenses, net_income, data.return_id))
        
        conn.commit()
        
        return {
            "success": True,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_income": net_income
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()


@router.get("/schedule125/{return_id}")
async def get_schedule_125(return_id: int, conn=Depends(get_connection)):
    """Get Schedule 125 data"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT line_number, amount
            FROM t2_schedule_data
            WHERE return_id = %s AND schedule_number = '125'
        """, (return_id,))
        
        data = {row[0]: float(row[1]) for row in cur.fetchall()}
        
        return {
            "charter_revenue": data.get("8000", 0),
            "other_revenue": data.get("8299", 0),
            "cost_of_sales": data.get("8518", 0),
            "salaries": data.get("8513", 0),
            "benefits": data.get("8523", 0),
            "rent": data.get("8690-1", 0),
            "repairs": data.get("8690-2", 0),
            "bad_debts": data.get("8590", 0),
            "interest": data.get("8711", 0),
            "insurance": data.get("9270", 0),
            "office": data.get("8810", 0),
            "professional_fees": data.get("8860", 0),
            "property_tax": data.get("9180", 0),
            "travel": data.get("9200", 0),
            "vehicle": data.get("9281", 0),
            "other_expenses": data.get("9923", 0)
        }
    finally:
        cur.close()


@router.post("/schedule100")
async def save_schedule_100(data: Schedule100Data, conn=Depends(get_connection)):
    """Save Schedule 100 (Balance Sheet) data"""
    cur = conn.cursor()
    try:
        lines = [
            ("100", "1000-B", "Cash - Beginning", data.cash_begin),
            ("100", "1000-E", "Cash - Ending", data.cash_end),
            ("100", "1200-B", "Accounts Receivable - Beginning", data.ar_begin),
            ("100", "1200-E", "Accounts Receivable - Ending", data.ar_end),
            ("100", "1400-B", "Inventory - Beginning", data.inventory_begin),
            ("100", "1400-E", "Inventory - Ending", data.inventory_end),
            ("100", "2000-B", "PPE - Beginning", data.ppe_begin),
            ("100", "2000-E", "PPE - Ending", data.ppe_end),
            ("100", "3000-B", "Accounts Payable - Beginning", data.ap_begin),
            ("100", "3000-E", "Accounts Payable - Ending", data.ap_end),
            ("100", "3500-B", "Loans - Beginning", data.loans_begin),
            ("100", "3500-E", "Loans - Ending", data.loans_end),
            ("100", "4000-B", "Retained Earnings - Beginning", data.retained_earnings_begin),
            ("100", "4000-E", "Retained Earnings - Ending", data.retained_earnings_end),
        ]
        
        for schedule, line_num, desc, amount in lines:
            cur.execute("""
                INSERT INTO t2_schedule_data (return_id, schedule_number, line_number, line_description, amount)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (return_id, schedule_number, line_number)
                DO UPDATE SET amount = EXCLUDED.amount, updated_at = NOW()
            """, (data.return_id, schedule, line_num, desc, amount))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()


@router.get("/schedule100/{return_id}")
async def get_schedule_100(return_id: int, conn=Depends(get_connection)):
    """Get Schedule 100 data"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT line_number, amount
            FROM t2_schedule_data
            WHERE return_id = %s AND schedule_number = '100'
        """, (return_id,))
        
        data = {row[0]: float(row[1]) for row in cur.fetchall()}
        
        return {
            "cash_begin": data.get("1000-B", 0),
            "cash_end": data.get("1000-E", 0),
            "ar_begin": data.get("1200-B", 0),
            "ar_end": data.get("1200-E", 0),
            "inventory_begin": data.get("1400-B", 0),
            "inventory_end": data.get("1400-E", 0),
            "ppe_begin": data.get("2000-B", 0),
            "ppe_end": data.get("2000-E", 0),
            "ap_begin": data.get("3000-B", 0),
            "ap_end": data.get("3000-E", 0),
            "loans_begin": data.get("3500-B", 0),
            "loans_end": data.get("3500-E", 0),
            "retained_earnings_begin": data.get("4000-B", 0),
            "retained_earnings_end": data.get("4000-E", 0)
        }
    finally:
        cur.close()


@router.post("/calculate-tax")
async def calculate_tax(data: TaxCalculation, conn=Depends(get_connection)):
    """Calculate federal and provincial tax"""
    cur = conn.cursor()
    try:
        # Get return to find tax year
        cur.execute("SELECT tax_year FROM t2_return_metadata WHERE return_id = %s", (data.return_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Return not found")
        
        tax_year = row[0]
        
        # Get tax rates
        cur.execute("""
            SELECT federal_small_business_rate, federal_general_rate,
                   alberta_small_business_rate, alberta_general_rate,
                   small_business_limit
            FROM corporate_tax_rates
            WHERE tax_year = %s
        """, (tax_year,))
        
        rates = cur.fetchone()
        if not rates:
            raise HTTPException(status_code=404, detail=f"Tax rates not found for {tax_year}")
        
        fed_sbd, fed_general, ab_sbd, ab_general, sbd_limit = rates
        
        # Calculate general income (anything above SBD limit)
        general_income = max(0, data.taxable_income - data.small_business_income)
        
        # Calculate taxes
        fed_tax_sbd = data.small_business_income * float(fed_sbd)
        fed_tax_general = general_income * float(fed_general)
        ab_tax_sbd = data.small_business_income * float(ab_sbd)
        ab_tax_general = general_income * float(ab_general)
        
        total_federal = fed_tax_sbd + fed_tax_general
        total_provincial = ab_tax_sbd + ab_tax_general
        total_tax = total_federal + total_provincial
        
        # Update return metadata
        cur.execute("""
            UPDATE t2_return_metadata
            SET taxable_income = %s,
                federal_tax = %s,
                provincial_tax = %s,
                total_tax = %s,
                status = 'calculated',
                updated_at = NOW()
            WHERE return_id = %s
        """, (data.taxable_income, total_federal, total_provincial, total_tax, data.return_id))
        
        conn.commit()
        
        return {
            "success": True,
            "taxable_income": data.taxable_income,
            "small_business_income": data.small_business_income,
            "general_income": general_income,
            "federal_tax_sbd": fed_tax_sbd,
            "federal_tax_general": fed_tax_general,
            "total_federal": total_federal,
            "provincial_tax_sbd": ab_tax_sbd,
            "provincial_tax_general": ab_tax_general,
            "total_provincial": total_provincial,
            "total_tax": total_tax
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()


@router.patch("/returns/{return_id}")
async def update_t2_return(return_id: int, data: T2ReturnUpdate, conn=Depends(get_connection)):
    """Update T2 return status or filing information"""
    cur = conn.cursor()
    try:
        updates = []
        params = []
        
        if data.status:
            updates.append("status = %s")
            params.append(data.status)
        
        if data.filed_date:
            updates.append("filed_date = %s")
            params.append(data.filed_date)
        
        if not updates:
            return {"success": True, "message": "No updates provided"}
        
        updates.append("updated_at = NOW()")
        params.append(return_id)
        
        query = f"UPDATE t2_return_metadata SET {', '.join(updates)} WHERE return_id = %s"
        cur.execute(query, params)
        
        conn.commit()
        return {"success": True, "message": "T2 return updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
