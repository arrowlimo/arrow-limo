#!/usr/bin/env python
"""
Test fill_cra_form.py with the refined mapping
"""
import sys
from pathlib import Path

# Add cra to path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fill_cra_form import compute_fields

# Load refined mapping
mapping = json.loads(Path(__file__).with_name('mapping_gst_refined.json').read_text())

# Test 2025Q3
print("Testing GST34 for 2025Q3 with refined mapping:\n")
values = compute_fields(mapping, '2025Q3')

for k, v in values.items():
    print(f"  {k}: ${v:,.2f}")

print(f"\nTotal: {len(values)} fields computed")
