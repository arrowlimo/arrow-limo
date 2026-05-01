from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import psycopg2

BASE = Path(r"l:\limo")


def load_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def conn_from_env(env: Dict[str, str]) -> Dict[str, object]:
    out: Dict[str, object] = {
        "host": env.get("DB_HOST", "localhost"),
        "port": int(env.get("DB_PORT", "5432")),
        "dbname": env.get("DB_NAME", "almsdata"),
        "user": env.get("DB_USER", "postgres"),
        "password": env.get("DB_PASSWORD", ""),
    }
    if env.get("DB_SSLMODE"):
        out["sslmode"] = env["DB_SSLMODE"]
    if env.get("DB_CHANNEL_BINDING"):
        out["channel_binding"] = env["DB_CHANNEL_BINDING"]
    return out


def get_max(cur, table: str, col: str):
    cur.execute(f"SELECT MAX({col}) FROM {table}")
    return cur.fetchone()[0]


def get_count(cur, table: str):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


if __name__ == "__main__":
    local_env = load_env(BASE / ".env")
    neon_env = load_env(BASE / ".env.neon")

    local = psycopg2.connect(**conn_from_env(local_env))
    neon = psycopg2.connect(**conn_from_env(neon_env))

    checks: Tuple[Tuple[str, str], ...] = (
        ("charters", "updated_at"),
        ("payments", "created_at"),
        ("receipts", "created_at"),
        ("clients", "updated_at"),
        ("employees", "updated_at"),
        ("vehicles", "updated_at"),
    )

    try:
        lcur = local.cursor()
        ncur = neon.cursor()

        print("table,rowcount_local,rowcount_neon,max_local,max_neon,local_newer_than_neon")
        for table, ts_col in checks:
            lcount = get_count(lcur, table)
            ncount = get_count(ncur, table)
            lmax = get_max(lcur, table, ts_col)
            nmax = get_max(ncur, table, ts_col)
            newer = bool(lmax and (not nmax or lmax > nmax))
            print(f"{table},{lcount},{ncount},{lmax},{nmax},{newer}")

    finally:
        local.close()
        neon.close()
