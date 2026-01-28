#!/usr/bin/env python3
"""
Audit charter runs vs driver payroll assignments for 2021-2024 to detect LMS corruption
(where drivers were mixed up with charters). Also audit Paul's pay handling (post-2013
policy: not paid, banked).

Outputs CSVs under exports/driver_audit/:
- mismatches_2021_2024.csv: Charter vs payroll driver mismatches
- missing_payroll_2021_2024.csv: Charters with no payroll entries
- payroll_mismatched_charters_2021_2024.csv: Payroll entries referencing a charter whose assigned driver differs
- pauls_pay_audit_2014_2025.csv: Paul's payroll entries post-2013 with payment lookup hints

Joins/assumptions:
- charters.assigned_driver_id -> employees.employee_id for assigned driver
- driver_payroll.driver_id -> employees.employee_number to recover driver identity (employee_id may be NULL)
- Link driver_payroll to charters via (charter_id) or (reserve_number)
- Date filter on charters.charter_date between 2021-01-01 and 2024-12-31
"""

import psycopg2
import csv
from pathlib import Path
from collections import defaultdict

DB = dict(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')

EXPORT_DIR = Path(__file__).parent.parent / 'exports' / 'driver_audit'
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def connect():
    return psycopg2.connect(**DB)


def fetchall(cur, query, params=None):
    if params is None:
        cur.execute(query)
    else:
        cur.execute(query, params)
    return cur.fetchall()


def load_employees(cur):
    # Build lookups by employee_id and employee_number
    rows = fetchall(cur, """
        SELECT employee_id, employee_number, COALESCE(full_name, first_name || ' ' || last_name) AS full_name
        FROM employees
    """)
    by_id = {r[0]: {'employee_number': r[1], 'full_name': r[2]} for r in rows}
    by_number = {r[1]: {'employee_id': r[0], 'full_name': r[2]} for r in rows if r[1] is not None}
    return by_id, by_number


def load_charters_2021_2024(cur):
    # Pull essential fields, resolve assigned driver name via employees
    rows = fetchall(cur, """
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.assigned_driver_id,
               COALESCE(e.full_name, c.driver_name) AS assigned_driver_name
        FROM charters c
        LEFT JOIN employees e ON e.employee_id = c.assigned_driver_id
        WHERE c.charter_date BETWEEN DATE '2021-01-01' AND DATE '2024-12-31'
          AND COALESCE(c.cancelled, false) = false
    """)
    charters = {}
    for charter_id, reserve_number, charter_date, assigned_driver_id, assigned_driver_name in rows:
        charters[charter_id] = {
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'charter_date': charter_date,
            'assigned_driver_id': assigned_driver_id,
            'assigned_driver_name': assigned_driver_name or ''
        }
    return charters


def load_driver_payroll_map(cur):
    # Map payroll by charter_id and by reserve_number; enrich with employee via employee_number
    rows = fetchall(cur, """
        SELECT id, driver_id, employee_id, charter_id, reserve_number, pay_date, gross_pay
        FROM driver_payroll
        WHERE (charter_id IS NOT NULL OR reserve_number IS NOT NULL)
    """)
    payroll_by_charter = defaultdict(list)
    payroll_by_reserve = defaultdict(list)
    for id_, driver_id, employee_id, charter_id, reserve_number, pay_date, gross_pay in rows:
        payroll_by_charter[charter_id].append({
            'id': id_, 'driver_id': driver_id, 'employee_id': employee_id,
            'charter_id': charter_id, 'reserve_number': reserve_number,
            'pay_date': pay_date, 'gross_pay': gross_pay
        })
        if reserve_number:
            payroll_by_reserve[str(reserve_number).strip()].append({
                'id': id_, 'driver_id': driver_id, 'employee_id': employee_id,
                'charter_id': charter_id, 'reserve_number': reserve_number,
                'pay_date': pay_date, 'gross_pay': gross_pay
            })
    return payroll_by_charter, payroll_by_reserve


def enrich_payroll_with_emp(payroll_entries, employees_by_number, employees_by_id):
    for entry in payroll_entries:
        emp = None
        if entry.get('employee_id'):
            emp = employees_by_id.get(entry['employee_id'])
        if not emp and entry.get('driver_id'):
            emp = employees_by_number.get(entry['driver_id'])
        entry['payroll_employee_id'] = emp.get('employee_id') if emp else None
        entry['payroll_employee_name'] = emp.get('full_name') if emp else None
    return payroll_entries


def write_csv(path, rows, headers):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def audit_mismatches():
    conn = connect()
    cur = conn.cursor()

    employees_by_id, employees_by_number = load_employees(cur)
    # Note: load_employees returned by_id, by_number; adapt:
    employees_by_id, employees_by_number = employees_by_id, employees_by_number

    charters = load_charters_2021_2024(cur)
    payroll_by_charter, payroll_by_reserve = load_driver_payroll_map(cur)

    mismatches = []
    missing_payroll = []
    payroll_mismatched_charters = []

    for charter_id, c in charters.items():
        # Find payroll by charter_id or reserve_number
        p_entries = list(payroll_by_charter.get(charter_id, []))
        if not p_entries and c['reserve_number'] is not None:
            p_entries = list(payroll_by_reserve.get(str(c['reserve_number']).strip(), []))

        if not p_entries:
            missing_payroll.append({
                'charter_id': c['charter_id'],
                'reserve_number': c['reserve_number'],
                'charter_date': c['charter_date'],
                'assigned_driver_id': c['assigned_driver_id'],
                'assigned_driver_name': c['assigned_driver_name'],
                'issue': 'NO_PAYROLL'
            })
            continue

        # Enrich entries with employee name
        p_entries = enrich_payroll_with_emp(p_entries, employees_by_number, employees_by_id)

        # Compare names/IDs
        for pe in p_entries:
            pay_name = pe.get('payroll_employee_name') or ''
            pay_emp_id = pe.get('payroll_employee_id')
            if (pay_emp_id is not None and c['assigned_driver_id'] is not None and pay_emp_id != c['assigned_driver_id']) \
               or (pay_emp_id is None and pay_name and c['assigned_driver_name'] and pay_name.strip().lower() != c['assigned_driver_name'].strip().lower()):
                mismatches.append({
                    'charter_id': c['charter_id'],
                    'reserve_number': c['reserve_number'],
                    'charter_date': c['charter_date'],
                    'assigned_driver_id': c['assigned_driver_id'],
                    'assigned_driver_name': c['assigned_driver_name'],
                    'payroll_entry_id': pe['id'],
                    'payroll_driver_id': pe['driver_id'],
                    'payroll_employee_id': pay_emp_id,
                    'payroll_employee_name': pay_name,
                    'pay_date': pe['pay_date'],
                    'gross_pay': pe['gross_pay'],
                    'issue': 'DRIVER_MISMATCH'
                })

    # Also find payroll entries that reference a charter with different assigned driver
    # We will scan payroll_by_charter keys within 2021-2024 charters
    for charter_id, entries in payroll_by_charter.items():
        if charter_id in charters:
            c = charters[charter_id]
            entries = enrich_payroll_with_emp(entries, employees_by_number, employees_by_id)
            for pe in entries:
                pay_name = pe.get('payroll_employee_name') or ''
                pay_emp_id = pe.get('payroll_employee_id')
                if (pay_emp_id is not None and c['assigned_driver_id'] is not None and pay_emp_id != c['assigned_driver_id']) \
                   or (pay_emp_id is None and pay_name and c['assigned_driver_name'] and pay_name.strip().lower() != c['assigned_driver_name'].strip().lower()):
                    payroll_mismatched_charters.append({
                        'charter_id': c['charter_id'],
                        'reserve_number': c['reserve_number'],
                        'charter_date': c['charter_date'],
                        'assigned_driver_id': c['assigned_driver_id'],
                        'assigned_driver_name': c['assigned_driver_name'],
                        'payroll_entry_id': pe['id'],
                        'payroll_driver_id': pe['driver_id'],
                        'payroll_employee_id': pay_emp_id,
                        'payroll_employee_name': pay_name,
                        'pay_date': pe['pay_date'],
                        'gross_pay': pe['gross_pay'],
                        'issue': 'PAYROLL_REFERS_DIFFERENT_DRIVER'
                    })

    # Write CSVs
    write_csv(EXPORT_DIR / 'missing_payroll_2021_2024.csv', missing_payroll,
              ['charter_id','reserve_number','charter_date','assigned_driver_id','assigned_driver_name','issue'])
    write_csv(EXPORT_DIR / 'mismatches_2021_2024.csv', mismatches,
              ['charter_id','reserve_number','charter_date','assigned_driver_id','assigned_driver_name','payroll_entry_id','payroll_driver_id','payroll_employee_id','payroll_employee_name','pay_date','gross_pay','issue'])
    write_csv(EXPORT_DIR / 'payroll_mismatched_charters_2021_2024.csv', payroll_mismatched_charters,
              ['charter_id','reserve_number','charter_date','assigned_driver_id','assigned_driver_name','payroll_entry_id','payroll_driver_id','payroll_employee_id','payroll_employee_name','pay_date','gross_pay','issue'])

    print(f"Charters analyzed: {len(charters):,}")
    print(f"Missing payroll entries: {len(missing_payroll):,}")
    print(f"Driver mismatches: {len(mismatches):,}")
    print(f"Payroll entries referencing mismatched charters: {len(payroll_mismatched_charters):,}")

    cur.close(); conn.close()


def audit_pauls_pay():
    """Audit Paul's pay entries after 2013 (policy: not paid, banked)."""
    conn = connect(); cur = conn.cursor()

    # Find employees likely named Paul
    paul_rows = fetchall(cur, """
        SELECT employee_id, employee_number, COALESCE(full_name, first_name || ' ' || last_name) AS name
        FROM employees
        WHERE LOWER(COALESCE(full_name, first_name || ' ' || last_name)) LIKE '%paul%'
    """)
    pauls = [{'employee_id': r[0], 'employee_number': r[1], 'name': r[2]} for r in paul_rows]

    results = []
    total_count = 0
    total_amount = 0.0

    for p in pauls:
        # Driver payroll rows 2014+
        rows = fetchall(cur, """
            SELECT id, pay_date, driver_id, employee_id, charter_id, reserve_number, gross_pay
            FROM driver_payroll
            WHERE (employee_id = %s OR driver_id = %s)
              AND pay_date >= DATE '2014-01-01'
            ORDER BY pay_date
        """, (p['employee_id'], p['employee_number']))

        for r in rows:
            rid, pay_date, driver_id, employee_id, charter_id, reserve_number, gross_pay = r
            total_count += 1
            total_amount += float(gross_pay or 0)
            results.append({
                'paul_employee_id': p['employee_id'],
                'paul_employee_number': p['employee_number'],
                'paul_name': p['name'],
                'payroll_id': rid,
                'pay_date': pay_date,
                'driver_id': driver_id,
                'employee_id': employee_id,
                'charter_id': charter_id,
                'reserve_number': reserve_number,
                'gross_pay': gross_pay,
                'note': 'Verify banked, not paid'
            })

    write_csv(EXPORT_DIR / 'pauls_pay_audit_2014_2025.csv', results,
              ['paul_employee_id','paul_employee_number','paul_name','payroll_id','pay_date','driver_id','employee_id','charter_id','reserve_number','gross_pay','note'])

    # Heuristic: search banking transactions for possible payments to Paul names (by last name token)
    lastnames = set()
    for p in pauls:
        if p['name']:
            parts = p['name'].strip().split()
            if len(parts) >= 2:
                lastnames.add(parts[-1].lower())

    found_bank = []
    total_bank = 0.0
    for ln in lastnames:
        rows = fetchall(cur, """
            SELECT transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE transaction_date >= DATE '2014-01-01'
              AND debit_amount > 0
              AND LOWER(description) LIKE %s
            ORDER BY transaction_date
        """, (f"%{ln}%",))
        for r in rows:
            found_bank.append({'lastname': ln, 'transaction_date': r[0], 'description': r[1], 'debit_amount': r[2]})
            total_bank += float(r[2] or 0)

    if found_bank:
        write_csv(EXPORT_DIR / 'pauls_possible_bank_payments_2014_2025.csv', found_bank,
                  ['lastname','transaction_date','description','debit_amount'])

    print(f"Paul candidates: {len(pauls)}; payroll entries 2014+: {total_count:,}; total gross: ${total_amount:,.2f}")
    if found_bank:
        print(f"Possible bank payments mentioning Paul last names since 2014: {len(found_bank):,}; total debit: ${total_bank:,.2f}")

    cur.close(); conn.close()


def audit_david_richard_runs():
    """Find any charters assigned to a driver whose name matches 'David Richard'.
    Writes CSV for 2014-2025 to exports/driver_audit/david_richard_charters_2014_2025.csv
    """
    conn = connect(); cur = conn.cursor()

    # Find employees with names containing both 'david' and 'richard' in any order
    cand_rows = fetchall(cur, """
        SELECT employee_id, employee_number, COALESCE(full_name, first_name || ' ' || last_name) AS name
        FROM employees
        WHERE LOWER(COALESCE(full_name, first_name || ' ' || last_name)) LIKE '%david%'
          AND LOWER(COALESCE(full_name, first_name || ' ' || last_name)) LIKE '%richard%'
    """)
    candidate_ids = [r[0] for r in cand_rows]

    results = []
    if candidate_ids:
        # Charters with assigned_driver_id in candidate IDs
        rows = fetchall(cur, """
            SELECT c.charter_id, c.reserve_number, c.charter_date, c.assigned_driver_id,
                   COALESCE(e.full_name, c.driver_name) AS assigned_driver_name
            FROM charters c
            LEFT JOIN employees e ON e.employee_id = c.assigned_driver_id
            WHERE c.charter_date >= DATE '2014-01-01' AND c.charter_date <= DATE '2025-12-31'
              AND c.assigned_driver_id = ANY(%s)
              AND COALESCE(c.cancelled, false) = false
            ORDER BY c.charter_date
        """, (candidate_ids,))
        for r in rows:
            results.append({
                'charter_id': r[0],
                'reserve_number': r[1],
                'charter_date': r[2],
                'assigned_driver_id': r[3],
                'assigned_driver_name': r[4],
                'match_type': 'assigned_driver_id'
            })

    # Also search by free-text driver_name for robustness
    rows2 = fetchall(cur, """
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.assigned_driver_id,
               COALESCE(e.full_name, c.driver_name) AS assigned_driver_name
        FROM charters c
        LEFT JOIN employees e ON e.employee_id = c.assigned_driver_id
        WHERE c.charter_date >= DATE '2014-01-01' AND c.charter_date <= DATE '2025-12-31'
          AND COALESCE(c.cancelled, false) = false
          AND LOWER(COALESCE(e.full_name, c.driver_name)) LIKE '%david%'
          AND LOWER(COALESCE(e.full_name, c.driver_name)) LIKE '%richard%'
        ORDER BY c.charter_date
    """)
    for r in rows2:
        results.append({
            'charter_id': r[0],
            'reserve_number': r[1],
            'charter_date': r[2],
            'assigned_driver_id': r[3],
            'assigned_driver_name': r[4],
            'match_type': 'name_text_match'
        })

    # Deduplicate by charter_id
    seen = set()
    deduped = []
    for row in results:
        if row['charter_id'] in seen:
            continue
        seen.add(row['charter_id'])
        deduped.append(row)

    out_path = EXPORT_DIR / 'david_richard_charters_2014_2025.csv'
    write_csv(out_path, deduped, ['charter_id','reserve_number','charter_date','assigned_driver_id','assigned_driver_name','match_type'])

    print(f"David Richard charter matches (2014-2025): {len(deduped):,}")

    cur.close(); conn.close()

if __name__ == '__main__':
    print("Running charter vs payroll audit (2021-2024) and Paul's pay audit...")
    audit_mismatches()
    audit_pauls_pay()
    audit_david_richard_runs()
    print(f"CSV outputs written to: {EXPORT_DIR}")
