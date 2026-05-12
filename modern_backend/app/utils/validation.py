"""Shared validation helpers for API routers."""

from fastapi import HTTPException


def validate_tax_year(tax_year: int, min_year: int = 2000, max_year: int = 2100) -> int:
    """Validate tax year is within an operational range."""

    if tax_year < min_year or tax_year > max_year:
        raise HTTPException(
            status_code=422,
            detail=f"tax_year must be between {min_year} and {max_year}",
        )
    return tax_year
