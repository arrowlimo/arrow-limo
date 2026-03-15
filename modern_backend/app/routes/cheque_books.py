"""
Cheque Book Management API
Allows tracking and updating cheques by bank, number, status (NSF, void, cleared, etc.)
"""

from datetime import date

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_connection

router = APIRouter(prefix="/api/cheque-books", tags=["Cheque Books"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChequeSearchRequest(BaseModel):
    cheque_number: str | None = None
    amount: float | None = None
    payee: str | None = None
    bank_account: str | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class ChequeUpdateRequest(BaseModel):
    cheque_number: str
    payee: str | None = None
    amount: float | None = None
    status: str | None = Field(None, description="cleared, void, nsf, pending")
    notes: str | None = None
    gl_code: str | None = None


class ChequeResponse(BaseModel):
    transaction_id: int
    cheque_number: str
    transaction_date: date | None
    payee: str | None
    amount: float
    bank_account: str
    bank_name: str
    status: str | None
    category: str | None
    gl_code: str | None
    balance_after: float | None
    notes: str | None


class ChequeBookSummary(BaseModel):
    bank_account: str
    bank_name: str
    total_cheques: int
    categorized: int
    uncategorized: int
    total_amount: float
    cheque_range: str
    unknown_payees: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/summary", response_model=list[ChequeBookSummary])
async def get_cheque_books_summary():
    """Get summary of all cheque books by bank account"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                account_number,
                CASE 
                    WHEN source_file ILIKE '%scotia%' THEN 'Scotia Bank'
                    WHEN source_file ILIKE '%cibc%' THEN 'CIBC'
                    WHEN account_number = '903990106011' THEN 'Scotia Bank'
                    WHEN account_number = '0228362' THEN 'CIBC'
                    ELSE 'Unknown Bank'
                END as bank_name,
                COUNT(*) as total_cheques,
                COUNT(CASE WHEN category IS NOT NULL AND category != '' THEN 1 END) as categorized,
                COUNT(CASE WHEN category IS NULL OR category = '' THEN 1 END) as uncategorized,
                SUM(debit_amount) as total_amount,
                MIN(CAST(REGEXP_REPLACE(vendor_extracted, '[^0-9]', '', 'g') AS INTEGER)) as min_cheque,
                MAX(CAST(REGEXP_REPLACE(vendor_extracted, '[^0-9]', '', 'g') AS INTEGER)) as max_cheque,
                COUNT(CASE WHEN check_recipient IS NULL OR check_recipient = 'Unknown' THEN 1 END) as unknown_payees
            FROM banking_transactions
            WHERE vendor_extracted LIKE 'CHEQUE%'
            AND transaction_date >= '2012-01-01'
            GROUP BY account_number, bank_name
            ORDER BY bank_name, account_number
        """)
        
        results = cur.fetchall()
        
        summaries = []
        for row in results:
            summaries.append(ChequeBookSummary(
                bank_account=row['account_number'],
                bank_name=row['bank_name'],
                total_cheques=row['total_cheques'],
                categorized=row['categorized'],
                uncategorized=row['uncategorized'],
                total_amount=float(row['total_amount'] or 0),
                cheque_range=f"#{row['min_cheque']}-#{row['max_cheque']}" if row['min_cheque'] and row['max_cheque'] else "N/A",
                unknown_payees=row['unknown_payees']
            ))
        
        return summaries
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.post("/search", response_model=list[ChequeResponse])
async def search_cheques(search: ChequeSearchRequest):
    """Search for cheques by number, amount, payee, bank, status, or date range"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Build dynamic WHERE clause
        where_clauses = ["vendor_extracted LIKE 'CHEQUE%'", "transaction_date >= '2012-01-01'"]
        params = []
        
        if search.cheque_number:
            where_clauses.append("vendor_extracted ILIKE %s")
            params.append(f"%CHEQUE #{search.cheque_number}%")
        
        if search.amount:
            where_clauses.append("ABS(debit_amount - %s) < 0.01")
            params.append(search.amount)
        
        if search.payee:
            where_clauses.append("(check_recipient ILIKE %s OR vendor_extracted ILIKE %s)")
            params.extend([f"%{search.payee}%", f"%{search.payee}%"])
        
        if search.bank_account:
            where_clauses.append("account_number = %s")
            params.append(search.bank_account)
        
        if search.status:
            if search.status.lower() == 'nsf':
                where_clauses.append("(category ILIKE '%nsf%' OR description ILIKE '%nsf%' OR description ILIKE '%returned%')")
            elif search.status.lower() == 'void':
                where_clauses.append("(category ILIKE '%void%' OR description ILIKE '%void%')")
            elif search.status.lower() == 'cleared':
                where_clauses.append("category IS NOT NULL AND category != '' AND category NOT ILIKE '%nsf%' AND category NOT ILIKE '%void%'")
            elif search.status.lower() == 'pending':
                where_clauses.append("(category IS NULL OR category = '')")
        
        if search.date_from:
            where_clauses.append("transaction_date >= %s")
            params.append(search.date_from)
        
        if search.date_to:
            where_clauses.append("transaction_date <= %s")
            params.append(search.date_to)
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                transaction_id,
                vendor_extracted,
                transaction_date,
                check_recipient,
                debit_amount,
                account_number,
                CASE 
                    WHEN source_file ILIKE '%scotia%' THEN 'Scotia Bank'
                    WHEN source_file ILIKE '%cibc%' THEN 'CIBC'
                    WHEN account_number = '903990106011' THEN 'Scotia Bank'
                    WHEN account_number = '0228362' THEN 'CIBC'
                    ELSE 'Unknown Bank'
                END as bank_name,
                CASE
                    WHEN category ILIKE '%nsf%' OR description ILIKE '%nsf%' THEN 'NSF'
                    WHEN category ILIKE '%void%' OR description ILIKE '%void%' THEN 'VOID'
                    WHEN category IS NOT NULL AND category != '' THEN 'CLEARED'
                    ELSE 'PENDING'
                END as status,
                category,
                gl_code,
                running_balance,
                description
            FROM banking_transactions
            WHERE {where_sql}
            ORDER BY 
                CAST(REGEXP_REPLACE(vendor_extracted, '[^0-9]', '', 'g') AS INTEGER),
                transaction_date
            LIMIT 1000
        """
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        cheques = []
        for row in results:
            # Extract cheque number from vendor_extracted (e.g., "CHEQUE #123")
            import re
            match = re.search(r'#(\d+)', row['vendor_extracted'])
            cheque_num = match.group(1) if match else row['vendor_extracted']
            
            cheques.append(ChequeResponse(
                transaction_id=row['transaction_id'],
                cheque_number=cheque_num,
                transaction_date=row['transaction_date'],
                payee=row['check_recipient'],
                amount=float(row['debit_amount'] or 0),
                bank_account=row['account_number'],
                bank_name=row['bank_name'],
                status=row['status'],
                category=row['category'],
                gl_code=row['gl_code'],
                balance_after=float(row['running_balance'] or 0),
                notes=row['description']
            ))
        
        return cheques
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.put("/{transaction_id}", response_model=dict)
async def update_cheque(transaction_id: int, update: ChequeUpdateRequest):
    """Update cheque information (payee, status, GL code, notes)"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Build dynamic UPDATE clause
        update_fields = []
        params = []
        
        if update.payee is not None:
            update_fields.append("check_recipient = %s")
            params.append(update.payee)
        
        if update.status is not None:
            # Map status to category
            status_map = {
                'nsf': 'NSF Fee',
                'void': 'VOID',
                'cleared': 'Expense - Other',  # Default, should be updated with actual GL
                'pending': None
            }
            category = status_map.get(update.status.lower(), update.status)
            update_fields.append("category = %s")
            params.append(category)
        
        if update.gl_code is not None:
            update_fields.append("gl_code = %s")
            params.append(update.gl_code)
        
        if update.notes is not None:
            update_fields.append("description = %s")
            params.append(update.notes)
        
        # Always update modified timestamp
        update_fields.append("updated_at = NOW()")
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        params.append(transaction_id)
        
        update_sql = f"""
            UPDATE banking_transactions
            SET {', '.join(update_fields)}
            WHERE transaction_id = %s
            RETURNING transaction_id, check_recipient, category, gl_code
        """
        
        cur.execute(update_sql, params)
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Cheque transaction {transaction_id} not found")
        
        conn.commit()
        
        return {
            "success": True,
            "message": "Cheque updated successfully",
            "transaction_id": result[0],
            "payee": result[1],
            "category": result[2],
            "gl_code": result[3]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.post("/bulk-update", response_model=dict)
async def bulk_update_cheques(updates: list[ChequeUpdateRequest]):
    """Bulk update multiple cheques at once"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        updated_count = 0
        errors = []
        
        for update in updates:
            try:
                # Find transaction by cheque number
                cur.execute("""
                    SELECT transaction_id
                    FROM banking_transactions
                    WHERE vendor_extracted ILIKE %s
                    LIMIT 1
                """, (f"%CHEQUE #{update.cheque_number}%",))
                
                result = cur.fetchone()
                if not result:
                    errors.append(f"Cheque #{update.cheque_number} not found")
                    continue
                
                transaction_id = result[0]
                
                # Build UPDATE
                update_fields = []
                params = []
                
                if update.payee:
                    update_fields.append("check_recipient = %s")
                    params.append(update.payee)
                
                if update.gl_code:
                    update_fields.append("gl_code = %s")
                    params.append(update.gl_code)
                
                if update.status:
                    status_map = {
                        'nsf': 'NSF Fee',
                        'void': 'VOID',
                        'cleared': 'Expense - Other',
                        'pending': None
                    }
                    category = status_map.get(update.status.lower(), update.status)
                    update_fields.append("category = %s")
                    params.append(category)
                
                if update.notes:
                    update_fields.append("description = %s")
                    params.append(update.notes)
                
                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    params.append(transaction_id)
                    
                    update_sql = f"""
                        UPDATE banking_transactions
                        SET {', '.join(update_fields)}
                        WHERE transaction_id = %s
                    """
                    
                    cur.execute(update_sql, params)
                    updated_count += cur.rowcount
                
            except Exception as e:
                errors.append(f"Cheque #{update.cheque_number}: {e!s}")
        
        conn.commit()
        
        return {
            "success": True,
            "updated": updated_count,
            "total": len(updates),
            "errors": errors
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.get("/by-bank/{account_number}", response_model=list[ChequeResponse])
async def get_cheques_by_bank(
    account_number: str,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get all cheques for a specific bank account"""
    search = ChequeSearchRequest(bank_account=account_number)
    return await search_cheques(search)
