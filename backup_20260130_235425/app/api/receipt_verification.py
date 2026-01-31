#!/usr/bin/env python3
"""
API endpoints for physical receipt verification.
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import os
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter(prefix="/api/receipts/verification", tags=["receipt_verification"])

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REDACTED***")
    )

@router.get("/summary")
async def get_verification_summary():
    """Get overall verification statistics."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM receipt_verification_summary;
        """)
        result = cur.fetchone()
        return {
            "total_receipts": result['total_receipts'],
            "verified_count": result['physically_verified_count'],
            "unverified_count": result['unverified_count'],
            "verification_percentage": float(result['verification_percentage'] or 0)
        }
    finally:
        cur.close()
        conn.close()

@router.get("/by-year")
async def get_verification_by_year():
    """Get verification stats by year."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
              EXTRACT(YEAR FROM receipt_date)::INT as year,
              COUNT(*) as total,
              SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) as verified,
              ROUND(100.0 * SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) / 
                    NULLIF(COUNT(*), 0), 1) as percentage
            FROM receipts
            WHERE business_personal != 'personal' 
              AND is_personal_purchase = FALSE
            GROUP BY EXTRACT(YEAR FROM receipt_date)
            ORDER BY year;
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

@router.get("/unverified")
async def get_unverified_receipts(
    year: int = Query(None),
    limit: int = Query(100, le=1000)
):
    """Get unverified receipts."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        where = "r.is_paper_verified = FALSE AND r.business_personal != 'personal' AND r.is_personal_purchase = FALSE"
        if year:
            where += f" AND EXTRACT(YEAR FROM r.receipt_date) = {year}"
        
        cur.execute(f"""
            SELECT 
              r.receipt_id,
              r.receipt_date,
              r.vendor_name,
              r.gross_amount,
              r.category,
              r.banking_transaction_id,
              CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'Linked to banking' ELSE 'Not linked' END as status
            FROM receipts r
            WHERE {where}
            ORDER BY r.receipt_date DESC
            LIMIT {limit};
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

@router.post("/verify/{receipt_id}")
async def mark_receipt_verified(receipt_id: int, verified_by: str = Query(default="system")):
    """Mark a receipt as physically verified."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE receipts
            SET 
              is_paper_verified = TRUE,
              paper_verification_date = CURRENT_TIMESTAMP,
              verified_by_user = %s
            WHERE receipt_id = %s
            RETURNING receipt_id, receipt_date, vendor_name, gross_amount;
        """, (verified_by, receipt_id))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        conn.commit()
        return {
            "receipt_id": result[0],
            "receipt_date": str(result[1]),
            "vendor_name": result[2],
            "gross_amount": float(result[3]),
            "status": "verified"
        }
    finally:
        cur.close()
        conn.close()

@router.post("/unverify/{receipt_id}")
async def mark_receipt_unverified(receipt_id: int):
    """Mark a receipt as not verified."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE receipts
            SET 
              is_paper_verified = FALSE,
              paper_verification_date = NULL,
              verified_by_user = NULL
            WHERE receipt_id = %s
            RETURNING receipt_id;
        """, (receipt_id,))
        
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        conn.commit()
        return {"receipt_id": result[0], "status": "unverified"}
    finally:
        cur.close()
        conn.close()

@router.get("/verified")
async def get_verified_receipts(
    year: int = Query(None),
    limit: int = Query(100, le=1000)
):
    """Get verified receipts (matched to banking)."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        where = "r.is_paper_verified = TRUE"
        if year:
            where += f" AND EXTRACT(YEAR FROM r.receipt_date) = {year}"
        
        cur.execute(f"""
            SELECT 
              r.receipt_id,
              r.receipt_date,
              r.vendor_name,
              r.gross_amount,
              r.category,
              r.banking_transaction_id,
              bt.transaction_date,
              bt.description
            FROM receipts r
            LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
            WHERE {where}
            ORDER BY r.receipt_date DESC
            LIMIT {limit};
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
