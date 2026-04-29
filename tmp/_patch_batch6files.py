"""Patch 6 files: charters router, vehicle_booked_out, outlook_calendar,
dashboards_phase2_phase3, split_receipt_creation_dialog, dashboards_phase11."""
import ast
from pathlib import Path

# === modern_backend/app/routers/charters.py ===
p = Path("modern_backend/app/routers/charters.py")
src = p.read_text(encoding="utf-8")
src = src.replace(
    "        where = \"WHERE (c.charter_id::text ILIKE %s OR COALESCE(cl.client_name,'') ILIKE %s)\"",
    "        where = (\n"
    "            \"WHERE (c.charter_id::text ILIKE %s\"\n"
    "            \" OR COALESCE(cl.client_name,'') ILIKE %s)\"\n"
    "        )",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  charters.py")
except SyntaxError as e:
    print(f"AST_FAIL charters.py: {e}")

# === desktop_app/vehicle_booked_out_widget.py ===
p = Path("desktop_app/vehicle_booked_out_widget.py")
src = p.read_text(encoding="utf-8")

src = src.replace(
    "                        CASE WHEN LOWER(COALESCE({status_col}, '')) = 'active' THEN 0 ELSE 1 END,",
    "                        CASE WHEN LOWER(\n"
    "                            COALESCE({status_col}, '')\n"
    "                        ) = 'active' THEN 0 ELSE 1 END,",
    1,
)
src = src.replace(
    "                                THEN CAST(regexp_replace(vehicle_number, '[^0-9]', '', 'g') AS INT)",
    "                                THEN CAST(regexp_replace(\n"
    "                                    vehicle_number, '[^0-9]', '', 'g'\n"
    "                                ) AS INT)",
    1,
)
src = src.replace(
    "                      AND (status IS NULL OR status NOT IN ('cancelled', 'no-show'))",
    "                      AND (status IS NULL\n"
    "                          OR status NOT IN ('cancelled', 'no-show'))",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  vehicle_booked_out_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL vehicle_booked_out_widget.py: {e}")

# === desktop_app/outlook_style_calendar_widget.py ===
p = Path("desktop_app/outlook_style_calendar_widget.py")
src = p.read_text(encoding="utf-8")

for col in ["calendar_notes", "calendar_color", "quote_expires_at", "charter_hours"]:
    src = src.replace(
        f"                    WHERE table_schema='public' AND table_name='charters' AND column_name='{col}'",
        f"                    WHERE table_schema='public'\n"
        f"                        AND table_name='charters'\n"
        f"                        AND column_name='{col}'",
        1,
    )

src = src.replace(
    "        Returns list of dicts with 'start_time', 'end_time', 'event_type', 'label' for each segment.",
    "        Returns list of dicts with 'start_time', 'end_time',\n"
    "        'event_type', 'label' for each segment.",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  outlook_style_calendar_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL outlook_style_calendar_widget.py: {e}")

# === desktop_app/dashboards_phase2_phase3.py ===
p = Path("desktop_app/dashboards_phase2_phase3.py")
src = p.read_text(encoding="utf-8")

for kw in ["fuel", "maint", "insur"]:
    col = {"fuel": "fuel_cost", "maint": "maint_cost", "insur": "insur_cost"}[kw]
    src = src.replace(
        f"                           COALESCE(SUM(CASE WHEN r.description ILIKE '%{kw}%' THEN r.gross_amount ELSE 0 END), 0) as {col},",
        f"                           COALESCE(SUM(CASE\n"
        f"                               WHEN r.description ILIKE '%{kw}%'\n"
        f"                               THEN r.gross_amount ELSE 0 END), 0) as {col},",
        1,
    )

src = src.replace(
    "                           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,",
    "                           SUM(CASE WHEN status = 'cancelled'\n"
    "                               THEN 1 ELSE 0 END) as cancelled,",
    1,
)
src = src.replace(
    "                           SUM(CASE WHEN status = 'completed' THEN total_amount_due ELSE 0 END) as completed_revenue",
    "                           SUM(CASE WHEN status = 'completed'\n"
    "                               THEN total_amount_due ELSE 0 END) as completed_revenue",
    1,
)
src = src.replace(
    "                    SELECT 'Insurance' as type, policy_number, 'Active', expiry_date,",
    "                    SELECT 'Insurance' as type, policy_number,\n"
    "                           'Active', expiry_date,",
    1,
)
src = src.replace(
    "                    SELECT 'License' as type, license_number, license_status, expiry_date,",
    "                    SELECT 'License' as type, license_number,\n"
    "                           license_status, expiry_date,",
    1,
)
src = src.replace(
    "                    WHERE status = 'active' OR expiry_date >= CURRENT_DATE - INTERVAL '30 days'",
    "                    WHERE status = 'active'\n"
    "                        OR expiry_date >= CURRENT_DATE - INTERVAL '30 days'",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  dashboards_phase2_phase3.py")
except SyntaxError as e:
    print(f"AST_FAIL dashboards_phase2_phase3.py: {e}")

# === desktop_app/split_receipt_creation_dialog.py ===
p = Path("desktop_app/split_receipt_creation_dialog.py")
src = p.read_text(encoding="utf-8")

# Two near-identical lines (418, 426) - different indentation
src = src.replace(
    "                border: 2px solid {'#4CAF50' if difference < 0.01 else '#FF5252'};",
    "                border: 2px solid {\n"
    "                    '#4CAF50' if difference < 0.01 else '#FF5252'};",
    1,
)
src = src.replace(
    "                    border: 2px solid {'#4CAF50' if difference < 0.01 else '#FF5252'};",
    "                    border: 2px solid {\n"
    "                        '#4CAF50' if difference < 0.01 else '#FF5252'};",
    1,
)
src = src.replace(
    "                    UPDATE receipts SET split_status = 'split_reconciled' WHERE receipt_id = %s",
    "                    UPDATE receipts\n"
    "                    SET split_status = 'split_reconciled'\n"
    "                    WHERE receipt_id = %s",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  split_receipt_creation_dialog.py")
except SyntaxError as e:
    print(f"AST_FAIL split_receipt_creation_dialog.py: {e}")

# === desktop_app/dashboards_phase11.py ===
p = Path("desktop_app/dashboards_phase11.py")
src = p.read_text(encoding="utf-8")

# 5 identical WHERE lines
count = src.count("                    WHERE e.is_chauffeur = true AND e.employment_status = 'active'")
src = src.replace(
    "                    WHERE e.is_chauffeur = true AND e.employment_status = 'active'",
    "                    WHERE e.is_chauffeur = true\n"
    "                        AND e.employment_status = 'active'",
)
print(f"Replaced {count} occurrences of is_chauffeur WHERE clause")

# Line 183 - long SELECT
src = src.replace(
    "                    SELECT COALESCE(SUBSTRING(charter_date::text, 1, 10), 'Local'), COUNT(*), COALESCE(AVG(total_amount_due), 0)",
    "                    SELECT\n"
    "                        COALESCE(SUBSTRING(charter_date::text, 1, 10), 'Local'),\n"
    "                        COUNT(*),\n"
    "                        COALESCE(AVG(total_amount_due), 0)",
    1,
)
p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  dashboards_phase11.py")
except SyntaxError as e:
    print(f"AST_FAIL dashboards_phase11.py: {e}")
