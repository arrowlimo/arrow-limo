"""
Compare staged vehicle VINs to production `vehicles` by VIN; report missing vehicles and missing loan data.

Outputs:
- Console summary of:
  * Discovered staging tables/columns containing VINs
  * Count of distinct staged VINs (normalized 17-char)
  * Count of distinct production VINs (vehicles table)
  * VINs present in staging but missing from vehicles (top 50 listed)
  * VINs with no loan/financing evidence in `email_financial_events`
- Optional CSV at reports/staged_vehicle_vin_comparison.csv (created if any differences)

Assumptions:
- Production table is `vehicles` with VIN column `vin_number` (falls back to columns like vin, vehicle_vin)
- Staging VIN columns discovered via information_schema where column_name ILIKE '%vin%'
- Loan evidence checked via `email_financial_events` where vin matches and (lender_name IS NOT NULL OR event_type ILIKE '%loan%' OR event_type ILIKE '%lease%' OR notes ILIKE '%finance%')
"""

import os
import re
import csv
from typing import Dict, List, Set, Tuple

import psycopg2
import psycopg2.extras

PG_CONN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

VIN_REGEX = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")  # Excludes I, O, Q


def get_conn():
    return psycopg2.connect(**PG_CONN)


def normalize_vin(v: str) -> str:
    if not v:
        return ''
    v = v.strip().upper().replace(' ', '')
    # Remove common separators
    v = v.replace('-', '').replace('_', '')
    return v


def discover_vin_sources(cur) -> List[Tuple[str, str]]:
    """Return list of (table_name, column_name) with VIN-like columns excluding `vehicles` table."""
    cur.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name ILIKE '%vin%'
        ORDER BY table_name, ordinal_position
        """
    )
    candidates = [(r[0], r[1]) for r in cur.fetchall()]

    # Filter out obvious non-vehicle contexts if needed later; for now exclude vehicles table
    return [(t, c) for (t, c) in candidates if t != 'vehicles']


def get_production_vins(cur) -> Tuple[str, Set[str]]:
    """Detect VIN column in vehicles and return (column_name, set of normalized VINs)."""
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'vehicles' AND column_name ILIKE '%vin%'
        ORDER BY ordinal_position
        """
    )
    cols = [r[0] for r in cur.fetchall()]
    vin_col = None
    for name in ['vin_number', 'vin', 'vehicle_vin', 'vin_no']:
        if name in cols:
            vin_col = name
            break
    if not vin_col:
        vin_col = cols[0] if cols else None
    if not vin_col:
        return '', set()

    cur.execute(f"SELECT DISTINCT {psycopg2.extensions.AsIs(vin_col)} FROM vehicles")
    vins = set()
    for (v,) in cur.fetchall():
        nv = normalize_vin(v if isinstance(v, str) else (v.decode() if v is not None else ''))
        if VIN_REGEX.match(nv):
            vins.add(nv)
    return vin_col, vins


def collect_staged_vins(cur, sources: List[Tuple[str, str]]) -> Dict[str, Set[str]]:
    """Return mapping table_name -> set of normalized VINs from that source."""
    staged: Dict[str, Set[str]] = {}
    for table, col in sources:
        try:
            cur.execute(f"SELECT DISTINCT {psycopg2.extensions.AsIs(col)} FROM {psycopg2.extensions.AsIs(table)}")
            vals = set()
            for (v,) in cur.fetchall():
                nv = normalize_vin(v if isinstance(v, str) else (v.decode() if v is not None else ''))
                if VIN_REGEX.match(nv):
                    vals.add(nv)
            if vals:
                staged.setdefault(f"{table}.{col}", set()).update(vals)
        except Exception as e:
            # Skip tables we cannot read
            print(f"WARN: Skipping {table}.{col}: {e}")
    return staged


def have_loan_evidence(cur, vin: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM email_financial_events efe
        WHERE (efe.vin = %s OR efe.vehicle_id IN (
                 SELECT vehicle_id FROM vehicles v
                 WHERE (v.vin_number = %s OR v.vin_number = %s)
               ))
          AND (
              lender_name IS NOT NULL AND lender_name <> ''
              OR event_type ILIKE '%loan%'
              OR event_type ILIKE '%lease%'
              OR notes ILIKE '%finance%'
          )
        LIMIT 1
        """,
        (vin, vin, vin)
    )
    return cur.fetchone() is not None


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("Discovering VIN sources in staging/public...")
    sources = discover_vin_sources(cur)
    if not sources:
        print("No VIN-like columns found beyond `vehicles`.")
        return
    print(f"Found {len(sources)} candidate VIN columns (excluding vehicles):")
    for t, c in sources:
        print(f"  - {t}.{c}")

    print("\nLoading production VINs from vehicles...")
    vin_col, prod_vins = get_production_vins(cur)
    print(f"vehicles VIN column: {vin_col or 'NOT FOUND'}; count={len(prod_vins)}")

    print("\nCollecting staged VINs from discovered sources...")
    staged_map = collect_staged_vins(cur, sources)

    staged_union: Set[str] = set()
    for src, vins in staged_map.items():
        print(f"  {src}: {len(vins)} VINs")
        staged_union |= vins

    print(f"\nTotal distinct staged VINs: {len(staged_union)}")

    # Compare
    missing_in_vehicles = sorted(v for v in staged_union if v not in prod_vins)
    print(f"VINs present in staging but missing in vehicles: {len(missing_in_vehicles)}")
    for v in missing_in_vehicles[:50]:
        print(f"  - {v}")
    if len(missing_in_vehicles) > 50:
        print(f"  ... {len(missing_in_vehicles)-50} more")

    # Loan evidence
    print("\nAssessing loan/financing evidence via email_financial_events...")
    no_loan_vins = []
    checked = 0
    for v in sorted(staged_union):
        checked += 1
        if not have_loan_evidence(cur, v):
            no_loan_vins.append(v)
        # keep it reasonably fast; we're scanning all, but OK for now

    print(f"VINs with NO loan/financing evidence: {len(no_loan_vins)}")
    for v in no_loan_vins[:50]:
        print(f"  - {v}")
    if len(no_loan_vins) > 50:
        print(f"  ... {len(no_loan_vins)-50} more")

    # Optional CSV report
    os.makedirs('reports', exist_ok=True)
    csv_path = os.path.join('reports', 'staged_vehicle_vin_comparison.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['category', 'vin'])
        for v in missing_in_vehicles:
            w.writerow(['missing_in_vehicles', v])
        for v in no_loan_vins:
            w.writerow(['no_loan_evidence', v])
    print(f"\nReport written: {csv_path}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
