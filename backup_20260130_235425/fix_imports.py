#!/usr/bin/env python
"""Fix main.py imports - add dashboard_classes import after typing import"""

import os
import sys

os.chdir(r'l:\limo\desktop_app')

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "from typing import" 
import_idx = None
for i, line in enumerate(lines):
    if 'from typing import' in line:
        import_idx = i
        break

if import_idx is not None:
    print(f"Found 'from typing' at line {import_idx + 1}")
    
    # Find the line after typing import (should be comment or next section)
    next_idx = import_idx + 1
    
    # Insert the new import after typing import
    new_imports = [
        "\n",
        "# Add current directory to path for dashboard imports\n",
        "sys.path.insert(0, os.path.dirname(__file__))\n",
        "from dashboard_classes import (\n",
        "    FleetManagementWidget, DriverPerformanceWidget,\n",
        "    FinancialDashboardWidget, PaymentReconciliationWidget\n",
        ")\n"
    ]
    
    lines[next_idx:next_idx] = new_imports
    
    # Write the modified file
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Import statement added successfully")
    print(f"File size: {len(lines)} lines")
else:
    print("Could not find 'from typing import' line")
