"""Receipts and Expenses API Router"""
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from ..db import get_connection

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


# Pydantic Models
class SplitComponent(BaseModel):
    amount: Decimal
    category: str
    description: Optional[str] = None
    is_personal: bool = False


class ReceiptCreate(BaseModel):
    date: date
    vendor: str
    amount: Decimal
    gst: Optional[Decimal] = None
    category: Optional[str] = None
    gl_account_code: Optional[str] = None
    description: Optional[str] = None
    vehicle_id: Optional[int] = None
    payment_method: Optional[str] = None
    banking_transaction_id: Optional[int] = None


class ReceiptUpdate(BaseModel):
    date: Optional[date] = None
    vendor: Optional[str] = None
    amount: Optional[Decimal] = None
    gst: Optional[Decimal] = None
    gl_account_code: Optional[str] = None
    category: Optional[str] = None  # Deprecated, use gl_account_code
    description: Optional[str] = None
    vehicle_id: Optional[int] = None


class ReceiptResponse(BaseModel):
    receipt_id: int
    date: date
    vendor: str
    amount: Decimal
    gst: Optional[Decimal]
    gl_account_code: Optional[str]
    category: Optional[str] = None  # Deprecated, use gl_account_code
    description: Optional[str]
    vehicle_id: Optional[int]
    payment_method: Optional[str]
    banking_transaction_id: Optional[int]
    created_at: Optional[datetime]


class ExpenseSummary(BaseModel):
    gl_account_code: str
    count: int
    total_amount: Decimal
    total_gst: Decimal


