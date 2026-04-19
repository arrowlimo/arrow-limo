import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
import pyodbc
from psycopg2 import sql

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

TS = datetime.now().strftime("%Y%m%d_%H%M%S")


def norm_reserve(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    if re.fullmatch(r"\d+", s):
        return s.zfill(6)
    return s


def canon_key(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    if re.fullmatch(r"\d+(?:\.0+)?", s):
        return str(int(float(s)))
    return s


def stored_key(v):
    key = canon_key(v)
    if re.fullmatch(r"\d+", key):
        return key.zfill(7)
    return key


def to_date(v):
    if v is None or pd.isna(v):
        return pd.NaT
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return pd.NaT


def load_lms():
    acc = pyodbc.connect(
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB + ";"
    )
    q = (
        "SELECT Reserve_No, Amount, [Key] AS payment_key, LastUpdated, PaymentID "
        "FROM Payment"
    )
    df = pd.read_sql(q, acc)
    acc.close()
    df = df.rename(
        columns={
            "Reserve_No": "reserve_number",
            "Amount": "amount",
            "LastUpdated": "payment_dt",
            "PaymentID": "lms_payment_id",
        }
    )
    df["reserve_number"] = df["reserve_number"].map(norm_reserve)
    df["payment_key_canon"] = df["payment_key"].map(canon_key)
    df["payment_key_store"] = df["payment_key"].map(stored_key)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).round(2)
    df["payment_date"] = df["payment_dt"].map(to_date)
    df = df[df["payment_key_canon"] != ""].copy()
    return df


def load_pg(conn):
    q = (
        "SELECT payment_id, reserve_number, amount, payment_key, payment_date, payment_method "
        "FROM payments WHERE payment_key IS NOT NULL AND TRIM(payment_key) <> ''"
    )
    df = pd.read_sql_query(q, conn)
    df["reserve_number"] = df["reserve_number"].map(norm_reserve)
    df["payment_key_canon"] = df["payment_key"].map(canon_key)
    df["payment_key_store"] = df["payment_key"].map(stored_key)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).round(2)
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce").dt.date
    return df


def sort_rows(df, is_pg):
    cols = ["payment_date", "amount", "reserve_number"]
    if is_pg:
        cols.append("payment_id")
    else:
        cols.append("lms_payment_id")
    return df.sort_values(cols, na_position="last").reset_index(drop=True)


def make_sync_plan(lms, pg):
    lms_keys = sorted(set(lms["payment_key_canon"]))
    pg_by_key = {k: sort_rows(g.copy(), True) for k, g in pg.groupby("payment_key_canon")}
    lms_by_key = {k: sort_rows(g.copy(), False) for k, g in lms.groupby("payment_key_canon")}

    updates = []
    inserts = []
    delete_rows = []
    affected_old_reserves = set()
    affected_new_reserves = set()

    for key in lms_keys:
        lsub = lms_by_key[key]
        psub = pg_by_key.get(key, pd.DataFrame(columns=pg.columns))
        pair_count = min(len(lsub), len(psub))

        for idx in range(pair_count):
            lrow = lsub.iloc[idx]
            prow = psub.iloc[idx]
            affected_old_reserves.add(prow["reserve_number"])
            affected_new_reserves.add(lrow["reserve_number"])
            desired_key = lrow["payment_key_store"]
            if (
                prow["reserve_number"] != lrow["reserve_number"]
                or round(float(prow["amount"]), 2) != round(float(lrow["amount"]), 2)
                or prow["payment_date"] != lrow["payment_date"]
                or prow["payment_key"] != desired_key
            ):
                updates.append(
                    {
                        "payment_id": int(prow["payment_id"]),
                        "payment_key_canon": key,
                        "reserve_number": lrow["reserve_number"],
                        "amount": round(float(lrow["amount"]), 2),
                        "payment_date": lrow["payment_date"],
                        "payment_key": desired_key,
                    }
                )

        if len(psub) > pair_count:
            extra = psub.iloc[pair_count:]
            delete_rows.extend(
                [
                    {
                        "payment_id": int(payment_id),
                        "payment_key_canon": key,
                        "reserve_number": reserve_number,
                    }
                    for payment_id, reserve_number in zip(
                        extra["payment_id"].astype(int).tolist(),
                        extra["reserve_number"].tolist(),
                    )
                ]
            )
            affected_old_reserves.update(extra["reserve_number"].tolist())

        if len(lsub) > pair_count:
            missing = lsub.iloc[pair_count:]
            for _, lrow in missing.iterrows():
                inserts.append(
                    {
                        "payment_key_canon": key,
                        "reserve_number": lrow["reserve_number"],
                        "amount": round(float(lrow["amount"]), 2),
                        "payment_date": lrow["payment_date"],
                        "payment_key": lrow["payment_key_store"],
                    }
                )
                affected_new_reserves.add(lrow["reserve_number"])

    affected_reserves = sorted({r for r in affected_old_reserves | affected_new_reserves if r})
    return updates, inserts, delete_rows, affected_reserves


