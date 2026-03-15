#!/usr/bin/env python3
"""Categorize GL 6900 receipts into proper GL codes."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("GL 6900 CATEGORIZATION RULES")
print("=" * 100 + "\n")

rules = {
    "JOURNAL ENTRY": ("2100", "Internal journal entries/transfers"),
    "CHEQUE 955.46": ("2100", "Large internal transfer/correction"),
    "CHEQUE WO -120.00": ("2100", "Large internal write-off/correction"),
    "CORRECTION": ("2100", "Accounting corrections"),
    "PAUL RICHARD": ("5000", "Employee wages/draws (payroll)"),
    "PAUL MANSELL": ("5000", "Employee wages/draws (payroll)"),
    "MICHAEL RICHARD": ("5000", "Employee wages/draws (payroll)"),
    "JEANNIE SHILLINGTON": ("5000", "Employee wages/draws (payroll)"),
    "MARK LINTON": ("5000", "Employee wages/draws (payroll)"),
    "JESSE GORDON": ("5000", "Employee wages/draws (payroll)"),
    "KAREN": ("5000", "Employee wages/draws (payroll)"),
    "TAMMY": ("5000", "Employee wages/draws (payroll)"),
    "KEITH DIXON": ("5000", "Employee/contractor payment"),
    "MONEY MART": ("5000", "Cash withdrawal for payroll/expenses"),
    "WITHDRAWAL": ("5000", "Cash withdrawal"),
    "DRAFT": ("5000", "Draft payment (likely payroll)"),
    "UNKNOWN POINT OF SALE": ("5000", "Point of sale payment (unknown category)"),
    "[UNKNOWN": ("5000", "Unknown payment type"),
    "DEBIT VIA": ("5000", "Debit payment"),
    "ETRANSFER": ("5000", "E-transfer payment"),
    "EMAIL TRANSFER": ("5000", "Email transfer (employee/contractor)"),
    "RECEIVER GENERAL": ("8000", "Tax/CRA payments"),
    "ATTACHMENT": ("5000", "Attachment order/garnishment"),
    "BILL PAYMENT": ("5000", "Generic payment (to be reviewed)"),
    "BANK DRAFT": ("5000", "Bank draft payment"),
    "BUSINESS EXPENSE": ("6800", "General business expense"),
    "DRAFT PURCHASE": ("5200", "Purchase via draft"),
    "ACCOUNTANT": ("6100", "Accounting/professional fees"),
}

print("Proposed GL Mapping:")
print("-" * 100 + "\n")

# Group by proposed GL code
by_gl = {}
for vendor_pattern, (new_gl, description) in rules.items():
    if new_gl not in by_gl:
        by_gl[new_gl] = []
    by_gl[new_gl].append((vendor_pattern, description))

for gl_code in sorted(by_gl.keys()):
    print(f"\n{gl_code} - {by_gl[gl_code][0][1]}:")
    for vendor_pattern, description in by_gl[gl_code]:
        print(f"  • {vendor_pattern:30} | {description}")

# Estimate impact
print("\n" + "=" * 100)
print("CATEGORIZATION IMPACT")
print("=" * 100 + "\n")

for gl_code in sorted(set(v[0] for v in rules.values())):
    patterns = [k for k, (g, _) in rules.items() if g == gl_code]
    
    # Count receipts matching these patterns
    query = " OR ".join([f"vendor_name LIKE '%{p}%'" for p in patterns])
    cur.execute(f"""
        SELECT COUNT(*), SUM(COALESCE(gross_amount, 0))
        FROM receipts
        WHERE gl_account_code = '6900'
        AND ({query})
    """)
    
    count, total = cur.fetchone()
    print(f"GL {gl_code}: {count:4d} receipts | ${float(total):12,.2f}")

print("\nNote: Some categories may overlap. Review before applying.")

cur.close()
conn.close()

print("\n✅ Analysis complete")
