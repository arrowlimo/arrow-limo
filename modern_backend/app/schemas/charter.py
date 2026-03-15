"""
Charter model - Comprehensive schema matching database
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from pydantic import BaseModel


class CharterRecordType(str, Enum):
    """Charter record type"""

    charter = "charter"
    placeholder = "placeholder"


class CharterBase(BaseModel):
    """Base charter fields"""

    reserve_number: str
    account_number: str | None = None
    client_id: int | None = None
    charter_date: date | None = None
    pickup_time: time | None = None
    pickup_address: str | None = None
    dropoff_address: str | None = None
    passenger_count: int | None = None
    vehicle: str | None = None
    driver: str | None = None
    rate: float | None = None
    driver_paid: bool | None = False
    balance: float | None = None
    payment_totals: float | None = None
    status: str | None = None
    cancelled: bool | None = False
    locked: bool | None = False
    notes: str | None = None

    # Driver/Client notes
    assigned_driver_id: int | None = None
    driver_notes: str | None = None
    client_notes: str | None = None
    booking_notes: str | None = None

    # NRR (Non-Revenue Run)
    nrr_received: bool | None = False
    nrr_amount: float | None = None

    # Amount tracking
    total_amount_due: float | None = None
    dispatcher_approved: bool | None = False
    approved_at: datetime | None = None

    # Driver pay calculation
    calculated_hours: float | None = None
    driver_hourly_rate: float | None = 15.00
    driver_hours_worked: float | None = None
    driver_base_pay: float | None = None
    driver_gratuity: float | None = 0.00
    driver_total_expense: float | None = None
    expense_calculated_at: datetime | None = None
    paid_amount: float | None = 0.00
    payment_status: str | None = "Pending"

    # Timing
    reservation_time: datetime | None = None

    # Mileage/Fuel
    odometer_start: float | None = None
    odometer_end: float | None = None
    total_kms: float | None = None
    fuel_added: float | None = None
    fuel_added_liters: float | None = None
    vehicle_notes: str | None = None

    # Special flags
    is_placeholder: bool | None = False

    # Workshift
    workshift_start: datetime | None = None
    workshift_end: datetime | None = None
    duty_log: dict[str, Any] | None = None

    # Pricing
    default_hourly_price: float | None = None
    package_rate: float | None = None
    extra_time_rate: float | None = None
    daily_rate: float | None = None
    airport_pickup_price: float | None = None

    # IDs
    employee_id: int | None = None
    vehicle_id: int | None = None
    client_display_name: str | None = None

    # Calendar sync
    calendar_sync_status: str | None = "not_synced"
    calendar_color: str | None = None
    outlook_entry_id: str | None = None
    calendar_notes: str | None = None

    # Record type
    record_type: str | None = "charter"
    is_out_of_town: bool | None = False
    version: int | None = 1

    # Services
    beverage_service_required: bool | None = False

    # NRD (Network Response Day)
    nrd_received: bool | None = False
    nrd_received_at: datetime | None = None
    nrd_amount: float | None = None
    nrd_method: str | None = None

    # Red Deer
    red_deer_bylaw_exempt: bool | None = False

    # Float
    float_received: float | None = None
    float_reimbursement_needed: float | None = None

    # Timestamps - progression
    on_duty_started_at: datetime | None = None
    on_location_at: datetime | None = None
    passengers_loaded_at: datetime | None = None
    en_route_to_event_at: datetime | None = None
    arrived_at_event_at: datetime | None = None
    return_journey_started_at: datetime | None = None
    off_duty_at: datetime | None = None
    completion_timestamp: datetime | None = None

    # Printing
    separate_customer_printout: bool | None = False

    # Charter type
    charter_type: str | None = "hourly"
    quoted_hours: float | None = 0.00
    standby_rate: float | None = 25.00
    split_run_before_hours: float | None = 0.00
    split_run_after_hours: float | None = 0.00
    actual_hours: float | None = None


class CharterCreate(CharterBase):
    """Create charter"""

    pass


class CharterUpdate(BaseModel):
    """Update charter - all fields optional"""

    reserve_number: str | None = None
    status: str | None = None
    cancelled: bool | None = None
    locked: bool | None = None
    driver_paid: bool | None = None
    # ... include any fields you want to allow updating


class Charter(CharterBase):
    """Charter from database"""

    charter_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
