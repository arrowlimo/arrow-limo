#!/usr/bin/env python
"""Quick test to validate PDF generator implementation"""
import sys
sys.path.insert(0, 'l:\\limo\\modern_backend')

from app.services.pdf_generator import CharterPDFForm

print('✓ Import successful')
print(f'✓ Has _draw_driver_and_vehicle: {hasattr(CharterPDFForm, "_draw_driver_and_vehicle")}')
print(f'✓ Has _friendly_route_label: {hasattr(CharterPDFForm, "_friendly_route_label")}')
print(f'✓ Has _format_time: {hasattr(CharterPDFForm, "_format_time")}')
print(f'✓ Has _safe: {hasattr(CharterPDFForm, "_safe")}')

# Try to instantiate
try:
    form = CharterPDFForm(data={})
    print('✓ CharterPDFForm instantiates without error')
except Exception as e:
    print(f'✗ Error instantiating: {e}')
