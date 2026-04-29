"""Patch employee_pay_ledger_widget.py and custom_report_builder.py."""
import ast
from pathlib import Path

# === employee_pay_ledger_widget.py ===
p = Path("desktop_app/employee_pay_ledger_widget.py")
src = p.read_text(encoding="utf-8")

# Line 4 - module docstring
src = src.replace(
    'Shows a "verified pay vs actual payments" ledger for a selected employee + period.',
    'Shows a "verified pay vs actual payments" ledger for a selected\nemployee + period.',
    1,
)

# Line 416 - class docstring
src = src.replace(
    "    'Pay Verification' group \u2014 shows calculated net pay vs actual payments made.",
    "    'Pay Verification' group \u2014 shows calculated net pay\n"
    "    vs actual payments made.",
    1,
)

# Line 541 - SQL DDL inside triple-quoted string
src = src.replace(
    "                        pay_type         VARCHAR(30) NOT NULL DEFAULT 'REGULAR_PAY',",
    "                        pay_type         VARCHAR(30) NOT NULL\n"
    "                            DEFAULT 'REGULAR_PAY',",
    1,
)

p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  employee_pay_ledger_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL employee_pay_ledger_widget.py: {e}")

# === custom_report_builder.py ===
p2 = Path("desktop_app/custom_report_builder.py")
src2 = p2.read_text(encoding="utf-8")

# Line 783 - SQL CASE WHEN regexp line
src2 = src2.replace(
    "                            WHEN vehicle_number ~ '^[Ll]-?\\\\d+$' THEN CAST(regexp_replace(vehicle_number, '[^0-9]', '', 'g') AS INT)",
    "                            WHEN vehicle_number ~ '^[Ll]-?\\\\d+$'\n"
    "                            THEN CAST(regexp_replace(\n"
    "                                vehicle_number, '[^0-9]', '', 'g'\n"
    "                            ) AS INT)",
    1,
)

# Line 1137 - CSV filename f-string
src2 = src2.replace(
    "                f\"{self.primary_table.currentText()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv\",",
    '                f"{self.primary_table.currentText()}_"\n'
    "                f\"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv\",",
    1,
)

# Line 1183 - DOCX filename f-string
src2 = src2.replace(
    "                f\"{self.primary_table.currentText()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx\",",
    '                f"{self.primary_table.currentText()}_"\n'
    "                f\"{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx\",",
    1,
)

# Line 1592 - hovertemplate y
src2 = src2.replace(
    '                                        hovertemplate="%{y:,.2f}<extra></extra>",',
    "                                        hovertemplate=(\n"
    '                                            "%{y:,.2f}<extra></extra>"\n'
    "                                        ),",
    1,
)

# Line 1633 - hovertemplate x/y scatter
src2 = src2.replace(
    '                                hovertemplate="%{x:,.2f}, %{y:,.2f}<extra></extra>",',
    "                                hovertemplate=(\n"
    '                                    "%{x:,.2f}, %{y:,.2f}"\n'
    '                                    "<extra></extra>"\n'
    "                                ),",
    1,
)

# Line 1638 - scatter title f-string
src2 = src2.replace(
    "                        title=f\"Scatter: {numeric_cols_data[0][0]} vs {numeric_cols_data[1][0]}\",",
    "                        title=(\n"
    '                            f"Scatter: {numeric_cols_data[0][0]}"\n'
    '                            f" vs {numeric_cols_data[1][0]}"\n'
    "                        ),",
    1,
)

# Line 1744 - hovertemplate treemap
src2 = src2.replace(
    '                    hovertemplate="<b>%{label}</b><br>Amount: $%{value:,.2f}<extra></extra>",',
    "                    hovertemplate=(\n"
    '                        "<b>%{label}</b><br>Amount: $%{value:,.2f}"\n'
    '                        "<extra></extra>"\n'
    "                    ),",
    1,
)

p2.write_text(src2, encoding="utf-8")
try:
    ast.parse(src2)
    print("AST_OK  custom_report_builder.py")
except SyntaxError as e:
    print(f"AST_FAIL custom_report_builder.py: {e}")
