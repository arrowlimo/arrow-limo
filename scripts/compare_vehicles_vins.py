import os
import psycopg2
from collections import defaultdict

DB = dict(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***'),
)

VIN_CANDIDATE_COLS = ['vin_number', 'vin', 'vehicle_vin', 'vin_no']


def get_conn():
    return psycopg2.connect(**DB)


def find_vehicle_vin_column(cur):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='vehicles'
        ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    for c in VIN_CANDIDATE_COLS:
        if c in cols:
            return c
    # fallback: try to find any column containing 'vin'
    for c in cols:
        if 'vin' in c.lower():
            return c
    return None


def normalize_vin(v):
    if not v:
        return None
    return ''.join(str(v).upper().split())


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("="*80)
    print("VEHICLE VIN COMPARISON: staging (lms_staging_vehicles) vs production (vehicles)")
    print("="*80)

    # Determine VIN column in production
    vin_col = find_vehicle_vin_column(cur)
    if not vin_col:
        print("ERROR: Could not determine VIN column in 'vehicles' table.")
        return
    print(f"Using vehicles.{vin_col} as VIN column")

    # Load production VINs
    cur.execute(f"""
        SELECT DISTINCT {vin_col}
        FROM vehicles
        WHERE {vin_col} IS NOT NULL AND LENGTH({vin_col}) >= 11
    """)
    prod_vins = {normalize_vin(r[0]) for r in cur.fetchall() if normalize_vin(r[0])}
    print(f"Production VINs: {len(prod_vins):,} distinct")

    # Load staging VINs
    cur.execute("""
        SELECT vehicle_code, vin
        FROM lms_staging_vehicles
        WHERE vin IS NOT NULL AND vin <> ''
        ORDER BY vehicle_code
    """)
    staging_rows = cur.fetchall()
    staging_vins = {normalize_vin(v): code for code, v in staging_rows if normalize_vin(v)}
    print(f"Staging VINs: {len(staging_vins):,} distinct (from {len(staging_rows)} rows)")

    # Compare
    missing_in_production = {vin: staging_vins[vin] for vin in staging_vins.keys() if vin not in prod_vins}
    print(f"Missing in production (present in staging only): {len(missing_in_production):,}")

    if missing_in_production:
        print("\nVINs missing in production:")
        for vin, code in sorted(missing_in_production.items(), key=lambda x: x[1]):
            print(f"  {code:<12} {vin}")

    # Loan data check via email_financial_events
    print("\n"+"-"*80)
    print("LOAN / FINANCING DATA CHECK (email_financial_events)")
    print("-"*80)

    # Introspect email_financial_events columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='email_financial_events'
    """)
    efe_cols = {r[0] for r in cur.fetchall()}

    efe_has_vin = 'vin' in efe_cols
    efe_has_lender = 'lender_name' in efe_cols
    efe_has_loan_id = 'loan_external_id' in efe_cols
    efe_has_policy = 'policy_number' in efe_cols

    print(f"email_financial_events columns: vin={efe_has_vin}, lender_name={efe_has_lender}, loan_external_id={efe_has_loan_id}, policy_number={efe_has_policy}")

    loan_status = {}

    if efe_has_vin:
        # Check only staging VINs for coverage
        for vin, code in staging_vins.items():
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE lender_name IS NOT NULL AND lender_name <> '') as lenders,
                    COUNT(*) FILTER (WHERE loan_external_id IS NOT NULL AND loan_external_id <> '') as loan_ids,
                    COUNT(*) FILTER (WHERE policy_number IS NOT NULL AND policy_number <> '') as policies
                FROM email_financial_events
                WHERE vin = %s
            """, (vin,))
            lenders, loan_ids, policies = cur.fetchone()
            loan_status[vin] = dict(code=code, lenders=lenders, loan_ids=loan_ids, policies=policies)

        no_lender = {vin: s for vin, s in loan_status.items() if s['lenders'] == 0}
        no_loan_id = {vin: s for vin, s in loan_status.items() if s['loan_ids'] == 0}
        no_policy = {vin: s for vin, s in loan_status.items() if s['policies'] == 0}

        print(f"\nVINs with NO lender_name entries: {len(no_lender):,}")
        if no_lender:
            for vin, s in sorted(no_lender.items(), key=lambda x: x[1]['code']):
                print(f"  {s['code']:<12} {vin}")

        print(f"\nVINs with NO loan_external_id entries: {len(no_loan_id):,}")
        if no_loan_id:
            for vin, s in sorted(no_loan_id.items(), key=lambda x: x[1]['code']):
                print(f"  {s['code']:<12} {vin}")

        print(f"\nVINs with NO policy_number entries: {len(no_policy):,}")
        if no_policy:
            for vin, s in sorted(no_policy.items(), key=lambda x: x[1]['code']):
                print(f"  {s['code']:<12} {vin}")
    else:
        print("email_financial_events has no VIN column; skipping loan check")

    # Also check vehicles table for finance fields if exist
    print("\n"+"-"*80)
    print("VEHICLES TABLE FINANCING FIELDS")
    print("-"*80)
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='vehicles'
    """)
    vcols = {r[0] for r in cur.fetchall()}
    finance_cols = [c for c in ['financing_partner','lease_status','insurance_policy','insurance_expiry'] if c in vcols]
    print(f"Available finance-related columns: {', '.join(finance_cols) if finance_cols else '(none)'}")

    if finance_cols and vin_col:
        cur.execute(f"""
            SELECT COUNT(*) FROM vehicles WHERE {vin_col} IS NOT NULL AND (
                { ' OR '.join([f"{c} IS NOT NULL AND {c} <> ''" for c in finance_cols]) }
            )
        """)
        with_fin = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM vehicles WHERE {vin_col} IS NOT NULL")
        total_v = cur.fetchone()[0]
        print(f"Vehicles with any finance/insurance data: {with_fin:,} / {total_v:,}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
