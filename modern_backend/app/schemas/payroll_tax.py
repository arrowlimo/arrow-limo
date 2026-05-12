"""Typed response schemas for payroll and T4 endpoints."""

from pydantic import BaseModel


class T4EntryResponse(BaseModel):
    employee_id: int
    tax_year: int
    box14: float
    box16: float
    box18: float
    box22: float
    box24: float
    box26: float
    box44: float
    box46: float
    box52: float
    auto_box14: float
    auto_box16: float
    auto_box18: float
    auto_box22: float
    auto_box24: float
    auto_box26: float
    auto_box44: float
    auto_box46: float
    auto_box52: float
    notes: str
