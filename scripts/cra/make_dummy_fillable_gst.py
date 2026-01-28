#!/usr/bin/env python
"""
Create a simple, obviously-not-official, fillable-like PDF with a few GST fields
for local testing when CRA templates aren't fillable.
"""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

FIELDS = [
    'Line101_TotalSales',
    'Line105_TotalGSTHSTCollected',
    'Line108_ITCs',
    'Line109_NetTax',
    'Line112_NetTaxAdjustments',
    'Line113A_Installments',
    'Line113B_Other',
    'Line114_NetTaxToRemit',
    'Line115_AmountOwingOrRefund',
]

def main():
    out = Path(__file__).with_name('GST34_dummy_fillable.pdf')
    c = canvas.Canvas(str(out), pagesize=LETTER)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(72, 760, 'GST34 Dummy (test only)')
    c.setFont('Helvetica', 10)
    y = 730
    for f in FIELDS:
        c.drawString(72, y, f)
        c.rect(300, y-4, 200, 14)
        y -= 18
    c.showPage()
    c.save()
    print(f'Wrote {out}')

if __name__ == '__main__':
    main()