def fetch_unique_reserve_map(conn, reserves):
    q = """
        SELECT reserve_number, COUNT(*) AS charter_count, MIN(charter_id) AS charter_id
        FROM charters
        WHERE reserve_number = ANY(%s)
        GROUP BY reserve_number
        ORDER BY reserve_number
    """
    df = pd.read_sql_query(q, conn, params=(reserves,))
    return df


def find_referenced_payment_ids(conn, payment_ids):
    if not payment_ids:
        return set()

    ref_meta_sql = """
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND ccu.table_name = 'payments'
          AND ccu.column_name = 'payment_id'
    """
    refs = pd.read_sql_query(ref_meta_sql, conn)
    found = set()
    with conn.cursor() as cur:
        for _, ref in refs.iterrows():
            query = sql.SQL("SELECT DISTINCT {col} FROM {tbl} WHERE {col} = ANY(%s)").format(
                col=sql.Identifier(ref["column_name"]),
                tbl=sql.Identifier(ref["table_name"]),
            )
            cur.execute(query, (payment_ids,))
            found.update(row[0] for row in cur.fetchall() if row[0] is not None)
    return found


def backup_existing_rows(cur, table_name, sql_where, params=()):
    backup_name = f"backup_{table_name}_{TS}"
    cur.execute(f"DROP TABLE IF EXISTS {backup_name}")
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name} WHERE false")
    cur.execute(f"INSERT INTO {backup_name} SELECT * FROM {table_name} WHERE {sql_where}", params)
    return backup_name


