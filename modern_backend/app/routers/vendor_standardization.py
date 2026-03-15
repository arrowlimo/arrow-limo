"""
Vendor Standardization Tool - identify and clean up vendor names
- List all vendors with counts
- Merge mistyped vendors
- Auto-capitalize all vendor names
- Track standardization history
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..database import get_connection

router = APIRouter(prefix="/api/vendors", tags=["vendors"])
logger = logging.getLogger(__name__)


class VendorInfo(BaseModel):
    """Vendor with receipt count and sample amounts"""
    vendor_name: str
    receipt_count: int
    total_amount: float
    last_used: str | None = None
    variations: list[str] = []


class VendorMerge(BaseModel):
    """Merge request: replace old vendor names with new one"""
    source_vendors: list[str]  # Old vendor names to merge
    target_vendor: str  # New canonical name (will be capitalized)


@router.get("/list-all")
async def get_all_vendors(
    min_receipts: int = Query(1, ge=1),
    conn=Depends(get_connection)
):
    """Get list of all vendors with receipt counts, sorted by frequency"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                vendor_name,
                COUNT(*) as receipt_count,
                SUM(amount) as total_amount,
                MAX(receipt_date) as last_used
            FROM receipts
            WHERE vendor_name IS NOT NULL AND vendor_name != ''
            GROUP BY vendor_name
            HAVING COUNT(*) >= %s
            ORDER BY receipt_count DESC
        """, (min_receipts,))
        
        rows = cur.fetchall()
        cur.close()
        
        vendors = [
            {
                "vendor_name": r[0],
                "receipt_count": r[1],
                "total_amount": float(r[2] or 0),
                "last_used": str(r[3]) if r[3] else None
            }
            for r in rows
        ]
        
        return vendors
    
    except Exception as e:
        logger.error(f"Error listing vendors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/find-variations")
async def find_vendor_variations(
    vendor_prefix: str = Query(..., min_length=3, description="First few chars"),
    conn=Depends(get_connection)
):
    """Find all vendor name variations starting with prefix (case-insensitive)"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT vendor_name
            FROM receipts
            WHERE LOWER(vendor_name) LIKE LOWER(%s)
            ORDER BY vendor_name
        """, (f"{vendor_prefix}%",))
        
        rows = cur.fetchall()
        cur.close()
        
        variations = [r[0] for r in rows]
        
        return {
            "search_prefix": vendor_prefix,
            "found": len(variations),
            "variations": variations
        }
    
    except Exception as e:
        logger.error(f"Error finding variations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-vendors")
async def merge_vendor_names(
    merge_request: VendorMerge,
    conn=Depends(get_connection)
):
    """
    Merge multiple vendor names into one canonical name.
    
    Example:
    - source_vendors: ["POS PURCHASE 1234.567", "POS PURCHASE 1234.5", "shell"]
    - target_vendor: "SHELL CANADA"
    
    Result: All receipts with any source vendor name → "SHELL CANADA"
    """
    try:
        if not merge_request.source_vendors or not merge_request.target_vendor:
            raise ValueError("Must provide source_vendors and target_vendor")
        
        # Capitalize target vendor name
        canonical_name = merge_request.target_vendor.upper()
        
        cur = conn.cursor()
        
        # Update all receipts with any of the source vendor names
        placeholders = ",".join(["%s"] * len(merge_request.source_vendors))
        
        cur.execute(f"""
            UPDATE receipts
            SET vendor_name = %s
            WHERE LOWER(vendor_name) IN ({placeholders})
        """, [canonical_name] + [v.lower() for v in merge_request.source_vendors])
        
        affected_rows = cur.rowcount
        conn.commit()
        
        # Log this standardization
        for old_vendor in merge_request.source_vendors:
            cur.execute("""
                INSERT INTO vendor_standardization_log (old_name, new_name, affected_count, standardized_by)
                VALUES (%s, %s, %s, 'admin')
            """, (old_vendor, canonical_name, affected_rows // len(merge_request.source_vendors)))
        
        conn.commit()
        cur.close()
        
        logger.info(f"Merged {len(merge_request.source_vendors)} vendor names → {canonical_name} ({affected_rows} receipts)")
        
        return {
            "status": "success",
            "message": f"Merged {len(merge_request.source_vendors)} vendor names to '{canonical_name}'",
            "affected_receipts": affected_rows,
            "canonical_name": canonical_name
        }
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error merging vendors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/capitalize-all")
async def capitalize_all_vendors(
    dry_run: bool = Query(True),
    conn=Depends(get_connection)
):
    """
    Capitalize all vendor names (UPPER CASE).
    Use dry_run=true to preview changes before applying.
    
    Example: "shell canada" → "SHELL CANADA"
    """
    try:
        cur = conn.cursor()
        
        if dry_run:
            # Preview what will change
            cur.execute("""
                SELECT vendor_name, UPPER(vendor_name) as capitalized
                FROM receipts
                WHERE vendor_name IS NOT NULL 
                  AND vendor_name != ''
                  AND vendor_name != UPPER(vendor_name)
                ORDER BY vendor_name
            """)
            
            rows = cur.fetchall()
            cur.close()
            
            changes = [
                {
                    "current": r[0],
                    "will_become": r[1],
                    "receipts": None  # Would need another query to count
                }
                for r in rows
            ]
            
            return {
                "dry_run": True,
                "changes_to_apply": len(changes),
                "preview": changes[:20]  # Show first 20
            }
        
        else:
            # Apply capitalization
            cur.execute("""
                UPDATE receipts
                SET vendor_name = UPPER(vendor_name)
                WHERE vendor_name IS NOT NULL 
                  AND vendor_name != ''
                  AND vendor_name != UPPER(vendor_name)
            """)
            
            affected = cur.rowcount
            conn.commit()
            cur.close()
            
            logger.info(f"Capitalized {affected} vendor names")
            
            return {
                "status": "success",
                "message": f"Capitalized {affected} vendor names to UPPER CASE",
                "affected_receipts": affected
            }
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error capitalizing vendors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/standardization-log")
async def get_standardization_log(
    limit: int = Query(100, ge=1, le=1000),
    conn=Depends(get_connection)
):
    """Get history of vendor name standardization changes"""
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                id,
                old_name,
                new_name,
                affected_count,
                standardized_by,
                standardized_at
            FROM vendor_standardization_log
            ORDER BY standardized_at DESC
            LIMIT %s
        """, (limit,))
        
        rows = cur.fetchall()
        cur.close()
        
        log = [
            {
                "id": r[0],
                "old_name": r[1],
                "new_name": r[2],
                "affected_receipts": r[3],
                "standardized_by": r[4],
                "date": str(r[5]) if r[5] else None
            }
            for r in rows
        ]
        
        return log
    
    except Exception as e:
        logger.error(f"Error getting standardization log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-standardize")
