"""
Business logic tests (GST, currency, date handling).
"""
import pytest
from decimal import Decimal

def calculate_gst(gross_amount, tax_rate=Decimal("0.05")):
    """GST calculation (tax included in amount)."""
    gst_amount = gross_amount * tax_rate / (1 + tax_rate)
    net_amount = gross_amount - gst_amount
    return gst_amount.quantize(Decimal("0.01")), net_amount.quantize(Decimal("0.01"))

def test_gst_calculation_standard():
    """Test GST calculation with standard 5% rate."""
    gross = Decimal("682.50")
    gst, net = calculate_gst(gross)
    
    assert gst == Decimal("32.50")
    assert net == Decimal("650.00")
    assert gst + net == gross

def test_gst_calculation_zero():
    """Test GST calculation with zero amount."""
    gross = Decimal("0.00")
    gst, net = calculate_gst(gross)
    
    assert gst == Decimal("0.00")
    assert net == Decimal("0.00")

def test_gst_calculation_large_amount():
    """Test GST calculation with large amount."""
    gross = Decimal("10500.00")
    gst, net = calculate_gst(gross)
    
    assert gst == Decimal("500.00")
    assert net == Decimal("10000.00")

def test_currency_rounding():
    """Test currency rounding to 2 decimal places."""
    values = [
        (Decimal("10.126"), Decimal("10.13")),
        (Decimal("10.124"), Decimal("10.12")),
        (Decimal("10.125"), Decimal("10.12")),  # Banker's rounding
    ]
    
    for input_val, expected in values:
        rounded = input_val.quantize(Decimal("0.01"))
        assert rounded == expected

def test_reserve_number_format():
    """Test reserve number format validation."""
    import re
    
    valid_reserves = ["025432", "019233", "000001", "999999"]
    invalid_reserves = ["25432", "ABC123", "1234567", ""]
    
    pattern = r"^\d{6}$"
    
    for reserve in valid_reserves:
        assert re.match(pattern, reserve), f"{reserve} should be valid"
    
    for reserve in invalid_reserves:
        assert not re.match(pattern, reserve), f"{reserve} should be invalid"
