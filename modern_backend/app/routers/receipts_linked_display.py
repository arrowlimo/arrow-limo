#!/usr/bin/env python3
"""
API endpoint to retrieve linked split receipts for display
Returns all receipts that share the same banking_transaction_id or parent_receipt_id
"""

from datetime import date as date_type

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/receipts-split", tags=["receipts-split"])


class SplitReceiptDetail(BaseModel):
    receipt_id: int
    receipt_date: date_type
    vendor_name: str
    gross_amount: float
    gst_amount: float | None
    description: str | None
    vehicle_id: int | None
    vehicle_number: str | None
    fuel_amount: float | None
    banking_transaction_id: int | None
    parent_receipt_id: int | None
    gl_account_code: str | None
    is_personal: bool
    is_paper_verified: bool | None = False


@router.get("/linked/{receipt_id}")
def get_linked_split_receipts(receipt_id: int):
    """Get all receipts linked to the same split (by banking transaction or parent receipt).
    
    Returns a list of related receipts that should be displayed together.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # First, get the base receipt to find what it's linked to
        cur.execute(
            """
            SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, gross_amount,
                   gst_amount, description, vehicle_id, fuel_amount, 
                   banking_transaction_id, parent_receipt_id, gl_account_code,
                   COALESCE(owner_personal_amount, 0) > 0 as is_personal,
                   is_paper_verified
            FROM receipts
            WHERE receipt_id = %s
            """,
            (receipt_id,),
        )
        
        base_receipt = cur.fetchone()
        if not base_receipt:
            raise HTTPException(status_code=404, detail=f"Receipt {receipt_id} not found")
        
        banking_id = base_receipt[9]  # banking_transaction_id
        parent_id = base_receipt[10]  # parent_receipt_id
        
        # Find all related receipts:
        # 1. Same banking transaction
        # 2. Same parent receipt ID (if marked as split parent)
        # 3. This receipt is the parent for others
        
        cur.execute(
            """
            SELECT DISTINCT r.receipt_id, r.receipt_date, r.vendor_name, r.canonical_vendor,
                   r.gross_amount, r.gst_amount, r.description, r.vehicle_id, r.fuel_amount,
                   r.banking_transaction_id, r.parent_receipt_id, r.gl_account_code,
                   COALESCE(r.owner_personal_amount, 0) > 0 as is_personal,
                   v.vehicle_number, r.is_paper_verified
            FROM receipts r
            LEFT JOIN vehicles v ON r.vehicle_id = v.vehicle_id
            WHERE 
                (r.banking_transaction_id = %s AND r.banking_transaction_id IS NOT NULL)
                OR (r.parent_receipt_id = %s AND r.parent_receipt_id IS NOT NULL)
                OR (r.receipt_id = %s AND (
                    EXISTS (SELECT 1 FROM receipts r2 WHERE r2.parent_receipt_id = r.receipt_id)
                    OR EXISTS (SELECT 1 FROM receipts r2 WHERE r2.banking_transaction_id = r.banking_transaction_id)
                ))
            ORDER BY r.gross_amount DESC, r.receipt_date ASC
            """,
            (banking_id, parent_id, receipt_id),
        )
        
        receipts = []
        total_gross = 0
        total_gst = 0
        
        for row in cur.fetchall():
            gross = float(row[4]) if row[4] else 0
            gst = float(row[5]) if row[5] else 0
            fuel = float(row[8]) if row[8] else None
            
            receipts.append({
                "receipt_id": row[0],
                "receipt_date": row[1],
                "vendor_name": row[2],
                "canonical_vendor": row[3],
                "gross_amount": gross,
                "gst_amount": gst,
                "description": row[6],
                "vehicle_id": row[7],
                "vehicle_number": row[13],
                "fuel_amount": fuel,
                "banking_transaction_id": row[9],
                "parent_receipt_id": row[10],
                "gl_account_code": row[11],
                "is_personal": bool(row[12]),
                "is_paper_verified": bool(row[14]) if row[14] is not None else False,
            })
            
            total_gross += gross
            total_gst += gst
        
        cur.close()
        conn.close()
        
        return {
            "count": len(receipts),
            "is_split": len(receipts) > 1,
            "total_gross": total_gross,
            "total_gst": total_gst,
            "receipts": receipts,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch linked receipts: {e!s}"
        )


@router.get("/by-banking/{transaction_id}")
def get_receipts_by_banking_transaction(transaction_id: int):
    """Get all receipts linked to a specific banking transaction."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.canonical_vendor,
                   r.gross_amount, r.gst_amount, r.description, r.vehicle_id, r.fuel_amount,
                   r.banking_transaction_id, r.gl_account_code,
                   COALESCE(r.owner_personal_amount, 0) > 0 as is_personal,
                   v.vehicle_number, r.is_paper_verified
            FROM receipts r
            LEFT JOIN vehicles v ON r.vehicle_id = v.vehicle_id
            WHERE r.banking_transaction_id = %s
            ORDER BY r.gross_amount DESC, r.receipt_date ASC
            """,
            (transaction_id,),
        )
        
        receipts = []
        total_gross = 0
        total_gst = 0
        
        for row in cur.fetchall():
            gross = float(row[4]) if row[4] else 0
            gst = float(row[5]) if row[5] else 0
            fuel = float(row[8]) if row[8] else None
            
            receipts.append({
                "receipt_id": row[0],
                "receipt_date": row[1],
                "vendor_name": row[2],
                "canonical_vendor": row[3],
                "gross_amount": gross,
                "gst_amount": gst,
                "description": row[6],
                "vehicle_id": row[7],
                "vehicle_number": row[12],
                "fuel_amount": fuel,
                "banking_transaction_id": row[9],
                "gl_account_code": row[10],
                "is_personal": bool(row[11]),
                "is_paper_verified": bool(row[13]) if row[13] is not None else False,
            })
            
            total_gross += gross
            total_gst += gst
        
        cur.close()
        conn.close()
        
        return {
            "count": len(receipts),
            "is_split": len(receipts) > 1,
            "total_gross": total_gross,
            "total_gst": total_gst,
            "receipts": receipts,
        }
    
    except Exception as e:
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch receipts: {e!s}"
        )
