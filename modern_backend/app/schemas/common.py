"""Shared API response schemas."""

from pydantic import BaseModel


class StatusMessageResponse(BaseModel):
    """Simple success/failure payload used by mutation endpoints."""

    status: str
    message: str
