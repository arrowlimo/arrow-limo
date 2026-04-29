"""Patch batch8: dashboard_classes, split_receipt_details, pdf.py, pdf_charter_export."""
import ast
from pathlib import Path


def ok(path, src):
    try:
        ast.parse(src)
        print(f"AST_OK  {Path(path).name}")
    except SyntaxError as e:
        print(f"AST_FAIL {Path(path).name}: {e}")


# ── dashboard_classes.py ───────────────────────────────────────────────────
p = Path("desktop_app/dashboard_classes.py")
src = p.read_text(encoding="utf-8")

src = src.replace(
    "                        WHEN v.decommission_date IS NOT NULL THEN '⚠️ Decommissioned'\n"
    "                        WHEN v.operational_status = 'maintenance' THEN '🔧 In Maintenance'\n"
    "                        WHEN v.operational_status IN ('inactive', 'retired', 'out_of_service') THEN '🚫 Inactive'",
    "                        WHEN v.decommission_date IS NOT NULL\n"
    "                            THEN '⚠️ Decommissioned'\n"
    "                        WHEN v.operational_status = 'maintenance'\n"
    "                            THEN '🔧 In Maintenance'\n"
    "                        WHEN v.operational_status IN\n"
    "                            ('inactive', 'retired', 'out_of_service')\n"
    "                            THEN '🚫 Inactive'",
    1,
)
src = src.replace(
    "                    COALESCE(SUM(CASE WHEN r.description ILIKE '%fuel%' THEN r.gross_amount ELSE 0 END),0) fuel_cost,\n"
    "                    COALESCE(SUM(CASE WHEN r.description ILIKE '%maint%' OR r.description ILIKE '%repair%' THEN r.gross_amount ELSE 0 END),0) maint_cost",
    "                    COALESCE(SUM(CASE\n"
    "                        WHEN r.description ILIKE '%fuel%'\n"
    "                        THEN r.gross_amount ELSE 0 END),0) fuel_cost,\n"
    "                    COALESCE(SUM(CASE\n"
    "                        WHEN r.description ILIKE '%maint%'\n"
    "                          OR r.description ILIKE '%repair%'\n"
    "                        THEN r.gross_amount ELSE 0 END),0) maint_cost",
    1,
)
src = src.replace(
    "                           CASE WHEN c.balance > 0 THEN 'Outstanding' ELSE 'Paid' END AS status",
    "                           CASE WHEN c.balance > 0\n"
    "                               THEN 'Outstanding'\n"
    "                               ELSE 'Paid'\n"
    "                           END AS status",
    1,
)
p.write_text(src, encoding="utf-8")
ok(p, src)

# ── split_receipt_details_widget.py ───────────────────────────────────────
p2 = Path("desktop_app/split_receipt_details_widget.py")
src2 = p2.read_text(encoding="utf-8")

src2 = src2.replace(
    "                    SELECT split_group_id, receipt_date, vendor_name, gross_amount, COALESCE(description,'')\n"
    "                    FROM receipts WHERE receipt_id = %s",
    "                    SELECT split_group_id, receipt_date,\n"
    "                           vendor_name, gross_amount,\n"
    "                           COALESCE(description,'')\n"
    "                    FROM receipts WHERE receipt_id = %s",
    1,
)
src2 = src2.replace(
    "        Heuristic: find receipts on the same day (±1), same vendor, with 'split' in description.",
    "        Heuristic: find receipts on the same day (±1), same vendor,\n"
    "        with 'split' in description.",
    1,
)
src2 = src2.replace(
    "                SELECT receipt_id, receipt_date, vendor_name, gross_amount, COALESCE(description,'')\n"
    "                FROM receipts",
    "                SELECT receipt_id, receipt_date,\n"
    "                       vendor_name, gross_amount,\n"
    "                       COALESCE(description,'')\n"
    "                FROM receipts",
    1,
)
p2.write_text(src2, encoding="utf-8")
ok(p2, src2)

# ── modern_backend/app/routers/pdf.py ─────────────────────────────────────
p3 = Path("modern_backend/app/routers/pdf.py")
src3 = p3.read_text(encoding="utf-8")

src3 = src3.replace(
    "                    WHEN c.closed = true AND c.cancelled = false THEN 'Reconciled'",
    "                    WHEN c.closed = true AND c.cancelled = false\n"
    "                        THEN 'Reconciled'",
    1,
)
src3 = src3.replace(
    "                WHERE payment_label IN ('NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')",
    "                WHERE payment_label IN (\n"
    "                    'NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer'\n"
    "                )",
    1,
)
src3 = src3.replace(
    "                COALESCE(address, pickup_location, dropoff_location, '') AS address,",
    "                COALESCE(\n"
    "                    address, pickup_location, dropoff_location, ''\n"
    "                ) AS address,",
    1,
)
p3.write_text(src3, encoding="utf-8")
ok(p3, src3)

# ── pdf_charter_export_module.py ──────────────────────────────────────────
p4 = Path("desktop_app/pdf_charter_export_module.py")
src4 = p4.read_text(encoding="utf-8")

src4 = src4.replace(
    "                    f\"{client.get('address_line1', '')}, {client.get('city', '')}\",",
    "                    (\n"
    "                        client.get('address_line1', '') + ', '\n"
    "                        + client.get('city', '')\n"
    "                    ),",
    1,
)
p4.write_text(src4, encoding="utf-8")
ok(p4, src4)
