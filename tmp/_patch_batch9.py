"""Patch residual E501 lines in top-5 files (batch 9)."""
import ast
from pathlib import Path


def write_and_check(path: str, src: str) -> None:
    p = Path(path)
    p.write_text(src, encoding="utf-8")
    try:
        ast.parse(src)
        print(f"AST_OK  {p.name}")
    except SyntaxError as e:
        print(f"AST_FAIL {p.name}: {e}")


# 1) desktop_app/smoke_test_all_widgets.py
p1 = "desktop_app/smoke_test_all_widgets.py"
s1 = Path(p1).read_text(encoding="utf-8")
s1 = s1.replace(
    '            "import": "from report_explorer_widget import ReportExplorerWidget",',
    '            "import": (\n'
    '                "from report_explorer_widget "\n'
    '                "import ReportExplorerWidget"\n'
    '            ),',
    1,
)
write_and_check(p1, s1)


# 2) desktop_app/pdf_form_generator_widget.py
p2 = "desktop_app/pdf_form_generator_widget.py"
s2 = Path(p2).read_text(encoding="utf-8")
s2 = s2.replace(
    '                f"Invoice_{reserve_number}_{datetime.now().strftime(\'%Y%m%d\')}.pdf",',
    '                (\n'
    '                    f"Invoice_{reserve_number}_"\n'
    '                    f"{datetime.now().strftime(\'%Y%m%d\')}.pdf"\n'
    '                ),',
    1,
)
write_and_check(p2, s2)


# 3) desktop_app/quotes_engine.py
p3 = "desktop_app/quotes_engine.py"
s3 = Path(p3).read_text(encoding="utf-8")

s3 = s3.replace(
    '                    {"hours": 3, "rate": 300.00, "description": "Pickup to Supper"},',
    '                    {\n'
    '                        "hours": 3,\n'
    '                        "rate": 300.00,\n'
    '                        "description": "Pickup to Supper",\n'
    '                    },',
    1,
)
s3 = s3.replace(
    '                    {"hours": 0, "rate": 0, "description": "Supper Stop (time stops)"},',
    '                    {\n'
    '                        "hours": 0,\n'
    '                        "rate": 0,\n'
    '                        "description": "Supper Stop (time stops)",\n'
    '                    },',
    1,
)
s3 = s3.replace(
    '                    {"hours": 3, "rate": 300.00, "description": "Supper to Return"},',
    '                    {\n'
    '                        "hours": 3,\n'
    '                        "rate": 300.00,\n'
    '                        "description": "Supper to Return",\n'
    '                    },',
    1,
)
s3 = s3.replace(
    '                    {"hours": 1.5, "rate": 250.00, "description": "Extra Time"},]',
    '                    {\n'
    '                        "hours": 1.5,\n'
    '                        "rate": 250.00,\n'
    '                        "description": "Extra Time",\n'
    '                    },\n'
    '                ]',
    1,
)
s3 = s3.replace(
    '                    "custom_charges": [{"description": "Late arrival discount", "amount": -50.00}]}',
    '                    "custom_charges": [\n'
    '                        {\n'
    '                            "description": "Late arrival discount",\n'
    '                            "amount": -50.00,\n'
    '                        }\n'
    '                    ],\n'
    '                }',
    1,
)
s3 = s3.replace(
    '            header_text = f"Quote Results - {selected_vehicle} - Booking Types: {booking_types_str}"',
    '            header_text = (\n'
    '                f"Quote Results - {selected_vehicle} - "\n'
    '                f"Booking Types: {booking_types_str}"\n'
    '            )',
    1,
)
s3 = s3.replace(
    "                f\"Quote_{self.client_name.text().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt\",",
    "                (\n"
    "                    f\"Quote_{self.client_name.text().replace(' ', '_')}_\"\n"
    "                    f\"{datetime.now().strftime('%Y%m%d')}.txt\"\n"
    "                ),",
    1,
)
write_and_check(p3, s3)