def main():
    lms = load_lms()
    conn = psycopg2.connect(**PG_CONN)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        pg = load_pg(conn)
        updates, inserts, delete_rows, affected_reserves = make_sync_plan(lms, pg)

        if not affected_reserves:
            print("No LMS-keyed reserve changes detected.")
            conn.rollback()
            return

        reserve_map = fetch_unique_reserve_map(conn, affected_reserves)
        missing_charters = sorted(set(affected_reserves) - set(reserve_map["reserve_number"]))
        ambiguous = reserve_map[reserve_map["charter_count"] != 1].copy()
        rebuild_reserves = sorted(
            set(reserve_map[reserve_map["charter_count"] == 1]["reserve_number"].tolist())
        )
        blocked_keys = set(lms[lms["reserve_number"].isin(missing_charters)]["payment_key_canon"].tolist())
        if not ambiguous.empty:
            blocked_keys.update(
                lms[lms["reserve_number"].isin(ambiguous["reserve_number"].tolist())]["payment_key_canon"]
                .tolist()
            )

        updates = [row for row in updates if row["payment_key_canon"] not in blocked_keys]
        inserts = [row for row in inserts if row["payment_key_canon"] not in blocked_keys]
        delete_rows = [row for row in delete_rows if row["payment_key_canon"] not in blocked_keys]
        delete_ids = sorted({row["payment_id"] for row in delete_rows})

        referenced_delete_ids = find_referenced_payment_ids(conn, delete_ids)
        if referenced_delete_ids:
            blocked_keys.update(
                row["payment_key_canon"]
                for row in delete_rows
                if row["payment_id"] in referenced_delete_ids
            )
            updates = [row for row in updates if row["payment_key_canon"] not in blocked_keys]
            inserts = [row for row in inserts if row["payment_key_canon"] not in blocked_keys]
            delete_rows = [row for row in delete_rows if row["payment_key_canon"] not in blocked_keys]
            delete_ids = sorted({row["payment_id"] for row in delete_rows})

        executable_old_reserves = {row["reserve_number"] for row in delete_rows if row["reserve_number"]}
        update_payment_ids = [row["payment_id"] for row in updates]
        executable_old_reserves.update(
            reserve
            for reserve in pg[pg["payment_id"].isin(update_payment_ids)]["reserve_number"].tolist()
            if reserve
        )
        executable_new_reserves = {row["reserve_number"] for row in updates if row["reserve_number"]}
        executable_new_reserves.update(row["reserve_number"] for row in inserts if row["reserve_number"])
        affected_reserves = sorted(executable_old_reserves | executable_new_reserves)
        rebuild_reserves = sorted(set(rebuild_reserves) & set(affected_reserves))

        touched_payment_ids = sorted({row["payment_id"] for row in updates} | set(delete_ids))
        payment_backup = None
        if touched_payment_ids:
            payment_backup = backup_existing_rows(
                cur,
                "payments",
                "payment_id = ANY(%s)",
                (touched_payment_ids,),
            )

        charter_backup = None
        cp_backup = None
        if rebuild_reserves:
            charter_backup = backup_existing_rows(
                cur,
                "charters",
                "reserve_number = ANY(%s)",
                (rebuild_reserves,),
            )

            cp_backup = backup_existing_rows(
                cur,
                "charter_payments",
                "charter_id IN (SELECT charter_id::text FROM charters WHERE reserve_number = ANY(%s))",
                (rebuild_reserves,),
            )

        for row in updates:
            cur.execute(
                """
                UPDATE payments
                SET reserve_number = %s,
                    amount = %s,
                    payment_date = %s,
                    payment_key = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    version = COALESCE(version, 1) + 1
                WHERE payment_id = %s
                """,
                (
                    row["reserve_number"],
                    row["amount"],
                    row["payment_date"],
                    row["payment_key"],
                    row["payment_id"],
                ),
            )

        if inserts:
            cur.executemany(
                """
                INSERT INTO payments (
                    reserve_number, amount, payment_key, payment_date, payment_method, status, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        row["reserve_number"],
                        row["amount"],
                        row["payment_key"],
                        row["payment_date"],
                        "unknown",
                        "pending",
                        "Inserted from LMS2026d payment sync",
                    )
                    for row in inserts
                ],
            )

        if delete_ids:
            cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (delete_ids,))

        if rebuild_reserves:
            # Rebuild charter_payments only for reserves with a unique local charter row.
            cur.execute(
                """
                DELETE FROM charter_payments
                WHERE charter_id IN (
                    SELECT charter_id::text
                    FROM charters
                    WHERE reserve_number = ANY(%s)
                )
                """,
                (rebuild_reserves,),
            )

            cur.execute(
                """
                INSERT INTO charter_payments (
                    payment_id, charter_id, amount, payment_date, payment_method, payment_key, source
                )
                SELECT
                    p.payment_id,
                    c.charter_id::text,
                    p.amount,
                    p.payment_date,
                    p.payment_method,
                    p.payment_key,
                    'PAYMENTS_TABLE_REBUILD_20260417_LMS2026D_SYNC'
                FROM payments p
                JOIN charters c ON c.reserve_number = p.reserve_number
                WHERE c.reserve_number = ANY(%s)
                """,
                (rebuild_reserves,),
            )

            cur.execute(
                """
                WITH cp_totals AS (
                    SELECT
                        c.charter_id,
                        COALESCE(SUM(cp.amount), 0)::numeric(12,2) AS paid
                    FROM charters c
                    LEFT JOIN charter_payments cp ON cp.charter_id = c.charter_id::text
                    WHERE c.reserve_number = ANY(%s)
                    GROUP BY c.charter_id
                )
                UPDATE charters c
                SET amount_paid = t.paid,
                    balance_owing = ROUND(COALESCE(c.total_amount_due, 0)::numeric - t.paid, 2),
                    balance = ROUND(COALESCE(c.total_amount_due, 0)::numeric - t.paid, 2),
                    payment_totals = t.paid
                FROM cp_totals t
                WHERE c.charter_id = t.charter_id
                """,
                (rebuild_reserves,),
            )

        conn.commit()

        summary = pd.DataFrame(
            {
                "metric": [
                    "updates",
                    "inserts",
                    "deletes",
                    "affected_reserves",
                    "rebuild_reserves",
                    "missing_charter_reserves",
                    "ambiguous_reserves",
                    "payment_backup_rows",
                ],
                "value": [
                    len(updates),
                    len(inserts),
                    len(delete_ids),
                    len(affected_reserves),
                    len(rebuild_reserves),
                    len(missing_charters),
                    len(ambiguous),
                    len(touched_payment_ids),
                ],
            }
        )
        report_path = REPORT_DIR / f"lms2026d_sync_summary_{TS}.csv"
        summary.to_csv(report_path, index=False)

        print(f"payment_backup={payment_backup}")
        print(f"charter_backup={charter_backup}")
        print(f"charter_payments_backup={cp_backup}")
        if missing_charters:
            print("missing_charter_reserves_sample=" + ",".join(missing_charters[:20]))
        if not ambiguous.empty:
            print("ambiguous_reserves_sample=" + ",".join(ambiguous['reserve_number'].astype(str).tolist()[:20]))
        print(summary.to_string(index=False))
        print(f"summary_report={report_path}")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
