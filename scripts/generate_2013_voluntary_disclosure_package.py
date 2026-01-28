#!/usr/bin/env python3
"""Generate skeleton for CRA Voluntary Disclosures Program (VDP) package for 2013.
Outputs folder reports/VDP_2013/ with:
 - cover_letter.md
 - checklist.md
 - schedules/gst34_support.csv (placeholders)
 - schedules/t2_support.csv (placeholders)
 - schedules/payroll_pd7a_support.csv (placeholders)
"""
import os, csv

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'reports', 'VDP_2013'))

COVER = """# Voluntary Disclosure – 2013 (GST & T2)

To: CRA Voluntary Disclosures Program

Subject: Late filing and payment for GST/HST return (2013) and T2 Corporate Income Tax Return (2013)

We are submitting this disclosure to correct past non-compliance for tax year 2013. We request consideration under the VDP for penalty relief and interest reduction where applicable.

Summary:
- GST/HST Collected: $61,872.95
- Input Tax Credits (ITCs): $12,888.23
- Net GST Owing: $48,984.72
- Corporate Result (T2): Net business loss $6,665.22

Enclosures:
- Schedule A: GST/HST return reconstruction and support
- Schedule B: T2 support (Income Statement & Balance Sheet extracts)
- Schedule C: Payroll PD7A reconciliation (withholdings vs remittances)
- Evidence: Banking extracts showing no prior remittance; GL and receipts exports

We intend to remit the GST principal plus accrued interest immediately upon CRA computation and accept a payment arrangement for the remaining balance if required.

Sincerely,
Arrow Limousine Management
"""

CHECKLIST = """# VDP 2013 Checklist
- [ ] Complete disclosure is voluntary and prior to enforcement action
- [ ] Penalty applicable (late filing/payment)
- [ ] Information at least one year past due (yes – 2013)
- [ ] Payment arrangement addressed (ability to pay statement prepared)
- [ ] Supporting documents attached (GL, receipts, banking, payroll)
"""

def ensure_dirs():
    os.makedirs(BASE, exist_ok=True)
    os.makedirs(os.path.join(BASE, 'schedules'), exist_ok=True)


def write_text(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def write_csv(path, headers, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)


def main():
    ensure_dirs()
    write_text(os.path.join(BASE, 'cover_letter.md'), COVER)
    write_text(os.path.join(BASE, 'checklist.md'), CHECKLIST)
    write_csv(os.path.join(BASE, 'schedules', 'gst34_support.csv'),
              ['component','amount','source','notes'],
              [
                ['GST Collected','61872.95','2013_TAX_FINALIZATION_CHECKLIST.md','To be validated vs ledger'],
                ['ITCs','12888.23','2013_TAX_FINALIZATION_CHECKLIST.md','To be validated vs receipts'],
                ['Net Tax','48984.72','Computed','61872.95-12888.23']
              ])
    write_csv(os.path.join(BASE, 'schedules', 't2_support.csv'),
              ['line','amount','source','notes'],
              [
                ['Revenue','2806269.72','2013_TAX_FINALIZATION_CHECKLIST.md','Validate vs GL export'],
                ['Expenses','2812934.94','2013_TAX_FINALIZATION_CHECKLIST.md','Validate vs GL export'],
                ['Net Income (Loss)','-6665.22','Computed','Revenue-Expenses']
              ])
    write_csv(os.path.join(BASE, 'schedules', 'payroll_pd7a_support.csv'),
              ['component','amount','source','notes'],
              [
                ['CPP Withheld','TBD','driver_payroll','Sum 2013 CPP'],
                ['EI Withheld','TBD','driver_payroll','Sum 2013 EI'],
                ['Income Tax Withheld','TBD','driver_payroll','Sum 2013 Tax'],
                ['Remitted to CRA','TBD','banking_transactions','Filter CRA payees 2013-2014']
              ])
    print(f"VDP skeleton created at {BASE}")

if __name__ == '__main__':
    main()
