"""
Pydantic models for booking/charter operations.

Converts form data to validated database records with business rule enforcement.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class RouteItem(BaseModel):
    """
    Single stop in a charter itinerary.

    Types: pickup, dropoff, stop, depart, return
    """

    type: str = Field(
        ..., description="Route type: pickup, dropoff, stop, depart, return"
    )
    address: str = Field(..., min_length=5, description="Address of the stop")
    time24: Optional[str] = Field(None, description="Time in HH:MM format")

    @validator("type")
    def validate_type(cls, v):
        """Ensure route type is valid."""
        valid_types = ["pickup", "dropo", "stop", "depart", "return"]
        if v.lower() not in valid_types:
            raise ValueError(f"route type must be one of {valid_types}")
        return v.lower()

    @validator("time24")
    def validate_time(cls, v):
        """Validate time format HH:MM."""
        if v is None:
            return v
        try:
            time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("time24 must be in HH:MM format")


class ChartRequest(BaseModel):
    """
    Complete booking request from form submission.

    All field validations enforce business rules:
    - Dates must be >= today
    - Passenger load 1-50
    - Total amount > 0
    - Status must be valid
    - Itinerary must have >= 2 stops
    """

    # Customer Details
    client_name: str = Field(..., min_length=2, description="Customer name")
    phone: str = Field(..., min_length=10, description="Phone number")
    email: str = Field(..., description="Email address")
    billing_address: str = Field(..., min_length=5, description="Billing address")
    city: str = Field(..., min_length=2, description="City")
    province: str = Field(default="AB", description="Province/State")
    postal_code: str = Field(..., min_length=5, description="Postal code")

    # Charter Details
    charter_date: date = Field(..., description="Charter date (>= today)")
    pickup_time: str = Field(..., description="Pickup time in HH:MM format")
    passenger_load: int = Field(..., ge=1, le=50, description="Passenger count 1-50")
    vehicle_type_requested: Optional[str] = Field(
        None, description="Vehicle type preference"
    )
    vehicle_booked_id: Optional[int] = Field(None, description="Assigned vehicle ID")
    assigned_driver_id: Optional[int] = Field(None, description="Assigned driver ID")

    # Itinerary
    itinerary: List[RouteItem] = Field(
        ..., min_items=2, description="Min 2 stops (pickup + dropoff)"
    )

    # Notes
    customer_notes: Optional[str] = Field(None, description="Notes for customer")
    dispatcher_notes: Optional[str] = Field(
        None, description="Internal notes for dispatcher"
    )
    special_requests: Optional[str] = Field(
        None, description="Special requests (alcohol, AV, etc)"
    )

    # Pricing
    base_charge: Decimal = Field(..., gt=0, description="Base charge amount")
    airport_fee: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Airport fee (if applicable)",
    )
    additional_charges_amount: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Additional charges"
    )
    total_amount_due: Decimal = Field(
        ..., gt=0, description="Total amount (includes GST)"
    )
    deposit_paid: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Deposit paid upfront"
    )

    # Status
    status: str = Field(
        default="Quote",
        description="Quote, Confirmed, Assigned, In Progress, Completed, Cancelled",
    )
    cancellation_reason: Optional[str] = Field(
        None, description="Reason for cancellation"
    )
    reference_number: Optional[str] = Field(
        None, description="Customer reference (PO, etc)"
    )

    @validator("charter_date")
    def validate_date(cls, v):
        """Charter date must be >= today."""
        if v < date.today():
            raise ValueError("charter_date must be today or later")
        return v

    @validator("pickup_time")
    def validate_pickup_time(cls, v):
        """Validate pickup time format HH:MM."""
        try:
            time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("pickup_time must be in HH:MM format")

    @validator("status")
    def validate_status(cls, v):
        """Status must be one of allowed values."""
        valid_statuses = [
            "Quote",
            "Confirmed",
            "Assigned",
            "In Progress",
            "Completed",
            "Cancelled",
        ]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v

    @validator("itinerary")
    def validate_itinerary(cls, v):
        """Itinerary must have at least 2 stops (pickup + dropoff)."""
        if len(v) < 2:
            raise ValueError("itinerary must have at least 2 stops (pickup + dropoff)")
        return v

    @validator("total_amount_due")
    def validate_total_amount(cls, v):
        """Total amount must be positive."""
        if v <= 0:
            raise ValueError("total_amount_due must be > 0")
        return v

    @validator("passenger_load")
    def validate_passenger_load(cls, v):
        """Passenger load must be 1-50."""
        if not 1 <= v <= 50:
            raise ValueError("passenger_load must be between 1 and 50")
        return v


class ChartResponse(BaseModel):
    """
    Response after successful charter creation.

    Contains charter_id (internal), reserve_number (business key),
    status, and timestamp.
    """

    charter_id: int = Field(..., description="Internal charter ID")
    reserve_number: str = Field(
        ..., description="6-digit business key (e.g., '019233')"
    )
    status: str = Field(..., description="Current booking status")
    created_at: datetime = Field(..., description="Timestamp of creation")

    class Config:
        """Allow arbitrary types for datetime."""

        arbitrary_types_allowed = True


class CharterSearch(BaseModel):
    """
    Search result for charter.

    Used in GET /api/charters/search response.
    """

    charter_id: int
    reserve_number: str
    client_name: str
    charter_date: date
    status: str
    total_amount_due: str

    class Config:
        """Allow arbitrary types."""

        arbitrary_types_allowed = True


class CustomerSearch(BaseModel):
    """
    Search result for customer autocomplete.

    Used in GET /api/customers/search response.
    """

    client_id: int
    client_name: str
    phone: str
    email: str


class VehicleResponse(BaseModel):
    """
    Vehicle details for dropdown selection.

    Used in GET /api/vehicles response.
    """

    vehicle_id: int
    vehicle_number: str
    make: str
    model: str
    year: int
    passenger_capacity: int


class DriverResponse(BaseModel):
    """
    Driver details for dropdown selection.

    Used in GET /api/employees/drivers response.
    """

    employee_id: int
    first_name: str
    last_name: str
    driver_license: str


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """

    status_code: int
    error: str
    detail: Optional[str] = None


