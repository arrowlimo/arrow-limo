import os, psycopg2, json, math
from decimal import Decimal

# Connection
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

cur.execute("""
SELECT id, driver_id, employee_id, charter_id, reserve_number, pay_date, gross_pay, net_pay, record_notes, source
FROM driver_payroll
WHERE driver_id = 'ADJ'
ORDER BY pay_date
""")
rows = cur.fetchall()

records = []
for r in rows:
    rec = {
        'id': r[0],
        'driver_id': r[1],
        'employee_id': r[2],
        'charter_id': r[3],
        'reserve_number': r[4],
        'pay_date': str(r[5]),
        'gross_pay': float(r[6] or 0),
        'net_pay': float(r[7] or 0),
        'notes': r[8],
        'source': r[9]
    }
    records.append(rec)

count = len(records)
total_gross = sum(r['gross_pay'] for r in records)

# Simple classification heuristics
for rec in records:
    txt = (rec['notes'] or '') + ' ' + (rec['source'] or '')
    lower = txt.lower()
    reasons = []
    if 'adjust' in lower or 'adj' in lower:
        reasons.append('keyword:adjust')
    if 'import' in lower:
        reasons.append('import artifact')
    if rec['charter_id'] is None and rec['reserve_number'] is None:
        reasons.append('no charter linkage')
    if rec['employee_id'] is None:
        reasons.append('no employee linkage')
    rec['classification_hints'] = reasons

summary = {
    'count': count,
    'total_gross_pay': total_gross,
    'average_gross': (total_gross / count) if count else 0,
    'records': records
}

print(f"ADJ adjustment entries: {count}")
print(f"Total gross: ${total_gross:,.2f}")
print(f"Average gross: ${summary['average_gross']:,.2f}")
print()
print("Details:")
for rec in records:
    print(f"  ID {rec['id']} | Date {rec['pay_date']} | Gross ${rec['gross_pay']:,.2f} | Net ${rec['net_pay']:,.2f} | Charter {rec['charter_id']} | Reserve {rec['reserve_number']} | Emp {rec['employee_id']} | Hints: {', '.join(rec['classification_hints']) if rec['classification_hints'] else 'none'}")
    if rec['notes']:
        print(f"    Notes: {rec['notes'][:180]}")
    if rec['source']:
        print(f"    Source: {rec['source'][:140]}")

# Proposed segregation DDL (printed, not executed)
print("\nProposed adjustments table (DDL preview):")
print("""CREATE TABLE IF NOT EXISTS payroll_adjustments (
    adjustment_id SERIAL PRIMARY KEY,
    driver_payroll_id INTEGER REFERENCES driver_payroll(id) ON DELETE CASCADE,
    adjustment_type VARCHAR(50) NOT NULL, -- e.g., LEGACY_CORRECTION, BULK_IMPORT, REVERSAL
    gross_amount NUMERIC(12,2) NOT NULL,
    net_amount NUMERIC(12,2),
    rationale TEXT, -- descriptive explanation
    source_reference TEXT, -- original source / batch id
    has_charter_link BOOLEAN DEFAULT FALSE,
    has_employee_link BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);""")

print("\nNext actions suggestions:")
print(" 1. Verify each ADJ note/source for original provenance (journal, QuickBooks export, manual correction).")
print(" 2. Populate payroll_adjustments with classification before removing from driver_payroll analytical totals.")
print(" 3. Recompute payroll KPIs excluding adjustments to reflect pure wage amounts.")
print(" 4. Attach audit rationale per adjustment (who authorized, date, source file).")

cur.close(); conn.close()
