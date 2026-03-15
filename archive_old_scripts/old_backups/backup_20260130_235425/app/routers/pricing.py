"""
Vehicle Pricing API Router

Endpoints:
- GET /pricing/defaults - Get all vehicle pricing defaults
- GET /pricing/by-vehicle/{vehicle_type} - Get pricing for specific vehicle type
- POST /pricing/calculate-quotes - Calculate 3 quote options (hourly, package, split run)
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from ..db import get_connection

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class QuoteRequest(BaseModel):
    """Request to calculate quotes for a charter"""
    vehicle_type: str
    quoted_hours: float
    include_gratuity: bool = False
    gratuity_percentage: float = 18.0


class QuoteOption(BaseModel):
    """Single quote calculation result"""
    quote_type: str  # 'hourly', 'package', 'split_run'
    quote_name: str
    base_rate: Decimal
    hours_included: Optional[float]
    extra_time_rate: Optional[Decimal]
    standby_rate: Optional[Decimal]
    total_before_gratuity: Decimal
    gratuity_amount: Optional[Decimal]
    total_with_gratuity: Optional[Decimal]
    calculation_notes: str


@router.get("/defaults")
def get_all_pricing_defaults():
    """Get all vehicle pricing defaults"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                vehicle_type, charter_type_code, hourly_rate, package_rate,
                package_hours, minimum_hours, extra_time_rate, standby_rate,
                split_run_before_hours, split_run_after_hours, is_active
            FROM vehicle_pricing_defaults
            WHERE is_active = true
            ORDER BY vehicle_type, charter_type_code
        """)
        
        results = []
        for row in cur.fetchall():
            results.append({
                "vehicle_type": row[0],
                "charter_type": row[1],
                "hourly_rate": str(row[2]) if row[2] else "0.00",
                "package_rate": str(row[3]) if row[3] else "0.00",
                "package_hours": float(row[4]) if row[4] else 0.0,
                "minimum_hours": float(row[5]) if row[5] else 0.0,
                "extra_time_rate": str(row[6]) if row[6] else "0.00",
                "standby_rate": str(row[7]) if row[7] else "0.00",
                "split_run_before_hours": float(row[8]) if row[8] else 0.0,
                "split_run_after_hours": float(row[9]) if row[9] else 0.0,
                "is_active": row[10]
            })
        
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load pricing: {e}")
    finally:
        cur.close()
        conn.close()


@router.get("/by-vehicle/{vehicle_type}")
def get_pricing_by_vehicle(vehicle_type: str):
    """Get pricing defaults for specific vehicle type"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                charter_type_code, hourly_rate, package_rate, package_hours,
                minimum_hours, extra_time_rate, standby_rate,
                split_run_before_hours, split_run_after_hours
            FROM vehicle_pricing_defaults
            WHERE vehicle_type = %s AND is_active = true
            ORDER BY charter_type_code
        """, (vehicle_type,))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "charter_type": row[0],
                "hourly_rate": str(row[1]) if row[1] else "0.00",
                "package_rate": str(row[2]) if row[2] else "0.00",
                "package_hours": float(row[3]) if row[3] else 0.0,
                "minimum_hours": float(row[4]) if row[4] else 0.0,
                "extra_time_rate": str(row[5]) if row[5] else "0.00",
                "standby_rate": str(row[6]) if row[6] else "0.00",
                "split_run_before_hours": float(row[7]) if row[7] else 0.0,
                "split_run_after_hours": float(row[8]) if row[8] else 0.0,
            })
        
        if not results:
            raise HTTPException(status_code=404, detail=f"No pricing found for {vehicle_type}")
        
        return {"vehicle_type": vehicle_type, "pricing_options": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load pricing: {e}")
    finally:
        cur.close()
        conn.close()


@router.post("/calculate-quotes")
def calculate_quotes(request: QuoteRequest):
    """
    Calculate 3 quote options for a charter:
    1. Hourly rate (e.g., $195/hr × 6 hours = $1170)
    2. Package rate (e.g., 6hr package $1170 + extra time $150/hr)
    3. Split run (e.g., 1.5hr before + 1.5hr after = 3hr free, OR 3hr standby @ $25/hr)
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Get pricing defaults for this vehicle type
        cur.execute("""
            SELECT 
                charter_type_code, hourly_rate, package_rate, package_hours,
                minimum_hours, extra_time_rate, standby_rate,
                split_run_before_hours, split_run_after_hours
            FROM vehicle_pricing_defaults
            WHERE vehicle_type = %s AND is_active = true
        """, (request.vehicle_type,))
        
        pricing_data = {}
        for row in cur.fetchall():
            pricing_data[row[0]] = {
                "hourly_rate": float(row[1]) if row[1] else 0.0,
                "package_rate": float(row[2]) if row[2] else 0.0,
                "package_hours": float(row[3]) if row[3] else 0.0,
                "minimum_hours": float(row[4]) if row[4] else 0.0,
                "extra_time_rate": float(row[5]) if row[5] else 0.0,
                "standby_rate": float(row[6]) if row[6] else 0.0,
                "split_run_before": float(row[7]) if row[7] else 0.0,
                "split_run_after": float(row[8]) if row[8] else 0.0,
            }
        
        if not pricing_data:
            raise HTTPException(status_code=404, detail=f"No pricing found for {request.vehicle_type}")
        
        quotes = []
        quoted_hours = request.quoted_hours
        
        # QUOTE 1: Hourly Rate
        if 'hourly' in pricing_data:
            hourly = pricing_data['hourly']
            hourly_total = hourly['hourly_rate'] * quoted_hours
            
            gratuity_amt = None
            total_with_tip = None
            if request.include_gratuity:
                gratuity_amt = round(hourly_total * request.gratuity_percentage / 100, 2)
                total_with_tip = hourly_total + gratuity_amt
            
            quotes.append({
                "quote_type": "hourly",
                "quote_name": f"Quote 1: Hourly Rate",
                "base_rate": hourly['hourly_rate'],
                "hours_included": quoted_hours,
                "extra_time_rate": hourly['extra_time_rate'],
                "standby_rate": None,
                "total_before_gratuity": round(hourly_total, 2),
                "gratuity_amount": gratuity_amt,
                "total_with_gratuity": total_with_tip,
                "calculation_notes": f"${hourly['hourly_rate']:.2f}/hr × {quoted_hours} hours = ${hourly_total:.2f}. Extra time: ${hourly['extra_time_rate']:.2f}/hr"
            })
        
        # QUOTE 2: Package Rate
        if 'package' in pricing_data:
            pkg = pricing_data['package']
            if pkg['package_rate'] > 0:
                pkg_hours = pkg['package_hours']
                base_total = pkg['package_rate']
                
                # Calculate extra time if quoted hours exceed package hours
                extra_hours = max(0, quoted_hours - pkg_hours)
                extra_cost = extra_hours * pkg['extra_time_rate']
                total = base_total + extra_cost
                
                gratuity_amt = None
                total_with_tip = None
                if request.include_gratuity:
                    gratuity_amt = round(total * request.gratuity_percentage / 100, 2)
                    total_with_tip = total + gratuity_amt
                
                extra_note = f" + {extra_hours}hr extra @ ${pkg['extra_time_rate']:.2f}/hr = ${extra_cost:.2f}" if extra_hours > 0 else ""
                
                quotes.append({
                    "quote_type": "package",
                    "quote_name": f"Quote 2: Package Rate",
                    "base_rate": pkg['package_rate'],
                    "hours_included": pkg_hours,
                    "extra_time_rate": pkg['extra_time_rate'],
                    "standby_rate": None,
                    "total_before_gratuity": round(total, 2),
                    "gratuity_amount": gratuity_amt,
                    "total_with_gratuity": total_with_tip,
                    "calculation_notes": f"{pkg_hours}hr package ${pkg['package_rate']:.2f}{extra_note}. Total: ${total:.2f}"
                })
        
        # QUOTE 3: Split Run
        if 'split_run' in pricing_data:
            split = pricing_data['split_run']
            before_hrs = split['split_run_before']
            after_hrs = split['split_run_after']
            free_hours = before_hrs + after_hrs
            
            # Calculate standby time (middle period)
            standby_hours = max(0, quoted_hours - free_hours)
            standby_cost = standby_hours * split['standby_rate']
            
            gratuity_amt = None
            total_with_tip = None
            if request.include_gratuity:
                gratuity_amt = round(standby_cost * request.gratuity_percentage / 100, 2)
                total_with_tip = standby_cost + gratuity_amt
            
            if standby_hours > 0:
                calc_note = f"{before_hrs}hr before + {after_hrs}hr after = {free_hours}hr free. {standby_hours}hr standby @ ${split['standby_rate']:.2f}/hr = ${standby_cost:.2f}"
            else:
                calc_note = f"{before_hrs}hr before + {after_hrs}hr after = {free_hours}hr (within free time, no charge)"
            
            quotes.append({
                "quote_type": "split_run",
                "quote_name": f"Quote 3: Split Run",
                "base_rate": 0.00,
                "hours_included": free_hours,
                "extra_time_rate": split['extra_time_rate'],
                "standby_rate": split['standby_rate'],
                "total_before_gratuity": round(standby_cost, 2),
                "gratuity_amount": gratuity_amt,
                "total_with_gratuity": total_with_tip,
                "calculation_notes": calc_note
            })
        
        return {
            "vehicle_type": request.vehicle_type,
            "quoted_hours": quoted_hours,
            "include_gratuity": request.include_gratuity,
            "gratuity_percentage": request.gratuity_percentage if request.include_gratuity else None,
            "quotes": quotes,
            "count": len(quotes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate quotes: {e}")
    finally:
        cur.close()
        conn.close()


@router.get("/charter-types")
def get_charter_types():
    """Get all available charter types"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT type_code, type_name, description, requires_hours, is_active
            FROM charter_types
            WHERE is_active = true
            ORDER BY display_order
        """)
        
        results = []
        for row in cur.fetchall():
            results.append({
                "type_code": row[0],
                "type_name": row[1],
                "description": row[2],
                "requires_hours": row[3],
                "is_active": row[4]
            })
        
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load charter types: {e}")
    finally:
        cur.close()
        conn.close()