# 4) modern_backend/app/routers/receipts_linked_display.py
p4 = "modern_backend/app/routers/receipts_linked_display.py"
s4 = Path(p4).read_text(encoding="utf-8")
s4 = s4.replace(
    "                    OR (COALESCE(r.split_key, '') <> '' AND EXISTS (SELECT 1 FROM receipts r2 WHERE r2.split_key = r.split_key))",
    "                    OR (\n"
    "                        COALESCE(r.split_key, '') <> ''\n"
    "                        AND EXISTS (\n"
    "                            SELECT 1 FROM receipts r2\n"
    "                            WHERE r2.split_key = r.split_key\n"
    "                        )\n"
    "                    )",
    1,
)
write_and_check(p4, s4)


# 5) modern_backend/app/routes/cheque_books.py
p5 = "modern_backend/app/routes/cheque_books.py"
s5 = Path(p5).read_text(encoding="utf-8")

s5 = s5.replace(
    "                COUNT(CASE WHEN category IS NOT NULL AND category != '' THEN 1 END) as categorized,",
    "                COUNT(CASE\n"
    "                    WHEN category IS NOT NULL AND category != ''\n"
    "                    THEN 1 END) as categorized,",
    1,
)
s5 = s5.replace(
    "                COUNT(CASE WHEN category IS NULL OR category = '' THEN 1 END) as uncategorized,",
    "                COUNT(CASE\n"
    "                    WHEN category IS NULL OR category = ''\n"
    "                    THEN 1 END) as uncategorized,",
    1,
)
s5 = s5.replace(
    "                MIN(CAST(REGEXP_REPLACE(vendor_extracted, '[^0-9]', '', 'g') AS INTEGER)) as min_cheque,",
    "                MIN(CAST(REGEXP_REPLACE(\n"
    "                    vendor_extracted, '[^0-9]', '', 'g'\n"
    "                ) AS INTEGER)) as min_cheque,",
    1,
)
s5 = s5.replace(
    "                MAX(CAST(REGEXP_REPLACE(vendor_extracted, '[^0-9]', '', 'g') AS INTEGER)) as max_cheque,",
    "                MAX(CAST(REGEXP_REPLACE(\n"
    "                    vendor_extracted, '[^0-9]', '', 'g'\n"
    "                ) AS INTEGER)) as max_cheque,",
    1,
)
s5 = s5.replace(
    "                COUNT(CASE WHEN check_recipient IS NULL OR check_recipient = 'Unknown' THEN 1 END) as unknown_payees",
    "                COUNT(CASE\n"
    "                    WHEN check_recipient IS NULL\n"
    "                      OR check_recipient = 'Unknown'\n"
    "                    THEN 1 END) as unknown_payees",
    1,
)
s5 = s5.replace(
    "                    WHEN category ILIKE '%nsf%' OR description ILIKE '%nsf%' THEN 'NSF'",
    "                    WHEN category ILIKE '%nsf%'\n"
    "                      OR description ILIKE '%nsf%' THEN 'NSF'",
    1,
)
s5 = s5.replace(
    "                    WHEN category ILIKE '%void%' OR description ILIKE '%void%' THEN 'VOID'",
    "                    WHEN category ILIKE '%void%'\n"
    "                      OR description ILIKE '%void%' THEN 'VOID'",
    1,
)
s5 = s5.replace(
    "                CAST(REGEXP_REPLACE(vendor_extracted, '[^0-9]', '', 'g') AS INTEGER),",
    "                CAST(REGEXP_REPLACE(\n"
    "                    vendor_extracted, '[^0-9]', '', 'g'\n"
    "                ) AS INTEGER),",
    1,
)
s5 = s5.replace(
    '                "cleared": "Expense - Other",  # Default, should be updated with actual GL',
    '                "cleared": "Expense - Other",  # Default GL; update if known',
    1,
)
write_and_check(p5, s5)