# ============================================================================
# BUSINESS RULE CONSTANTS
# ============================================================================

GST_RATE = Decimal("0.05")  # Alberta 5% GST
# Tax-included formula: gst = total * 0.05 / 1.05
GST_DIVISOR = Decimal("1.05")

VALID_STATUSES = [
    "Quote",
    "Confirmed",
    "Assigned",
    "In Progress",
    "Completed",
    "Cancelled",
]
VALID_ROUTE_TYPES = ["pickup", "dropo", "stop", "depart", "return"]

# Payment methods
VALID_PAYMENT_METHODS = [
    "cash",
    "check",
    "credit_card",
    "debit_card",
    "bank_transfer",
    "trade_of_services",
    "unknown",
]

# Charge types (for line-item pricing)
CHARGE_TYPE_BASE = "base_rate"
CHARGE_TYPE_AIRPORT = "airport_fee"
CHARGE_TYPE_ADDITIONAL = "additional"
CHARGE_TYPE_GST = "gst"


def calculate_gst(total_amount: Decimal) -> Decimal:
    """
    Calculate GST amount from tax-included total.

    Alberta uses 5% GST that is INCLUDED in the total price.

    Formula: gst = total * 0.05 / 1.05

    Example:
        total = $258.75
        gst = 258.75 * 0.05 / 1.05 = $12.32
        net = 258.75 - 12.32 = $246.43

    Args:
        total_amount: Total amount including GST

    Returns:
        GST amount rounded to 2 decimals
    """
    gst = (total_amount * GST_RATE / GST_DIVISOR).quantize(Decimal("0.01"))
    return gst
