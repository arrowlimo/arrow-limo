"""
Compare PostgreSQL charter total_amount_due against LMS Est_Charge (authoritative charter total)
Outputs:
  - Yearly aggregate comparison (PG vs LMS for matched charters)
  - List of top discrepancies (abs diff > 0.01)
  - Zero-total PG charters where LMS Est_Charge > 0 (potential missing charges)
  - LMS reserves missing in PG (optional reference)

Safety:
  - READ-ONLY: Does not modify any data
Requirements:
  - pyodbc (Access connection)
  - psycopg2 (PostgreSQL connection)
"""
import os, sys, math
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

LMS_PATH_PRIMARY = r'L:\limo\lms.mdb'
LMS_PATH_BACKUP = r'L:\limo\backups\lms.mdb'

THRESHOLD = 0.01  # penny tolerance
MAX_LIST = 50      # number of top discrepancies to show

def connect_pg():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def connect_lms():
    for path in (LMS_PATH_PRIMARY, LMS_PATH_BACKUP):
        if not os.path.exists(path):
            continue
        try:
            return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};')
        except:
            try:
                return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={path};')
            except Exception as e:
                print(f"Failed Access connect for {path}: {e}")
    raise RuntimeError("Could not connect to any LMS .mdb path")

def normalize_reserve(r):
    if r is None:
        return None
    try:
        s = str(r).strip()
        if s.startswith('REF') or s.startswith('AUDIT'):
            return s  # leave special formats untouched
        # zero-pad pure numeric
        if s.isdigit():
            return s.zfill(6)
        # mixed -> return as-is
        return s
    except Exception:
        return str(r)

