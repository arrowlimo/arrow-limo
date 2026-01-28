#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate concise vendor groups summary
"""

print("\n" + "="*110)
print("TOP VENDOR GROUPS WITH VARIATIONS - SUMMARY")
print("="*110 + "\n")

print("GROUP 1: FAS GAS (443 total transactions)")
print("  - FAS GAS (base): 130 transactions")
print("  - 313 variants with receipt numbers like: FAS GAS 000001210002, FAS GAS 000001996008")
print("  - ANALYSIS: Receipt numbers are unique transaction IDs - DO NOT COMBINE")
print()

print("GROUP 2: PETRO CANADA (177 total transactions)")
print("  - PETRO CANADA (base): 23 transactions")
print("  - 154 variants with receipt numbers")
print("  - ANALYSIS: Receipt numbers are unique - DO NOT COMBINE")
print()

print("GROUP 3: SHELL (105 total transactions)")
print("  - SHELL (base): 20 transactions")
print("  - 85 variants with receipt numbers")
print("  - ANALYSIS: Receipt numbers are unique - DO NOT COMBINE")
print()

print("GROUP 4: ESSO (90 total transactions)")
print("  - ESSO (base): 24 transactions")
print("  - 66 variants with receipt numbers")
print("  - ANALYSIS: Receipt numbers are unique - DO NOT COMBINE")
print()

print("GROUP 5: HUSKY (similar pattern)")
print("GROUP 6: CO-OP (similar pattern)")
print("GROUP 7: TIM HORTONS (similar pattern)")
print("GROUP 8: CANADIAN TIRE (similar pattern)")
print()

print("="*110)
print("GROUPS WITH TRUE NAME VARIATIONS (Actionable)")
print("="*110 + "\n")

print("1. WALMART variations:")
print("   - WAL-MART #3075 → should be: WALMART")
print("   - Transactions: 2")
print()

print("2. 7-ELEVEN variations:")
print("   - 7 ELEVEN → should be: 7-ELEVEN")
print("   - Transactions: 4")
print()

print("3. SUPERSTORE variations:")
print("   - REAL CANADIAN SUPERSTORE → should be: SUPERSTORE")
print("   - Transactions: 1")
print()

print("="*110)
print("RECOMMENDATION")
print("="*110 + "\n")

print("✅ KEEP SEPARATE:")
print("   - All receipt number variants (FAS GAS 000001210002, etc.)")
print("   - These are unique transaction identifiers from receipt imports")
print()

print("✅ STANDARDIZE ONLY:")
print("   - WAL-MART → WALMART")
print("   - 7 ELEVEN → 7-ELEVEN")
print("   - REAL CANADIAN SUPERSTORE → SUPERSTORE")
print()

print("📊 IMPACT:")
print("   - Total vendors with variations: 5,286")
print("   - Vendors needing standardization: 3")
print("   - Transactions affected: 7")
print()

print("✅ Current vendor standardization is EXCELLENT - minimal work needed!")
print()
