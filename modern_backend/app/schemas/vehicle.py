"""
Vehicle model - Comprehensive schema matching database
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class VehicleBase(BaseModel):
    """Base vehicle fields"""

    vehicle_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    license_plate: Optional[str] = None
    passenger_capacity: Optional[int] = None
    operational_status: str = "active"
    last_service_date: Optional[date] = None
    next_service_due: Optional[date] = None
    vin_number: Optional[str] = None
    description: Optional[str] = None
    ext_color: Optional[str] = None
    int_color: Optional[str] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    odometer: Optional[int] = None
    odometer_type: str = "mi"
    type: Optional[str] = None

    # Maintenance info
    engine_oil_type: Optional[str] = None
    fuel_filter_number: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission_fluid_type: Optional[str] = None
    transmission_fluid_quantity: Optional[str] = None
    fuel_filter_interval_km: Optional[int] = 60000
    transmission_service_interval_km: Optional[int] = 80000
    curb_weight: Optional[int] = None
    gross_vehicle_weight: Optional[int] = None
    fuel_efficiency_data: Optional[Dict[str, Any]] = None
    oil_quantity: Optional[str] = None
    oil_filter_number: Optional[str] = None
    coolant_type: Optional[str] = None
    coolant_quantity: Optional[str] = None
    belt_size: Optional[str] = None
    tire_size: Optional[str] = None
    tire_pressure: Optional[str] = None
    brake_fluid_type: Optional[str] = None
    power_steering_fluid_type: Optional[str] = None
    oil_change_interval_km: Optional[int] = 8000
    oil_change_interval_months: Optional[int] = 6
    air_filter_interval_km: Optional[int] = 30000
    coolant_change_interval_km: Optional[int] = 150000
    brake_fluid_change_interval_months: Optional[int] = 24
    air_filter_part_number: Optional[str] = None
    cabin_filter_part_number: Optional[str] = None
    serpentine_belt_part_number: Optional[str] = None
    return_to_service_date: Optional[date] = None
    maintenance_schedule: Optional[Dict[str, Any]] = None
    service_history: Optional[List[Dict[str, Any]]] = None
    parts_replacement_history: Optional[List[Dict[str, Any]]] = None

    # Classification
    vehicle_type: Optional[str] = None
    vehicle_category: Optional[str] = None
    vehicle_class: Optional[str] = None

    # Lifecycle
    commission_date: Optional[date] = None
    decommission_date: Optional[date] = None
    unit_number: Optional[str] = None
    status: Optional[str] = None

    # CVIP
    cvip_expiry_date: Optional[date] = None
    cvip_inspection_number: Optional[str] = None
    last_cvip_date: Optional[date] = None
    next_cvip_due: Optional[date] = None
    cvip_compliance_status: Optional[str] = None

    # Purchase info
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    purchase_vendor: Optional[str] = None
    finance_partner: Optional[str] = None
    financing_amount: Optional[float] = None
    monthly_payment: Optional[float] = None

    # Sale/Writeoff
    sale_date: Optional[date] = None
    sale_price: Optional[float] = None
    writeoff_date: Optional[date] = None
    writeoff_reason: Optional[str] = None
    repossession_date: Optional[date] = None

    # Status
    lifecycle_status: Optional[str] = None
    version: Optional[int] = 1
    tier_id: Optional[int] = None
    maintenance_start_date: Optional[date] = None
    maintenance_end_date: Optional[date] = None
    is_in_maintenance: Optional[bool] = False
    red_deer_compliant: Optional[bool] = False
    requires_class_2: Optional[bool] = False


class VehicleCreate(VehicleBase):
    """Create vehicle"""

    pass


class VehicleUpdate(BaseModel):
    """Update vehicle - all fields optional"""

    vehicle_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    license_plate: Optional[str] = None
    passenger_capacity: Optional[int] = None
    operational_status: Optional[str] = None
    # ... include any fields you want to allow updating


class Vehicle(VehicleBase):
    """Vehicle from database"""

    vehicle_id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