@router.get("/vendors")
def get_vendors():
    """Get distinct list of vendor names for autocomplete"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT vendor_name 
        FROM receipts 
        WHERE vendor_name IS NOT NULL AND vendor_name != ''
        ORDER BY vendor_name
    """)
    
    vendors = [row[0] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return vendors


@router.get("/categories")
def get_categories():
    """Get list of available expense categories"""
    return [
        {"value": "fuel", "label": "Fuel"},
        {"value": "maintenance", "label": "Vehicle Maintenance"},
        {"value": "insurance", "label": "Insurance"},
        {"value": "office", "label": "Office Supplies"},
        {"value": "meals", "label": "Meals & Entertainment"},
        {"value": "client_beverages", "label": "Client Beverages"},
        {"value": "client_supplies", "label": "Client Supplies"},
        {"value": "client_food", "label": "Client Food"},
        {"value": "professional", "label": "Professional Services"},
        {"value": "personal", "label": "Personal Purchase"},
        {"value": "rebate", "label": "Rebate/Discount"},
        {"value": "cash", "label": "Cash Payment"},
        {"value": "card", "label": "Card Payment"},
        {"value": "utilities", "label": "Utilities"},
        {"value": "rent", "label": "Rent"},
        {"value": "wages", "label": "Wages"},
        {"value": "other", "label": "Other"}
    ]


@router.get("/")
def get_receipts(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get receipts with optional filters"""
    conn = get_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            receipt_id, receipt_date, vendor_name, gross_amount, gst_amount,
            gl_account_code, category, description, vehicle_id,
            payment_method, banking_transaction_id, created_at
        FROM receipts
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND receipt_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND receipt_date <= %s"
        params.append(end_date)
    if vendor:
        query += " AND vendor_name ILIKE %s"
        params.append(f"%{vendor}%")
    if category:
        query += " AND category = %s"
        params.append(category)
    
    query += " ORDER BY receipt_date DESC, receipt_id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cur.execute(query, params)
    
    receipts = []
    for row in cur.fetchall():
        receipts.append({
            "receipt_id": row[0],
            "date": row[1],
            "vendor": row[2],
            "amount": float(row[3]) if row[3] else 0,
            "gst": float(row[4]) if row[4] else None,
            "gl_account_code": row[5],
            "category": row[6],
            "description": row[7],
            "vehicle_id": row[8],
            "payment_method": row[9],
            "banking_transaction_id": row[10],
            "created_at": row[11]
        })
    
    cur.close()
    conn.close()
    
    return receipts


@router.get("/{receipt_id}")
def get_receipt(receipt_id: int):
    """Get single receipt"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Get receipt
    cur.execute("""
        SELECT 
            receipt_id, receipt_date, vendor_name, gross_amount, gst_amount,
            gl_account_code, category, description, vehicle_id,
            payment_method, banking_transaction_id, created_at
        FROM receipts
        WHERE receipt_id = %s
    """, (receipt_id,))
    
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    receipt = {
        "receipt_id": row[0],
        "date": row[1],
        "vendor": row[2],
        "amount": float(row[3]) if row[3] else 0,
        "gst": float(row[4]) if row[4] else None,
        "gl_account_code": row[5],
        "category": row[6],
        "description": row[7],
        "vehicle_id": row[8],
        "payment_method": row[9],
        "banking_transaction_id": row[10],
        "created_at": row[11]
    }
    
    cur.close()
    conn.close()
    
    return receipt


@router.post("/", status_code=201)
def create_receipt(receipt: ReceiptCreate):
    """Create new receipt"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Create receipt
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, gst_amount, gl_account_code,
                category, description, vehicle_id, payment_method,
                banking_transaction_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING receipt_id
        """, (
            receipt.date, receipt.vendor, receipt.amount, receipt.gst,
            receipt.gl_account_code or receipt.category, receipt.category, 
            receipt.description, receipt.vehicle_id,
            receipt.payment_method, receipt.banking_transaction_id
        ))
        
        receipt_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {"receipt_id": receipt_id, "message": "Receipt created successfully"}
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to create receipt: {str(e)}")


@router.put("/{receipt_id}")
def update_receipt(receipt_id: int, receipt: ReceiptUpdate):
    """Update existing receipt"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Build dynamic update query
        updates = []
        params = []
        
        if receipt.date is not None:
            updates.append("receipt_date = %s")
            params.append(receipt.date)
        if receipt.vendor is not None:
            updates.append("vendor = %s")
            params.append(receipt.vendor)
        if receipt.amount is not None:
            updates.append("amount = %s")
            params.append(receipt.amount)
        if receipt.gst is not None:
            updates.append("gst_amount = %s")
            params.append(receipt.gst)
        if receipt.category is not None:
            updates.append("category = %s")
            params.append(receipt.category)
        if receipt.description is not None:
            updates.append("description = %s")
            params.append(receipt.description)
        if receipt.vehicle_id is not None:
            updates.append("vehicle_id = %s")
            params.append(receipt.vehicle_id)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # AUTO-VERIFY: Mark receipt as verified when edited
        updates.append("verified_by_edit = TRUE")
        updates.append("verified_at = NOW()")
        updates.append("verified_by_user = %s")
        params.append("api_user")  # Can be overridden if user auth is implemented
        
        params.append(receipt_id)
        query = f"UPDATE receipts SET {', '.join(updates)} WHERE receipt_id = %s"
        
        cur.execute(query, params)
        
        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"message": "Receipt updated successfully (auto-verified)"}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to update receipt: {str(e)}")


@router.delete("/{receipt_id}")
def delete_receipt(receipt_id: int):
    """Delete receipt"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Delete receipt
        cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
        
        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"message": "Receipt deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to delete receipt: {str(e)}")


@router.get("/summary/by-category")
def get_expense_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """Get expense summary grouped by category"""
    conn = get_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            COALESCE(category, 'Uncategorized') as category,
            COUNT(*) as count,
            SUM(amount) as total_amount,
            SUM(COALESCE(gst_amount, 0)) as total_gst
        FROM receipts
        WHERE parent_receipt_id IS NULL
    """
    params = []
    
    if start_date:
        query += " AND receipt_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND receipt_date <= %s"
        params.append(end_date)
    
    query += " GROUP BY category ORDER BY total_amount DESC"
    
    cur.execute(query, params)
    
    summary = []
    for row in cur.fetchall():
        summary.append({
            "category": row[0],
            "count": row[1],
            "total_amount": float(row[2]) if row[2] else 0,
            "total_gst": float(row[3]) if row[3] else 0
        })
    
    cur.close()
    conn.close()
    
    return summary

