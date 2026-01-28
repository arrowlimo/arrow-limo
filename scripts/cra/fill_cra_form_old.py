#!/usr/bin/env python
import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

# Support running as a script or module
try:
    from .db import get_connection
    from .periods import parse_period
except Exception:
    sys.path.append(str(Path(__file__).resolve().parent))
    from db import get_connection  # type: ignore
    from periods import parse_period  # type: ignore

try:
    from pypdf import PdfReader, PdfWriter
except Exception:  # optional dependency
    PdfReader = None
    PdfWriter = None


def run_sql(sql: str, params: dict[str, str]) -> Decimal:
    sql_filled = sql.format(**params)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_filled)
            row = cur.fetchone()
            if not row:
                return Decimal('0')
            v = row[0]
            if v is None:
                return Decimal('0')
            return Decimal(str(v))


def compute_fields(mapping: dict, period_label: str) -> dict[str, Decimal]:
    p = parse_period(period_label)
    params = {
        'period_start': p.start.isoformat(),
        'period_end': p.end.isoformat(),
        'year': str(p.start.year),
        'quarter': p.label[-2:] if 'Q' in p.label else ''
    }
    values: dict[str, Decimal] = {}

    # 1) Evaluate SQL-backed fields
    for field, spec in mapping['fields'].items():
        if 'sql' in spec:
            values[field] = run_sql(spec['sql'], params)
        else:
            values[field] = Decimal(str(spec.get('default', 0)))

    # 2) Evaluate formulas (simple references and +,- arithmetic)
    for field, spec in mapping['fields'].items():
        if 'formula' in spec:
            expr = spec['formula']
            safe = expr
            for k, v in values.items():
                safe = safe.replace(k, f"Decimal('{v}')")
            values[field] = eval(safe, {'Decimal': Decimal})

    return values


def fill_pdf(template: Path, output: Path, values: dict[str, Decimal]):
    if not PdfReader or not PdfWriter:
        raise RuntimeError('pypdf not available; install pypdf or use --no-template mode')
    reader = PdfReader(str(template))
    writer = PdfWriter()
    writer.append(reader)

    # Try to write as form fields if AcroForm present
    try:
        fields = writer.get_fields() or {}
        for name in fields.keys():
            if name in values:
                writer.update_page_form_field_values(writer.pages[0], {name: f"{values[name]:.2f}"})
    except Exception:
        # Fallback: overlay text on first page
        packet = output.with_suffix('.tmp.pdf')
        c = canvas.Canvas(str(packet), pagesize=LETTER)
        y = 720
        for k, v in values.items():
            c.drawString(72, y, f"{k}: {v:.2f}")
            y -= 14
        c.save()
        # Merge overlay
        from pypdf import PageObject
        overlay = PdfReader(str(packet)).pages[0]
        base = writer.pages[0]
        base.merge_page(overlay)

    with open(output, 'wb') as f:
        writer.write(f)


def render_summary_pdf(output: Path, values: dict[str, Decimal], title: str):
    c = canvas.Canvas(str(output), pagesize=LETTER)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(72, 760, title)
    c.setFont('Helvetica', 10)
    y = 730
    for k, v in values.items():
        c.drawString(72, y, f"{k}")
        c.drawRightString(540, y, f"{v:.2f}")
        y -= 14
        if y < 72:
            c.showPage()
            c.setFont('Helvetica', 10)
            y = 760
    c.showPage()
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--form', choices=['gst'], required=True)
    ap.add_argument('--period', required=True, help='e.g., 2025Q3, 2025, or 2025-07..2025-09')
    ap.add_argument('--template', help='Path to fillable PDF template (optional)')
    ap.add_argument('--output', required=True, help='Output PDF path')
    args = ap.parse_args()

    if args.form == 'gst':
        mapping = json.loads(Path(__file__).with_name('mapping_gst.json').read_text())
        values = compute_fields(mapping, args.period)
        out = Path(args.output)
        if args.template:
            fill_pdf(Path(args.template), out, values)
        else:
            render_summary_pdf(out, values, title=f"GST/HST Return {args.period}")
        print(f"✅ Wrote {out}")

if __name__ == '__main__':
    main()