def main():
    print("="*110)
    print("CHARTER TOTAL DISCREPANCY ANALYSIS (PG total_amount_due vs LMS Est_Charge)")
    print("="*110)

    lms_conn = connect_lms(); lms_cur = lms_conn.cursor()
    pg_conn = connect_pg(); pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)

    # Fetch LMS reserves (only columns needed)
    lms_cur.execute("SELECT Reserve_No, PU_Date, Est_Charge, LastUpdated FROM Reserve")
    lms_rows = lms_cur.fetchall()

    lms_map = {}
    lms_missing_charge_count = 0
    for row in lms_rows:
        reserve = normalize_reserve(row.Reserve_No)
        est = float(row.Est_Charge) if row.Est_Charge not in (None, '') else 0.0
        lms_map[reserve] = {
            'reserve_number': reserve,
            'est_charge': est,
            'pu_date': row.PU_Date,
            'last_updated': row.LastUpdated
        }
        if est <= 0:
            lms_missing_charge_count += 1

    # Fetch PG charters
    pg_cur.execute("SELECT charter_id, reserve_number, charter_date, total_amount_due FROM charters WHERE reserve_number IS NOT NULL")
    pg_rows = pg_cur.fetchall()

    discrepancies = []
    zero_total = []  # PG total_amount_due == 0 but LMS est_charge > 0
    missing_in_pg = []  # LMS reserve with est_charge > 0 but not in PG

    yearly_pg = defaultdict(float)
    yearly_lms = defaultdict(float)

    for pg in pg_rows:
        reserve = normalize_reserve(pg['reserve_number'])
        pg_total = float(pg['total_amount_due'] or 0.0)
        charter_date = pg['charter_date']
        year = charter_date.year if charter_date else None

        lms = lms_map.get(reserve)
        if not lms:
            # PG charter with no LMS counterpart; treat LMS total as 0
            if year:
                yearly_pg[year] += pg_total
            discrepancies.append({
                'reserve_number': reserve,
                'charter_id': pg['charter_id'],
                'pg_total': pg_total,
                'lms_total': 0.0,
                'diff': pg_total - 0.0,
                'year': year,
                'type': 'PG_ONLY'
            })
            continue

        lms_total = lms['est_charge']
        if year:
            yearly_pg[year] += pg_total
            yearly_lms[year] += lms_total

        diff = pg_total - lms_total
        if abs(diff) > THRESHOLD:
            discrepancies.append({
                'reserve_number': reserve,
                'charter_id': pg['charter_id'],
                'pg_total': pg_total,
                'lms_total': lms_total,
                'diff': diff,
                'year': year,
                'type': 'VALUE_DIFF'
            })
        if pg_total <= THRESHOLD and lms_total > THRESHOLD:
            zero_total.append({
                'reserve_number': reserve,
                'charter_id': pg['charter_id'],
                'lms_total': lms_total,
                'year': year
            })

    # LMS reserves missing in PG
    for reserve, info in lms_map.items():
        if reserve is None:
            continue
        if reserve not in {normalize_reserve(r['reserve_number']) for r in pg_rows} and info['est_charge'] > THRESHOLD:
            y = info['pu_date'].year if info['pu_date'] else None
            missing_in_pg.append({
                'reserve_number': reserve,
                'lms_total': info['est_charge'],
                'year': y
            })
            if y:
                yearly_lms[y] += info['est_charge']  # ensure LMS sum includes these even if PG missing

    # Sort discrepancies by absolute diff descending
    discrepancies.sort(key=lambda d: abs(d['diff']), reverse=True)

    total_pg = sum(yearly_pg.values())
    total_lms = sum(yearly_lms.values())
    net_gap = total_pg - total_lms

    print(f"Total PG charter sum:  ${total_pg:,.2f}")
    print(f"Total LMS Est_Charge sum (matched + missing): ${total_lms:,.2f}")
    print(f"NET GAP (PG - LMS):    ${net_gap:,.2f}\n")

    print("Yearly Summary (PG vs LMS):")
    print(f"{'Year':<6}{'PG_Total':>15}{'LMS_Total':>15}{'Diff':>15}")
    for year in sorted(set(list(yearly_pg.keys()) + list(yearly_lms.keys()))):
        pg_t = yearly_pg.get(year, 0.0)
        lms_t = yearly_lms.get(year, 0.0)
        print(f"{year:<6}{pg_t:15.2f}{lms_t:15.2f}{(pg_t - lms_t):15.2f}")
    print()

    print(f"Top Discrepancies (>|{THRESHOLD:.2f}|) - showing first {min(MAX_LIST, len(discrepancies))}:")
    print(f"{'Reserve':<10}{'CharterID':<10}{'PG_Total':>12}{'LMS_Total':>12}{'Diff':>12}{'Year':>6}{'Type':>12}")
    for d in discrepancies[:MAX_LIST]:
        print(f"{d['reserve_number']:<10}{d['charter_id']:<10}{d['pg_total']:12.2f}{d['lms_total']:12.2f}{d['diff']:12.2f}{d['year']:6}{d['type']:>12}")
    print(f"Total discrepancies count: {len(discrepancies)}\n")

    if zero_total:
        print("Zero-total PG charters with non-zero LMS Est_Charge (potential missing charges):")
        print(f"{'Reserve':<10}{'CharterID':<10}{'LMS_Total':>12}{'Year':>6}")
        for z in zero_total[:MAX_LIST]:
            print(f"{z['reserve_number']:<10}{z['charter_id']:<10}{z['lms_total']:12.2f}{z['year']:6}")
        print(f"Total zero-total suspects: {len(zero_total)}\n")
    else:
        print("No zero-total PG charters with positive LMS Est_Charge detected.\n")

    if missing_in_pg:
        print("LMS reserves missing entirely in PG (Est_Charge > 0):")
        print(f"{'Reserve':<10}{'LMS_Total':>12}{'Year':>6}")
        for m in missing_in_pg[:MAX_LIST]:
            print(f"{m['reserve_number']:<10}{m['lms_total']:12.2f}{m['year']:6}")
        print(f"Total LMS-only reserves: {len(missing_in_pg)}\n")
    else:
        print("No LMS reserves with Est_Charge > 0 missing in PG.\n")

    print("Next Actions Suggestions:\n"
          "  1. Review top VALUE_DIFF records; categorize by charge type (gratuity vs missing surcharge).\n"
          "  2. For ZERO-TOTAL suspects, verify charter_charges rows exist; if absent, import from LMS.\n"
          "  3. Confirm if PG_ONLY entries are legitimate (e.g., post-migration placeholders) or need LMS backfill.\n"
          "  4. Re-run after any corrections to measure gap reduction.")

    pg_cur.close(); pg_conn.close(); lms_cur.close(); lms_conn.close()

if __name__ == '__main__':
    main()
