#!/usr/bin/env python
import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
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


def detect_issues(values: dict[str, Decimal]) -> list[dict]:
    """Detect potential issues with GST return"""
    issues = []
    
    # Check GST rate
    if 'Line101_TotalSales' in values and 'Line105_TotalGSTHSTCollected' in values:
        sales = values['Line101_TotalSales']
        gst = values['Line105_TotalGSTHSTCollected']
        if sales > 0:
            rate = (gst / sales * 100)
            if rate < Decimal('4.5'):
                issues.append({
                    'severity': 'high',
                    'field': 'Line105_TotalGSTHSTCollected',
                    'message': f'GST rate is {rate:.2f}% (expected ~5%). Revenue may be GST-inclusive or sales may be partially exempt.',
                    'recommendation': 'Review revenue composition and GST accounting practices.'
                })
            elif rate > Decimal('5.5'):
                issues.append({
                    'severity': 'medium',
                    'field': 'Line105_TotalGSTHSTCollected',
                    'message': f'GST rate is {rate:.2f}% (expected ~5%). GST may be over-collected.',
                    'recommendation': 'Verify GST calculation and account balances.'
                })
    
    # Check ITCs
    if 'Line108_ITCs' in values:
        itcs = values['Line108_ITCs']
        if itcs == 0:
            issues.append({
                'severity': 'high',
                'field': 'Line108_ITCs',
                'message': 'No Input Tax Credits (ITCs) claimed. You may be missing significant tax recovery.',
                'recommendation': 'Verify if GST paid on business expenses is being tracked. Check for GST Paid/Recoverable accounts.'
            })
    
    # Check for unusual patterns
    if 'Line114_NetTaxToRemit' in values:
        net = values['Line114_NetTaxToRemit']
        if net < 0:
            issues.append({
                'severity': 'medium',
                'field': 'Line114_NetTaxToRemit',
                'message': 'Negative net tax indicates a refund is due.',
                'recommendation': 'Verify calculations and ensure all installments are recorded.'
            })
        elif net > Decimal('100000'):
            issues.append({
                'severity': 'low',
                'field': 'Line114_NetTaxToRemit',
                'message': f'Large remittance amount: ${net:,.2f}',
                'recommendation': 'Review for accuracy before submission.'
            })
    
    return issues


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


def render_summary_pdf(output: Path, values: dict[str, Decimal], title: str, period: str):
    """Enhanced PDF with issue flags and summary section"""
    c = canvas.Canvas(str(output), pagesize=LETTER)
    
    # Detect issues
    issues = detect_issues(values)
    
    # Header
    c.setFont('Helvetica-Bold', 16)
    c.drawString(72, 760, title)
    c.setFont('Helvetica', 10)
    c.drawString(72, 745, f"Period: {period}")
    c.drawString(72, 730, f"Generated: {date.today().isoformat()}")
    
    # Line separator
    c.line(72, 720, 540, 720)
    
    # Values section
    c.setFont('Helvetica-Bold', 12)
    c.drawString(72, 700, "Form Fields:")
    c.setFont('Helvetica', 10)
    
    y = 680
    issue_fields = {issue['field'] for issue in issues}
    
    for k, v in values.items():
        # Flag if issue detected
        flag = ''
        if k in issue_fields:
            severity = next((i['severity'] for i in issues if i['field'] == k), 'low')
            if severity == 'high':
                flag = ' ⚠️ REVIEW'
                c.setFillColor(colors.red)
            elif severity == 'medium':
                flag = ' ⚠️'
                c.setFillColor(colors.orange)
            else:
                flag = ' ℹ️'
                c.setFillColor(colors.blue)
        
        c.drawString(72, y, f"{k}{flag}")
        c.drawRightString(540, y, f"${v:,.2f}")
        c.setFillColor(colors.black)
        
        y -= 16
        if y < 150:
            c.showPage()
            c.setFont('Helvetica', 10)
            y = 760
    
    # Issues section
    if issues:
        if y < 250:
            c.showPage()
            y = 760
        
        y -= 20
        c.line(72, y, 540, y)
        y -= 20
        
        c.setFont('Helvetica-Bold', 12)
        c.setFillColor(colors.red)
        c.drawString(72, y, f"⚠️ ISSUES DETECTED ({len(issues)})")
        c.setFillColor(colors.black)
        y -= 20
        
        for i, issue in enumerate(issues, 1):
            if y < 100:
                c.showPage()
                c.setFont('Helvetica', 10)
                y = 760
            
            # Severity badge
            c.setFont('Helvetica-Bold', 10)
            if issue['severity'] == 'high':
                c.setFillColor(colors.red)
                badge = "HIGH"
            elif issue['severity'] == 'medium':
                c.setFillColor(colors.orange)
                badge = "MEDIUM"
            else:
                c.setFillColor(colors.blue)
                badge = "INFO"
            
            c.drawString(72, y, f"{i}. [{badge}]")
            c.setFillColor(colors.black)
            c.setFont('Helvetica', 10)
            
            # Field
            c.drawString(130, y, f"Field: {issue['field']}")
            y -= 14
            
            # Message (wrap if needed)
            msg = issue['message']
            if len(msg) > 80:
                words = msg.split()
                lines = []
                current = []
                for word in words:
                    if len(' '.join(current + [word])) > 80:
                        lines.append(' '.join(current))
                        current = [word]
                    else:
                        current.append(word)
                if current:
                    lines.append(' '.join(current))
                
                for line in lines:
                    c.drawString(90, y, line)
                    y -= 12
            else:
                c.drawString(90, y, msg)
                y -= 12
            
            # Recommendation
            c.setFont('Helvetica-Oblique', 9)
            c.setFillColor(colors.grey)
            rec = issue['recommendation']
            if len(rec) > 85:
                words = rec.split()
                lines = []
                current = []
                for word in words:
                    if len(' '.join(current + [word])) > 85:
                        lines.append(' '.join(current))
                        current = [word]
                    else:
                        current.append(word)
                if current:
                    lines.append(' '.join(current))
                
                for line in lines:
                    c.drawString(90, y, f"→ {line}")
                    y -= 11
            else:
                c.drawString(90, y, f"→ {rec}")
                y -= 11
            
            c.setFillColor(colors.black)
            c.setFont('Helvetica', 10)
            y -= 8
        
        # Footer note
        y -= 10
        if y < 80:
            c.showPage()
            y = 760
        c.setFont('Helvetica-Oblique', 8)
        c.setFillColor(colors.grey)
        c.drawString(72, y, "NOTE: Review flagged items with your accountant before CRA submission.")
        c.setFillColor(colors.black)
    
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
            render_summary_pdf(out, values, title=f"GST/HST Return (GST34)", period=args.period)
        print(f"✅ Wrote {out}")

if __name__ == '__main__':
    main()
