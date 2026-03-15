"""Pydantic models for Charter Routes."""

from datetime import time, datetime
from typing import Optional
from pydantic import BaseModel, Field


class CharterRouteBase(BaseModel):
    """Base model for charter route."""
    route_sequence: int = Field(..., ge=1, description="Route order (1, 2, 3, ...)")
    event_type_code: Optional[str] = Field(None, description="Event type: pickup, dropoff, leave_red_deer, etc.")
    address: Optional[str] = Field(None, description="Unified address for any event type")
    stop_time: Optional[time] = Field(None, description="Time of this routing event")
    reserve_number: Optional[str] = Field(None, description="Business key linking to charter")
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_duration_minutes: Optional[int] = Field(None, ge=0)
    estimated_distance_km: Optional[float] = Field(None, ge=0)
    actual_distance_km: Optional[float] = Field(None, ge=0)
    route_price: Optional[float] = Field(None, ge=0)
    route_notes: Optional[str] = None
    route_status: str = Field(default="pending", pattern="^(pending|in_progress|completed|cancelled)$")


class CharterRouteCreate(CharterRouteBase):
    """Model for creating a new charter route."""
    charter_id: int = Field(..., gt=0)


class CharterRouteUpdate(BaseModel):
    """Model for updating a charter route (all fields optional)."""
    route_sequence: Optional[int] = Field(None, ge=1)
    pickup_location: Optional[str] = None
    pickup_time: Optional[time] = None
    dropoff_location: Optional[str] = None
    dropoff_time: Optional[time] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_duration_minutes: Optional[int] = Field(None, ge=0)
    estimated_distance_km: Optional[float] = Field(None, ge=0)
    actual_distance_km: Optional[float] = Field(None, ge=0)
    route_price: Optional[float] = Field(None, ge=0)
    route_notes: Optional[str] = None
    route_status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed|cancelled)$")


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
    reserve_number: Optional[str] = None
    charter_date: Optional[datetime] = None
    client_id: Optional[int] = None
    status: Optional[str] = None
    
    # Route totals
    total_routes: int = 0
    total_estimated_minutes: Optional[int] = None
    total_actual_minutes: Optional[int] = None
    total_estimated_km: Optional[float] = None
    total_actual_km: Optional[float] = None
    total_route_price: Optional[float] = None
    
    # Routes list
    routes: list[CharterRoute] = []
    
    class Config:
        from_attributes = True
