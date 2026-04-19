import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
import pyodbc

LMS_DB = r"L:\limo\db\lms2026d.mdb"
REPORT_DIR = Path(r"L:\limo\reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

PG_CONN = dict(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)


def norm_reserve(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    if re.fullmatch(r"\d+", s):
        return s.zfill(6)
    return s


def norm_key(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    if re.fullmatch(r"\d+(?:\.0+)?", s):
        return str(int(float(s)))
    return s


def to_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return pd.NaT
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return pd.NaT


def reserve_set(values):
    vals = sorted({x for x in values if isinstance(x, str) and x})
    return "|".join(vals)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # LMS Payment load
    acc = pyodbc.connect(
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB + ";"
    )
    lms_sql = (
        "SELECT Reserve_No, Amount, [Key] AS payment_key, LastUpdated, PaymentID "
        "FROM Payment"
    )
    lms = pd.read_sql(lms_sql, acc)
    acc.close()

    lms = lms.rename(
        columns={
            "Reserve_No": "reserve_number",
            "Amount": "amount",
            "LastUpdated": "payment_dt",
            "PaymentID": "payment_id",
        }
    )
    lms["reserve_number"] = lms["reserve_number"].map(norm_reserve)
    lms["payment_key"] = lms["payment_key"].map(norm_key)
    lms["amount"] = pd.to_numeric(lms["amount"], errors="coerce").fillna(0.0).round(2)
    lms["payment_date"] = lms["payment_dt"].map(to_date)

    # PostgreSQL payments load
    pg = psycopg2.connect(**PG_CONN)
    pg_sql = (
        "SELECT reserve_number, amount, payment_key, payment_date, payment_id, payment_method "
        "FROM payments"
    )
    pgs = pd.read_sql_query(pg_sql, pg)
    pg.close()

    pgs["reserve_number"] = pgs["reserve_number"].map(norm_reserve)
    pgs["payment_key"] = pgs["payment_key"].map(norm_key)
    pgs["amount"] = pd.to_numeric(pgs["amount"], errors="coerce").fillna(0.0).round(2)
    pgs["payment_date"] = pd.to_datetime(pgs["payment_date"], errors="coerce").dt.date

    # key-focused audit (non-empty keys)
    lmsk = lms[lms["payment_key"] != ""].copy()
    pgk = pgs[pgs["payment_key"] != ""].copy()

    lms_key_agg = (
        lmsk.groupby("payment_key", dropna=False)
        .agg(
            lms_rows=("payment_key", "size"),
            lms_total=("amount", "sum"),
            lms_min_date=("payment_date", "min"),
            lms_max_date=("payment_date", "max"),
            lms_reserve_set=("reserve_number", reserve_set),
        )
        .reset_index()
    )
    pg_key_agg = (
        pgk.groupby("payment_key", dropna=False)
        .agg(
            pg_rows=("payment_key", "size"),
            pg_total=("amount", "sum"),
            pg_min_date=("payment_date", "min"),
            pg_max_date=("payment_date", "max"),
            pg_reserve_set=("reserve_number", reserve_set),
        )
        .reset_index()
    )

    lms_keys = set(lms_key_agg["payment_key"])
    pg_keys = set(pg_key_agg["payment_key"])

    missing_keys = sorted(lms_keys - pg_keys)
    extra_keys = sorted(pg_keys - lms_keys)

    missing_in_pg = lmsk[lmsk["payment_key"].isin(missing_keys)].copy()
    extra_in_pg = pgk[pgk["payment_key"].isin(extra_keys)].copy()

    key_cmp = lms_key_agg.merge(pg_key_agg, on="payment_key", how="inner")
    key_cmp["rows_match"] = key_cmp["lms_rows"] == key_cmp["pg_rows"]
    key_cmp["total_match"] = (key_cmp["lms_total"].round(2) == key_cmp["pg_total"].round(2))
    key_cmp["reserve_match"] = key_cmp["lms_reserve_set"] == key_cmp["pg_reserve_set"]
    key_cmp["date_window_match"] = (
        key_cmp["lms_min_date"].astype(str).eq(key_cmp["pg_min_date"].astype(str))
        & key_cmp["lms_max_date"].astype(str).eq(key_cmp["pg_max_date"].astype(str))
    )
    key_mismatches = key_cmp[
        ~(key_cmp["rows_match"] & key_cmp["total_match"] & key_cmp["reserve_match"])
    ].copy()

    # reserve totals audit (all rows)
    lms_res = (
        lms.groupby("reserve_number", dropna=False)["amount"]
        .sum()
        .reset_index(name="lms_total")
    )
    pg_res = (
        pgs.groupby("reserve_number", dropna=False)["amount"]
        .sum()
        .reset_index(name="pg_total")
    )
    res_cmp = lms_res.merge(pg_res, on="reserve_number", how="outer").fillna(0.0)
    res_cmp["difference"] = (res_cmp["pg_total"] - res_cmp["lms_total"]).round(2)
    reserve_diffs = res_cmp[res_cmp["difference"].abs() > 0.009].copy()
    reserve_diffs = reserve_diffs.sort_values("difference", key=lambda s: s.abs(), ascending=False)

    # Write outputs
    base = REPORT_DIR / f"lms2026d_mispayment_audit_{ts}"
    missing_path = Path(str(base) + "_missing_in_pg.csv")
    extra_path = Path(str(base) + "_extra_in_pg.csv")
    mismatch_path = Path(str(base) + "_key_mismatches.csv")
    reserve_path = Path(str(base) + "_reserve_total_differences.csv")
    summary_path = Path(str(base) + "_summary.txt")

    missing_in_pg.to_csv(missing_path, index=False)
    extra_in_pg.to_csv(extra_path, index=False)
    key_mismatches.to_csv(mismatch_path, index=False)
    reserve_diffs.to_csv(reserve_path, index=False)

    lines = [
        f"LMS rows: {len(lms):,}",
        f"PG payment rows: {len(pgs):,}",
        f"LMS keyed rows: {len(lmsk):,}",
        f"PG keyed rows: {len(pgk):,}",
        f"Missing keys in PG: {len(missing_keys):,}",
        f"Extra keys in PG: {len(extra_keys):,}",
        f"Key-level mismatches (shared keys with diff rows/totals/reserves): {len(key_mismatches):,}",
        f"Reserve total differences: {len(reserve_diffs):,}",
        f"LMS total amount: {lms['amount'].sum():,.2f}",
        f"PG total amount: {pgs['amount'].sum():,.2f}",
        f"PG-LMS amount delta: {pgs['amount'].sum() - lms['amount'].sum():,.2f}",
        "",
        f"missing_in_pg: {missing_path}",
        f"extra_in_pg: {extra_path}",
        f"key_mismatches: {mismatch_path}",
        f"reserve_total_differences: {reserve_path}",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
