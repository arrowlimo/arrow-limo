"""
Vehicle model - Comprehensive schema matching database
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class VehicleBase(BaseModel):
    """Base vehicle fields"""

    vehicle_number: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    passenger_capacity: int | None = None
    operational_status: str = "active"
    last_service_date: date | None = None
    next_service_due: date | None = None
    vin_number: str | None = None
    description: str | None = None
    ext_color: str | None = None
    int_color: str | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    odometer: int | None = None
    odometer_type: str = "mi"
    type: str | None = None

    # Maintenance info
    engine_oil_type: str | None = None
    fuel_filter_number: str | None = None
    fuel_type: str | None = None
    transmission_fluid_type: str | None = None
    transmission_fluid_quantity: str | None = None
    fuel_filter_interval_km: int | None = 60000
    transmission_service_interval_km: int | None = 80000
    curb_weight: int | None = None
    gross_vehicle_weight: int | None = None
    fuel_efficiency_data: dict[str, Any] | None = None
    oil_quantity: str | None = None
    oil_filter_number: str | None = None
    coolant_type: str | None = None
    coolant_quantity: str | None = None
    belt_size: str | None = None
    tire_size: str | None = None
    tire_pressure: str | None = None
    brake_fluid_type: str | None = None
    power_steering_fluid_type: str | None = None
    oil_change_interval_km: int | None = 8000
    oil_change_interval_months: int | None = 6
    air_filter_interval_km: int | None = 30000
    coolant_change_interval_km: int | None = 150000
    brake_fluid_change_interval_months: int | None = 24
    air_filter_part_number: str | None = None
    cabin_filter_part_number: str | None = None
    serpentine_belt_part_number: str | None = None
    return_to_service_date: date | None = None
    maintenance_schedule: dict[str, Any] | None = None
    service_history: list[dict[str, Any]] | None = None
    parts_replacement_history: list[dict[str, Any]] | None = None

    # Classification
    vehicle_type: str | None = None
    vehicle_category: str | None = None
    vehicle_class: str | None = None

    # Lifecycle
    commission_date: date | None = None
    decommission_date: date | None = None
    unit_number: str | None = None
    status: str | None = None

    # CVIP
    cvip_expiry_date: date | None = None
    cvip_inspection_number: str | None = None
    last_cvip_date: date | None = None
    next_cvip_due: date | None = None
    cvip_compliance_status: str | None = None

    # Purchase info
    purchase_date: date | None = None
    purchase_price: float | None = None
    purchase_vendor: str | None = None
    finance_partner: str | None = None
    financing_amount: float | None = None
    monthly_payment: float | None = None

    # Sale/Writeoff
    sale_date: date | None = None
    sale_price: float | None = None
    writeoff_date: date | None = None
    writeoff_reason: str | None = None
    repossession_date: date | None = None

    # Status
    lifecycle_status: str | None = None
    version: int | None = 1
    tier_id: int | None = None
    maintenance_start_date: date | None = None
    maintenance_end_date: date | None = None
    is_in_maintenance: bool | None = False
    red_deer_compliant: bool | None = False
    requires_class_2: bool | None = False


class VehicleCreate(VehicleBase):
    """Create vehicle"""

    pass


class VehicleUpdate(BaseModel):
    """Update vehicle - all fields optional"""

    vehicle_number: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    passenger_capacity: int | None = None
    operational_status: str | None = None
    # ... include any fields you want to allow updating


class Vehicle(VehicleBase):
    """Vehicle from database"""

    vehicle_id: int
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
