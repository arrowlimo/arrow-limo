"""Pydantic models for Charter Routes."""

from datetime import datetime, time

from pydantic import BaseModel, Field


class CharterRouteBase(BaseModel):
    """Base model for charter route."""

    route_sequence: int = Field(..., ge=1, description="Route order (1, 2, 3, ...)")
    event_type_code: str | None = Field(
        None, description="Event type: pickup, dropoff, leave_red_deer, etc."
    )
    address: str | None = Field(
        None, description="Unified address for any event type"
    )
    stop_time: time | None = Field(None, description="Time of this routing event")
    reserve_number: str | None = Field(
        None, description="Business key linking to charter"
    )
    estimated_duration_minutes: int | None = Field(None, ge=0)
    actual_duration_minutes: int | None = Field(None, ge=0)
    estimated_distance_km: float | None = Field(None, ge=0)
    actual_distance_km: float | None = Field(None, ge=0)
    route_price: float | None = Field(None, ge=0)
    route_notes: str | None = None
    route_status: str = Field(
        default="pending",
        pattern="^(pending|in_progress|completed|cancelled)$",
    )


class CharterRouteCreate(CharterRouteBase):
    """Model for creating a new charter route."""

    charter_id: int = Field(..., gt=0)


class CharterRouteUpdate(BaseModel):
    """Model for updating a charter route (all fields optional)."""

    route_sequence: int | None = Field(None, ge=1)
    pickup_location: str | None = None
    pickup_time: time | None = None
    dropoff_location: str | None = None
    dropoff_time: time | None = None
    estimated_duration_minutes: int | None = Field(None, ge=0)
    actual_duration_minutes: int | None = Field(None, ge=0)
    estimated_distance_km: float | None = Field(None, ge=0)
    actual_distance_km: float | None = Field(None, ge=0)
    route_price: float | None = Field(None, ge=0)
    route_notes: str | None = None
    route_status: str | None = Field(
        None, pattern="^(pending|in_progress|completed|cancelled)$"
    )


class CharterRoute(CharterRouteBase):
    """Model for reading a charter route (includes database fields)."""

    route_id: int
    charter_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CharterWithRoutes(BaseModel):
    """Charter with all its routes and calculated totals."""

    charter_id: int
    reserve_number: str | None = None
    charter_date: datetime | None = None
    client_id: int | None = None
    status: str | None = None

    # Route totals
    total_routes: int = 0
    total_estimated_minutes: int | None = None
    total_actual_minutes: int | None = None
    total_estimated_km: float | None = None
    total_actual_km: float | None = None
    total_route_price: float | None = None

    # Routes list
    routes: list[CharterRoute] = []

    class Config:
        from_attributes = True
