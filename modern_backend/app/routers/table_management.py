"""
FastAPI Router for Table Management
Provides CRUD endpoints for master data tables
"""

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import cursor, get_connection

router = APIRouter(prefix="/api/table-management", tags=["table-management"])


# ========== MODELS ==========


class ChartOfAccountRow(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    is_tax_applicable: bool = False
    is_business_expense: bool = False
    is_linked_account: bool = False
    requires_vehicle: bool = False
    requires_employee: bool = False
    is_active: bool = True


class ReceiptCategoryRow(BaseModel):
    category_code: str
    category_name: str
    gl_account_code: str | None = None
    is_tax_deductible: bool = False
    is_business_expense: bool = False
    requires_vehicle: bool = False
    requires_employee: bool = False


class CharterTypeRow(BaseModel):
    type_code: str
    type_name: str
    display_order: int = 0
    is_active: bool = True


class VehiclePricingRow(BaseModel):
    vehicle_type: str
    charter_type_code: str | None = None
    hourly_rate: float = 0.0
    package_rate: float = 0.0
    package_hours: float = 0.0
    extra_time_rate: float = 0.0
    standby_rate: float = 0.0
    is_active: bool = True


class BeverageRow(BaseModel):
    beverage_id: int | None = None
    name: str
    category: str | None = None
    price: float = 0.0
    stock_quantity: int = 0
    is_active: bool = True


# ========== CHART OF ACCOUNTS ==========


@router.get("/chart-of-accounts")
def get_chart_of_accounts():
    """Get all chart of accounts entries"""
    with cursor() as cur:
        cur.execute(
            """
            SELECT account_code, account_name, account_type,
                   is_tax_applicable, is_business_expense, is_linked_account,
                   requires_vehicle, requires_employee, is_active
            FROM chart_of_accounts
            ORDER BY account_code
        """
        )
        rows = cur.fetchall()
        return [
            {
                "account_code": r[0],
                "account_name": r[1],
                "account_type": r[2],
                "is_tax_applicable": r[3],
                "is_business_expense": r[4],
                "is_linked_account": r[5],
                "requires_vehicle": r[6],
                "requires_employee": r[7],
                "is_active": r[8],
            }
            for r in rows
        ]


@router.post("/chart-of-accounts")
def save_chart_of_accounts(data: List[ChartOfAccountRow]):
    """Save chart of accounts (upsert)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in data:
                if not row.account_code or not row.account_name:
                    continue

                cur.execute(
                    """
                    INSERT INTO chart_of_accounts (
                        account_code,
                        account_name,
                        account_type,
                        is_tax_applicable,
                        is_business_expense,
                        is_linked_account,
                        requires_vehicle,
                        requires_employee,
                        is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (account_code) DO UPDATE SET
                        account_name = EXCLUDED.account_name,
                        account_type = EXCLUDED.account_type,
                        is_tax_applicable = EXCLUDED.is_tax_applicable,
                        is_business_expense = EXCLUDED.is_business_expense,
                        is_linked_account = EXCLUDED.is_linked_account,
                        requires_vehicle = EXCLUDED.requires_vehicle,
                        requires_employee = EXCLUDED.requires_employee,
                        is_active = EXCLUDED.is_active
                """,
                    (
                        row.account_code,
                        row.account_name,
                        row.account_type,
                        row.is_tax_applicable,
                        row.is_business_expense,
                        row.is_linked_account,
                        row.requires_vehicle,
                        row.requires_employee,
                        row.is_active,
                    ),
                )
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== RECEIPT CATEGORIES ==========


@router.get("/receipt-categories")
def get_receipt_categories():
    """Get all receipt categories"""
    with cursor() as cur:
        cur.execute(
            """
            SELECT category_code, category_name, gl_account_code,
                   is_tax_deductible, is_business_expense,
                   requires_vehicle, requires_employee
            FROM receipt_categories
            ORDER BY category_code
        """
        )
        rows = cur.fetchall()
        return [
            {
                "category_code": r[0],
                "category_name": r[1],
                "gl_account_code": r[2],
                "is_tax_deductible": r[3],
                "is_business_expense": r[4],
                "requires_vehicle": r[5],
                "requires_employee": r[6],
            }
            for r in rows
        ]


@router.post("/receipt-categories")
def save_receipt_categories(data: List[ReceiptCategoryRow]):
    """Save receipt categories (upsert)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in data:
                if not row.category_code or not row.category_name:
                    continue

                cur.execute(
                    """
                    INSERT INTO receipt_categories (
                        category_code,
                        category_name,
                        gl_account_code,
                        is_tax_deductible,
                        is_business_expense,
                        requires_vehicle,
                        requires_employee)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (category_code) DO UPDATE SET
                        category_name = EXCLUDED.category_name,
                        gl_account_code = EXCLUDED.gl_account_code,
                        is_tax_deductible = EXCLUDED.is_tax_deductible,
                        is_business_expense = EXCLUDED.is_business_expense,
                        requires_vehicle = EXCLUDED.requires_vehicle,
                        requires_employee = EXCLUDED.requires_employee
                """,
                    (
                        row.category_code,
                        row.category_name,
                        row.gl_account_code,
                        row.is_tax_deductible,
                        row.is_business_expense,
                        row.requires_vehicle,
                        row.requires_employee,
                    ),
                )
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== CHARTER TYPES ==========


@router.get("/charter-types")
def get_charter_types():
    """Get all charter types"""
    with cursor() as cur:
        cur.execute(
            """
            SELECT type_code, type_name, display_order, is_active
            FROM charter_types
            ORDER BY display_order, type_code
        """
        )
        rows = cur.fetchall()
        return [
            {
                "type_code": r[0],
                "type_name": r[1],
                "display_order": r[2],
                "is_active": r[3],
            }
            for r in rows
        ]


@router.post("/charter-types")
def save_charter_types(data: List[CharterTypeRow]):
    """Save charter types (upsert)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in data:
                if not row.type_code or not row.type_name:
                    continue

                cur.execute(
                    """
                    INSERT INTO charter_types (
                        type_code,
                        type_name,
                        display_order,
                        is_active)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (type_code) DO UPDATE SET
                        type_name = EXCLUDED.type_name,
                        display_order = EXCLUDED.display_order,
                        is_active = EXCLUDED.is_active
                """,
                    (
                        row.type_code,
                        row.type_name,
                        row.display_order,
                        row.is_active,
                    ),
                )
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== VEHICLE PRICING ==========


@router.get("/vehicle-pricing")
def get_vehicle_pricing():
    """Get all vehicle pricing defaults"""
    with cursor() as cur:
        cur.execute(
            """
            SELECT vehicle_type, charter_type_code, hourly_rate, package_rate,
                   package_hours, extra_time_rate, standby_rate, is_active
            FROM vehicle_pricing_defaults
            ORDER BY vehicle_type, charter_type_code
        """
        )
        rows = cur.fetchall()
        return [
            {
                "vehicle_type": r[0],
                "charter_type_code": r[1],
                "hourly_rate": float(r[2]) if r[2] else 0.0,
                "package_rate": float(r[3]) if r[3] else 0.0,
                "package_hours": float(r[4]) if r[4] else 0.0,
                "extra_time_rate": float(r[5]) if r[5] else 0.0,
                "standby_rate": float(r[6]) if r[6] else 0.0,
                "is_active": r[7],
            }
            for r in rows
        ]


@router.post("/vehicle-pricing")
def save_vehicle_pricing(data: List[VehiclePricingRow]):
    """Save vehicle pricing defaults (upsert)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in data:
                if not row.vehicle_type:
                    continue

                cur.execute(
                    """
                    INSERT INTO vehicle_pricing_defaults (
                        vehicle_type,
                        charter_type_code,
                        hourly_rate,
                        package_rate,
                        package_hours,
                        extra_time_rate,
                        standby_rate,
                        is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vehicle_type, charter_type_code) DO UPDATE SET
                        hourly_rate = EXCLUDED.hourly_rate,
                        package_rate = EXCLUDED.package_rate,
                        package_hours = EXCLUDED.package_hours,
                        extra_time_rate = EXCLUDED.extra_time_rate,
                        standby_rate = EXCLUDED.standby_rate,
                        is_active = EXCLUDED.is_active
                """,
                    (
                        row.vehicle_type,
                        row.charter_type_code,
                        row.hourly_rate,
                        row.package_rate,
                        row.package_hours,
                        row.extra_time_rate,
                        row.standby_rate,
                        row.is_active,
                    ),
                )
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ========== BEVERAGES ==========


@router.get("/beverages")
def get_beverages():
    """Get all beverages"""
    with cursor() as cur:
        cur.execute(
            """
            SELECT beverage_id, name, category, price,
                   stock_quantity, is_active
            FROM beverages
            ORDER BY category, name
        """
        )
        rows = cur.fetchall()
        return [
            {
                "beverage_id": r[0],
                "name": r[1],
                "category": r[2],
                "price": float(r[3]) if r[3] else 0.0,
                "stock_quantity": r[4] if r[4] else 0,
                "is_active": r[5],
            }
            for r in rows
        ]


@router.post("/beverages")
def save_beverages(data: List[BeverageRow]):
    """Save beverages (upsert)"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for row in data:
                if not row.name:
                    continue

                if row.beverage_id:
                    # Update existing
                    cur.execute(
                        """
                        UPDATE beverages SET
                            name = %s, category = %s, price = %s,
                            stock_quantity = %s, is_active = %s
                        WHERE beverage_id = %s
                    """,
                        (
                            row.name,
                            row.category,
                            row.price,
                            row.stock_quantity,
                            row.is_active,
                            row.beverage_id,
                        ),
                    )
                else:
                    # Insert new
                    cur.execute(
                        """
                        INSERT INTO beverages (
                            name,
                            category,
                            price,
                            stock_quantity,
                            is_active)
                        VALUES (%s, %s, %s, %s, %s)
                    """,
                        (
                            row.name,
                            row.category,
                            row.price,
                            row.stock_quantity,
                            row.is_active,
                        ),
                    )
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
