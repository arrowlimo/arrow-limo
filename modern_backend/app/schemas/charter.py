"""
Charter model - Comprehensive schema matching database
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class CharterRecordType(str, Enum):
    """Charter record type"""

    charter = "charter"
    placeholder = "placeholder"


class CharterBase(BaseModel):
    """Base charter fields"""

    reserve_number: str
    account_number: Optional[str] = None
    client_id: Optional[int] = None
    charter_date: Optional[date] = None
    pickup_time: Optional[time] = None
    pickup_address: Optional[str] = None
    dropoff_address: Optional[str] = None
    passenger_count: Optional[int] = None
    vehicle: Optional[str] = None
    driver: Optional[str] = None
    rate: Optional[float] = None
    driver_paid: Optional[bool] = False
    balance: Optional[float] = None
    payment_totals: Optional[float] = None
    status: Optional[str] = None
    cancelled: Optional[bool] = False
    notes: Optional[str] = None

    # Driver/Client notes
    assigned_driver_id: Optional[int] = None
    driver_notes: Optional[str] = None
    client_notes: Optional[str] = None
    booking_notes: Optional[str] = None

    # NRR (Non-Revenue Run)
    nrr_received: Optional[bool] = False
    nrr_amount: Optional[float] = None

    # Amount tracking
    total_amount_due: Optional[float] = None
    dispatcher_approved: Optional[bool] = False
    approved_at: Optional[datetime] = None

    # Driver pay calculation
    calculated_hours: Optional[float] = None
    driver_hourly_rate: Optional[float] = 15.00
    driver_hours_worked: Optional[float] = None
    driver_base_pay: Optional[float] = None
    driver_gratuity: Optional[float] = 0.00
    driver_total_expense: Optional[float] = None
    expense_calculated_at: Optional[datetime] = None
    paid_amount: Optional[float] = 0.00
    payment_status: Optional[str] = "Pending"

    # Timing
    reservation_time: Optional[datetime] = None

    # Mileage/Fuel
    odometer_start: Optional[float] = None
    odometer_end: Optional[float] = None
    total_kms: Optional[float] = None
    fuel_added: Optional[float] = None
    fuel_added_liters: Optional[float] = None
    vehicle_notes: Optional[str] = None

    # Special flags
    is_placeholder: Optional[bool] = False

    # Workshift
    workshift_start: Optional[datetime] = None
    workshift_end: Optional[datetime] = None
    duty_log: Optional[Dict[str, Any]] = None

    # Pricing
    default_hourly_price: Optional[float] = None
    package_rate: Optional[float] = None
    extra_time_rate: Optional[float] = None
    daily_rate: Optional[float] = None
    airport_pickup_price: Optional[float] = None

    # IDs
    employee_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    client_display_name: Optional[str] = None

    # Calendar sync
    calendar_sync_status: Optional[str] = "not_synced"
    calendar_color: Optional[str] = None
    outlook_entry_id: Optional[str] = None
    calendar_notes: Optional[str] = None

    # Record type
    record_type: Optional[str] = "charter"
    is_out_of_town: Optional[bool] = False
    version: Optional[int] = 1

    # Services
    beverage_service_required: Optional[bool] = False

    # NRD (Network Response Day)
    nrd_received: Optional[bool] = False
    nrd_received_at: Optional[datetime] = None
    nrd_amount: Optional[float] = None
    nrd_method: Optional[str] = None

    # Red Deer
    red_deer_bylaw_exempt: Optional[bool] = False

    # Float
    float_received: Optional[float] = None
    float_reimbursement_needed: Optional[float] = None

    # Timestamps - progression
    on_duty_started_at: Optional[datetime] = None
    on_location_at: Optional[datetime] = None
    passengers_loaded_at: Optional[datetime] = None
    en_route_to_event_at: Optional[datetime] = None
    arrived_at_event_at: Optional[datetime] = None
    return_journey_started_at: Optional[datetime] = None
    off_duty_at: Optional[datetime] = None
    completion_timestamp: Optional[datetime] = None

    # Printing
    separate_customer_printout: Optional[bool] = False

    # Charter type
    charter_type: Optional[str] = "hourly"
    quoted_hours: Optional[float] = 0.00
    standby_rate: Optional[float] = 25.00
    split_run_before_hours: Optional[float] = 0.00
    split_run_after_hours: Optional[float] = 0.00
    actual_hours: Optional[float] = None


class CharterCreate(CharterBase):
    """Create charter"""

    pass


class CharterUpdate(BaseModel):
    """Update charter - all fields optional"""

    reserve_number: Optional[str] = None
    status: Optional[str] = None
    cancelled: Optional[bool] = None
    driver_paid: Optional[bool] = None
    # ... include any fields you want to allow updating


class Charter(CharterBase):
    """Charter from database"""

    charter_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
