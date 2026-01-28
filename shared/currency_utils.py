"""
Shared currency calculation utilities (GST, rounding, formatting).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple


def calculate_gst(gross_amount: Decimal, tax_rate: Decimal = Decimal('0.05')) -> Tuple[Decimal, Decimal]:
    """
    Calculate GST (tax included, Alberta 5%).
    
    GST is INCLUDED in the gross amount.
    Returns: (gst_amount, net_amount)
    
    Example:
        gst, net = calculate_gst(Decimal('682.50'))
        # gst=32.50, net=650.00
    """
    gross = Decimal(str(gross_amount))
    rate = Decimal(str(tax_rate))
    
    gst_amount = (gross * rate) / (1 + rate)
    net_amount = gross - gst_amount
    
    return round_currency(gst_amount), round_currency(net_amount)


def round_currency(amount: Decimal) -> Decimal:
    """Round to 2 decimal places (banker's rounding)."""
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def format_currency(amount: Decimal) -> str:
    """Format currency as $X,XXX.XX."""
    amount_dec = Decimal(str(amount))
    return f"${amount_dec:,.2f}"


def validate_currency(value: str) -> Decimal:
    """Parse and validate currency input."""
    try:
        # Remove $ and commas
        cleaned = value.replace('$', '').replace(',', '').strip()
        amount = Decimal(cleaned)
        return round_currency(amount)
    except Exception:
        raise ValueError(f"Invalid currency value: {value}")
