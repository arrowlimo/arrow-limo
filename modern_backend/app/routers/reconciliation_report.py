"""
Banking-Receipt Reconciliation Report with two-way linking and editing
Displays all banking transactions linked to receipts with easy editing
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..database import get_connection

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])
logger = logging.getLogger(__name__)


class ReconciliationLine(BaseModel):
    """Single reconciliation line: banking + linked receipt(s)"""
    id: int
    transaction_date: date
    banking_amount: float
    banking_description: str
    banking_id: int
    # Receipt side
    receipt_id: int | None = None
    receipt_vendor: str | None = None
    receipt_total: float | None = None
    receipt_gst: float | None = None
    receipt_pst: float | None = None
    receipt_category: str | None = None
    receipt_gl_code: str | None = None
    receipt_type: str | None = None  # BUSINESS or PERSONAL
    # Linking
    linked: bool
    discrepancy: float | None = None  # amount difference


class BankingReceiptReport(BaseModel):
    """Full report with all reconciliation lines"""
    count: int
    total_banking: float
    total_receipts: float
    linked_count: int
    unlinked_count: int
    lines: list[ReconciliationLine]


@router.get("/banking-receipt-report")
async def get_banking_receipt_reconciliation(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    unlinked_only: bool = False,
    conn=Depends(get_connection)
):
    """
    Get comprehensive reconciliation report:
    All banking transactions with linked receipts side-by-side
    Sortable by any column, easily editable inline
    """
    try:
        cur = conn.cursor()
        
        # Get unified view: banking left-joined to receipts
        query = """
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                COALESCE(bt.debit_amount, 0) as banking_amount,
                COALESCE(bt.credit_amount, 0) as banking_credit,
                bt.description,
                r.receipt_id,
                r.vendor_name,
                r.amount as receipt_total,
                r.gst_amount,
                r.pst_amount,
                r.category,
                r.gl_code,
                r.receipt_type,
                CASE WHEN r.receipt_id IS NOT NULL THEN 1 ELSE 0 END as linked,
                CASE WHEN r.receipt_id IS NOT NULL 
                     THEN ABS((COALESCE(bt.debit_amount, 0) + COALESCE(bt.credit_amount, 0)) - COALESCE(r.amount, 0))
                     ELSE NULL END as discrepancy
            FROM banking_transactions bt
            LEFT JOIN receipts r ON bt.transaction_id = r.banking_transaction_id
            WHERE bt.transaction_date >= %s 
              AND bt.transaction_date <= %s
        """
        
        params = [start_date, end_date]
        
        if unlinked_only:
            query += " AND r.receipt_id IS NULL"
        
        query += " ORDER BY bt.transaction_date DESC, bt.transaction_id"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        lines = []
        total_banking = 0
        total_receipts = 0
        linked_count = 0
        
        for row in rows:
            tx_id = row[0]
            tx_date = row[1]
            banking_debit = float(row[2] or 0)
            banking_credit = float(row[3] or 0)
            banking_amount = banking_debit if banking_debit > 0 else banking_credit
            tx_desc = row[4]
            
            receipt_id = row[5]
            receipt_vendor = row[6]
            receipt_total = float(row[7] or 0)
            receipt_gst = float(row[8] or 0)
            receipt_pst = float(row[9] or 0)
            receipt_category = row[10]
            receipt_gl = row[11]
            receipt_type = row[12]
            is_linked = row[13]
            discrepancy = float(row[14] or 0) if row[14] else None
            
            total_banking += banking_amount
            if receipt_total:
                total_receipts += receipt_total
            if is_linked:
                linked_count += 1
            
            lines.append(ReconciliationLine(
                id=tx_id,
                transaction_date=tx_date,
                banking_amount=banking_amount,
                banking_description=tx_desc,
                banking_id=tx_id,
                receipt_id=receipt_id,
                receipt_vendor=receipt_vendor,
                receipt_total=receipt_total,
                receipt_gst=receipt_gst,
                receipt_pst=receipt_pst,
                receipt_category=receipt_category,
                receipt_gl_code=receipt_gl,
                receipt_type=receipt_type,
                linked=bool(is_linked),
                discrepancy=discrepancy
            ))
        
        cur.close()
        
        unlinked_count = len([l for l in lines if not l.linked])
        
        return BankingReceiptReport(
            count=len(lines),
            total_banking=round(total_banking, 2),
            total_receipts=round(total_receipts, 2),
            linked_count=linked_count,
            unlinked_count=unlinked_count,
            lines=lines
        )
        
    except Exception as e:
        logger.error(f"Error generating reconciliation report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/link-banking-receipt")
async def link_banking_to_receipt(
    banking_id: int,
    receipt_id: int,
    conn=Depends(get_connection)
):
    """Link a banking transaction to a receipt"""
    try:
        cur = conn.cursor()
        
        # Update receipt with banking link
        cur.execute("""
            UPDATE receipts
            SET banking_transaction_id = %s
            WHERE receipt_id = %s
        """, (banking_id, receipt_id))
        
        conn.commit()
        cur.close()
        
        return {"status": "success", "message": f"Linked receipt {receipt_id} to banking tx {banking_id}"}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error linking banking to receipt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update-receipt-inline")
async def update_receipt_field(
    receipt_id: int,
    field: str,
    value: str,
    conn=Depends(get_connection)
):
    """Update a receipt field inline from report"""
    try:
        allowed_fields = ['vendor_name', 'category', 'gl_code', 'receipt_type', 'gst_amount', 'pst_amount']
        
        if field not in allowed_fields:
            raise ValueError(f"Field {field} not allowed")
        
        cur = conn.cursor()
        
        # Convert value type if needed
        if field in ['gst_amount', 'pst_amount']:
            value = float(value)
        
        update_sql = f"""
            UPDATE receipts
            SET {field} = %s
            WHERE receipt_id = %s
        """
        
        cur.execute(update_sql, (value, receipt_id))
        conn.commit()
        cur.close()
        
        return {"status": "success", "message": f"Updated {field} to {value}"}
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating receipt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unlinked-banking")
async def get_unlinked_banking(
    start_date: str = Query(...),
    end_date: str = Query(...),
    conn=Depends(get_connection)
):
    """Get all unlinked banking transactions"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                COALESCE(debit_amount, 0) + COALESCE(credit_amount, 0) as amount,
                vendor_extracted
            FROM banking_transactions
            WHERE transaction_date >= %s 
              AND transaction_date <= %s
              AND transaction_id NOT IN (
                  SELECT banking_transaction_id 
                  FROM receipts 
                  WHERE banking_transaction_id IS NOT NULL
              )
            ORDER BY transaction_date DESC
        """, (start_date, end_date))
        
        rows = cur.fetchall()
        cur.close()
        
        results = [
            {
                "banking_id": r[0],
                "date": str(r[1]),
                "description": r[2],
                "amount": float(r[3]),
                "vendor": r[4]
            }
            for r in rows
        ]
        
        return results
    
    except Exception as e:
        logger.error(f"Error getting unlinked banking: {e}")
        raise HTTPException(status_code=500, detail=str(e))