async def bulk_standardize_vendors(
    corrections: list[VendorMerge],
    dry_run: bool = Query(True),
    conn=Depends(get_connection)
):
    """
    Apply multiple vendor standardizations at once.
    
    Example corrections:
    [
        {"source_vendors": ["shell", "Shell"], "target_vendor": "SHELL CANADA"},
        {"source_vendors": ["POS", "pos"], "target_vendor": "POS PURCHASES"}
    ]
    """
    try:
        total_affected = 0
        applied = []
        errors = []
        
        cur = conn.cursor()
        
        for correction in corrections:
            try:
                canonical_name = correction.target_vendor.upper()
                placeholders = ",".join(["%s"] * len(correction.source_vendors))
                
                if dry_run:
                    # Count what would change
                    cur.execute(f"""
                        SELECT COUNT(*)
                        FROM receipts
                        WHERE LOWER(vendor_name) IN ({placeholders})
                    """, [v.lower() for v in correction.source_vendors])
                    
                    count = cur.fetchone()[0]
                    applied.append({
                        "source": correction.source_vendors,
                        "target": canonical_name,
                        "would_affect": count
                    })
                    total_affected += count
                
                else:
                    # Actually apply
                    cur.execute(f"""
                        UPDATE receipts
                        SET vendor_name = %s
                        WHERE LOWER(vendor_name) IN ({placeholders})
                    """, [canonical_name] + [v.lower() for v in correction.source_vendors])
                    
                    count = cur.rowcount
                    applied.append({
                        "source": correction.source_vendors,
                        "target": canonical_name,
                        "affected": count
                    })
                    total_affected += count
            
            except Exception as ce:
                errors.append({
                    "source": correction.source_vendors,
                    "target": correction.target_vendor,
                    "error": str(ce)
                })
        
        if not dry_run:
            conn.commit()
        
        cur.close()
        
        return {
            "dry_run": dry_run,
            "corrections_processed": len(applied),
            "corrections_with_errors": len(errors),
            "total_affected_receipts": total_affected,
            "applied": applied,
            "errors": errors if errors else None
        }
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error bulk standardizing vendors: {e}")
        raise HTTPException(status_code=500, detail=str(e))
