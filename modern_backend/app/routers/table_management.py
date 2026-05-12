"""
FastAPI Router for Table Management
Provides CRUD endpoints for master data tables
"""

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import cursor, get_connection

router = APIRouter(prefix="/api/table-management", tags=["table-management"])


def _service_actor() -> AuditEventActor:
    return AuditEventActor(
        actor_type="service",
        user_id=None,
        username="table_management_api",
        role="service",
    )


def _record_table_event(conn, action: str, rows_saved: int) -> None:
    record_audit_event(
        conn,
        AuditEvent(
            module="table_management",
            entity_type="master_table",
            entity_id=action,
            action=action,
            source="api",
            correlation_id=None,
            actor=_service_actor(),
            before=None,
            after={"rows_saved": rows_saved},
            evidence_links=[],
            retention_until=date(date.today().year + 6, 12, 31),
            note="Master table upsert",
        ),
        ensure_storage=False,
        commit=False,
    )


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
    item_id: int | None = None
    item_name: str
    category: str | None = None
    unit_price: float = 0.0
    our_cost: float = 0.0
    deposit_amount: float = 0.0
    stock_quantity: int | None = None
    description: str | None = None


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
def save_chart_of_accounts(data: list[ChartOfAccountRow]):
    """Save chart of accounts (upsert)"""
    conn = get_connection()
    try:
        ensure_audit_storage(conn)
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
        _record_table_event(conn, "save_chart_of_accounts", len(data))
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


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
def save_receipt_categories(data: list[ReceiptCategoryRow]):
    """Save receipt categories (upsert)"""
    conn = get_connection()
    try:
        ensure_audit_storage(conn)
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
        _record_table_event(conn, "save_receipt_categories", len(data))
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


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
def save_charter_types(data: list[CharterTypeRow]):
    """Save charter types (upsert)"""
    conn = get_connection()
    try:
        ensure_audit_storage(conn)
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
        _record_table_event(conn, "save_charter_types", len(data))
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


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
def save_vehicle_pricing(data: list[VehiclePricingRow]):
    """Save vehicle pricing defaults (upsert)"""
    conn = get_connection()
    try:
        ensure_audit_storage(conn)
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
        _record_table_event(conn, "save_vehicle_pricing", len(data))
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


# ========== BEVERAGES ==========


@router.get("/beverages")
def get_beverages():
    """Get all beverages from beverage_products"""
    with cursor() as cur:
        cur.execute(
            """
            SELECT item_id, item_name, category, unit_price,
                   our_cost, deposit_amount, stock_quantity, description
            FROM beverage_products
            ORDER BY category, item_name
        """
        )
        rows = cur.fetchall()
        return [
            {
                "item_id": r[0],
                "item_name": r[1],
                "category": r[2],
                "unit_price": float(r[3]) if r[3] else 0.0,
                "our_cost": float(r[4]) if r[4] else 0.0,
                "deposit_amount": float(r[5]) if r[5] else 0.0,
                "stock_quantity": r[6] if r[6] else 0,
                "description": r[7],
            }
            for r in rows
        ]


@router.post("/beverages")
def save_beverages(data: list[BeverageRow]):
    """Save beverages to beverage_products (upsert)"""
    conn = get_connection()
    try:
        ensure_audit_storage(conn)
        with conn.cursor() as cur:
            for row in data:
                if not row.item_name:
                    continue

                if row.item_id:
                    # Update existing
                    cur.execute(
                        """
                        UPDATE beverage_products SET
                            item_name = %s, category = %s, unit_price = %s,
                            our_cost = %s, deposit_amount = %s,
                            stock_quantity = %s, description = %s
                        WHERE item_id = %s
                    """,
                        (
                            row.item_name,
                            row.category,
                            row.unit_price,
                            row.our_cost,
                            row.deposit_amount,
                            row.stock_quantity,
                            row.description,
                            row.item_id,
                        ),
                    )
                else:
                    # Insert new
                    cur.execute(
                        """
                        INSERT INTO beverage_products (
                            item_name,
                            category,
                            unit_price,
                            our_cost,
                            deposit_amount,
                            stock_quantity,
                            description)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            row.item_name,
                            row.category,
                            row.unit_price,
                            row.our_cost,
                            row.deposit_amount,
                            row.stock_quantity,
                            row.description,
                        ),
                    )
        _record_table_event(conn, "save_beverages", len(data))
        conn.commit()
        return {"status": "success", "rows_saved": len(data)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
