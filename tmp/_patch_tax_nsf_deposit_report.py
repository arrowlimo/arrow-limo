"""Patch tax_optimization_module.py, nsf_pair_manager_widget.py,
deposit_slip_dialog.py, report_management_widget.py."""
import ast
from pathlib import Path

# === tax_optimization_module.py ===
p = Path("desktop_app/tax_optimization_module.py")
src = p.read_text(encoding="utf-8")

# Lines 136-137 and 588-589 are identical SQL blocks — patch both
gst_old = (
    "                    COALESCE(SUM(CASE WHEN account LIKE '%GST%Collected%' THEN credit ELSE 0 END), 0) as gst_collected,\n"
    "                    COALESCE(SUM(CASE WHEN account LIKE '%GST%Paid%' THEN debit ELSE 0 END), 0) as gst_paid"
)
gst_new = (
    "                    COALESCE(SUM(CASE WHEN account LIKE '%GST%Collected%'\n"
    "                        THEN credit ELSE 0 END), 0) as gst_collected,\n"
    "                    COALESCE(SUM(CASE WHEN account LIKE '%GST%Paid%'\n"
    "                        THEN debit ELSE 0 END), 0) as gst_paid"
)
count = src.count(gst_old)
if count == 2:
    src = src.replace(gst_old, gst_new)  # replaces both
    print(f"Replaced {count} occurrences of GST CASE block")
elif count == 1:
    src = src.replace(gst_old, gst_new, 1)
    print("Replaced 1 occurrence of GST CASE block")
else:
    print(f"WARN: GST block found {count} times")

# Line 671 - Fuel/Maintenance OR split
src = src.replace(
    "                    WHERE vendor_name LIKE '%Fuel%' OR vendor_name LIKE '%Maintenance%'",
    "                    WHERE vendor_name LIKE '%Fuel%'\n"
    "                        OR vendor_name LIKE '%Maintenance%'",
    1,
)

# Line 717 - Home/Office OR split
src = src.replace(
    "                    AND vendor_name LIKE '%Home%' OR vendor_name LIKE '%Office%'",
    "                    AND vendor_name LIKE '%Home%'\n"
    "                        OR vendor_name LIKE '%Office%'",
    1,
)

# Line 746 - Training/Course OR split
src = src.replace(
    "                    AND vendor_name LIKE '%Training%' OR vendor_name LIKE '%Course%'",
    "                    AND vendor_name LIKE '%Training%'\n"
    "                        OR vendor_name LIKE '%Course%'",
    1,
)

# Line 773 - Restaurant/Cafe OR split
src = src.replace(
    "                    AND vendor_name LIKE '%Restaurant%' OR vendor_name LIKE '%Cafe%'",
    "                    AND vendor_name LIKE '%Restaurant%'\n"
    "                        OR vendor_name LIKE '%Cafe%'",
    1,
)

# Line 909 - print f-string
src = src.replace(
    "        f\"Suggestions Found: {len(deductions.get('deduction_suggestions', []))}\"\n"
    "    )",
    "        f\"Suggestions Found: \"\n"
    "        f\"{len(deductions.get('deduction_suggestions', []))}\"\n"
    "    )",
    1,
)

p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  tax_optimization_module.py")
except SyntaxError as e:
    print(f"AST_FAIL tax_optimization_module.py: {e}")

# === nsf_pair_manager_widget.py ===
p2 = Path("desktop_app/nsf_pair_manager_widget.py")
src2 = p2.read_text(encoding="utf-8")

# Lines 223-227 - over-indented OR clauses — reindent to match 220-222 level
src2 = src2.replace(
    "                                                                         OR bt.description ILIKE '%%CANCEL%%'\n"
    "                                                                         OR bt.description ILIKE '%%REVERS%%'\n"
    "                                                                         OR bt.description ILIKE '%%REVERSE%%'\n"
    "                                                                         OR bt.description ILIKE '%%E-TRANSFER%%'\n"
    "                                                                         OR bt.description ILIKE '%%ETRANSFER%%'",
    "                                     OR bt.description ILIKE '%%CANCEL%%'\n"
    "                                     OR bt.description ILIKE '%%REVERS%%'\n"
    "                                     OR bt.description ILIKE '%%REVERSE%%'\n"
    "                                     OR bt.description ILIKE '%%E-TRANSFER%%'\n"
    "                                     OR bt.description ILIKE '%%ETRANSFER%%'",
    1,
)

# Line 467 - COALESCE category split
src2 = src2.replace(
    "                               category = COALESCE(NULLIF(category, ''), 'INTERNAL_TRANSFER_REVERSAL'),",
    "                               category = COALESCE(\n"
    "                                   NULLIF(category, ''),\n"
    "                                   'INTERNAL_TRANSFER_REVERSAL'\n"
    "                               ),",
    1,
)

# Line 470 - WHEN COALESCE split
src2 = src2.replace(
    "                                   WHEN COALESCE(reconciliation_notes, '') = '' THEN %s",
    "                                   WHEN COALESCE(\n"
    "                                       reconciliation_notes, ''\n"
    "                                   ) = '' THEN %s",
    1,
)

p2.write_text(src2, encoding="utf-8")
try:
    ast.parse(src2)
    print("AST_OK  nsf_pair_manager_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL nsf_pair_manager_widget.py: {e}")

# === deposit_slip_dialog.py ===
p3 = Path("desktop_app/deposit_slip_dialog.py")
src3 = p3.read_text(encoding="utf-8")

# Line 549 - nested f-string with ternary
src3 = src3.replace(
    "                f\"{'✅ Fully balanced.' if new_status == 'balanced' else f'⚠️ Gap remaining: ${gap:.2f}'}\",",
    "                (\n"
    "                    '✅ Fully balanced.' if new_status == 'balanced'\n"
    "                    else f'⚠️ Gap remaining: ${gap:.2f}'\n"
    "                ),",
    1,
)

p3.write_text(src3, encoding="utf-8")
try:
    ast.parse(src3)
    print("AST_OK  deposit_slip_dialog.py")
except SyntaxError as e:
    print(f"AST_FAIL deposit_slip_dialog.py: {e}")

# === report_management_widget.py ===
p4 = Path("desktop_app/report_management_widget.py")
src4 = p4.read_text(encoding="utf-8")

# Line 460 - long string literal
src4 = src4.replace(
    '            status_text += "Type: Flat PDF (no form fields)\\nNote: Will generate overlay PDFs"',
    '            status_text += (\n'
    '                "Type: Flat PDF (no form fields)\\n"\n'
    '                "Note: Will generate overlay PDFs"\n'
    "            )",
    1,
)

p4.write_text(src4, encoding="utf-8")
try:
    ast.parse(src4)
    print("AST_OK  report_management_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL report_management_widget.py: {e}")
