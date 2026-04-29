"""Patch dispatch_management_widget.py and client_drill_down.py E501 lines."""
import ast
from pathlib import Path

# === dispatch_management_widget.py ===
p = Path("desktop_app/dispatch_management_widget.py")
src = p.read_text(encoding="utf-8")

# Line 84 - COALESCE client_name split
src = src.replace(
    "                        COALESCE(c.client_display_name, cl.company_name, cl.client_name, 'Unknown') as client_name,",
    "                        COALESCE(\n"
    "                            c.client_display_name, cl.company_name,\n"
    "                            cl.client_name, 'Unknown'\n"
    "                        ) as client_name,",
    1,
)

# Line 96 - COALESCE vehicle_dispatched
src = src.replace(
    "                        COALESCE(v.vehicle_number, c.vehicle, '') as vehicle_dispatched,",
    "                        COALESCE(\n"
    "                            v.vehicle_number, c.vehicle, ''\n"
    "                        ) as vehicle_dispatched,",
    1,
)

# Line 97 - COALESCE driver
src = src.replace(
    "                        COALESCE(e.full_name, e2.full_name, c.driver, '') as driver,",
    "                        COALESCE(\n"
    "                            e.full_name, e2.full_name, c.driver, ''\n"
    "                        ) as driver,",
    1,
)

# Line 98 - COALESCE status
src = src.replace(
    "                        COALESCE(c.payment_status, c.status, 'Pending') as status,",
    "                        COALESCE(\n"
    "                            c.payment_status, c.status, 'Pending'\n"
    "                        ) as status,",
    1,
)

# Line 102 - TO_CHAR dropoff_time_fmt
src = src.replace(
    "                        TO_CHAR(COALESCE(c.do_time, c.dropoff_time), 'HH24:MI') as dropoff_time_fmt,",
    "                        TO_CHAR(\n"
    "                            COALESCE(c.do_time, c.dropoff_time),\n"
    "                            'HH24:MI'\n"
    "                        ) as dropoff_time_fmt,",
    1,
)

# Line 105 - COALESCE driver_notes
src = src.replace(
    "                        COALESCE(c.driver_notes, c.notes, c.vehicle_notes, '') as driver_notes,",
    "                        COALESCE(\n"
    "                            c.driver_notes, c.notes, c.vehicle_notes, ''\n"
    "                        ) as driver_notes,",
    1,
)

# Line 283 - long method chain
src = src.replace(
    "        self.bookings_table.horizontalHeader().customContextMenuRequested.connect(\n"
    "            self.show_column_menu",
    "        _hdr = self.bookings_table.horizontalHeader()\n"
    "        _hdr.customContextMenuRequested.connect(\n"
    "            self.show_column_menu",
    1,
)

p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  dispatch_management_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL dispatch_management_widget.py: {e}")

# === client_drill_down.py ===
p2 = Path("desktop_app/client_drill_down.py")
src2 = p2.read_text(encoding="utf-8")

# Line 836 - avg charter f-string split
src2 = src2.replace(
    '                            f"Avg Charter: ${total_rev / len(charter_rows):,.2f}"',
    '                            f"Avg Charter: $"\n'
    '                            f"{total_rev / len(charter_rows):,.2f}"',
    1,
)

# Line 1181 - where clause wrap
src2 = src2.replace(
    '                    where = "WHERE parent_client_id = 0 OR parent_client_id IS NULL"',
    "                    where = (\n"
    '                        "WHERE parent_client_id = 0"\n'
    '                        " OR parent_client_id IS NULL"\n'
    "                    )",
    1,
)

# Line 1185 - where += long condition
src2 = src2.replace(
    '                        where += " AND (client_name ILIKE %s OR company_name ILIKE %s OR client_id = %s)"',
    "                        where += (\n"
    '                            " AND (client_name ILIKE %s"\n'
    '                            " OR company_name ILIKE %s"\n'
    '                            " OR client_id = %s)"\n'
    "                        )",
    1,
)

p2.write_text(src2, encoding="utf-8")
try:
    ast.parse(src2)
    print("AST_OK  client_drill_down.py")
except SyntaxError as e:
    print(f"AST_FAIL client_drill_down.py: {e}")
