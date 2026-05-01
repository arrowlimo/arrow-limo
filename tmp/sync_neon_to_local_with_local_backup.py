from __future__ import annotations

import os
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import dotenv_values

BASE = Path(r"L:/limo")
TMP = BASE / "tmp"
TMP.mkdir(parents=True, exist_ok=True)


def q(v: str) -> str:
    return urllib.parse.quote_plus(v)


def run(cmd: list[str]) -> None:
    print("RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    neon_env = dotenv_values(BASE / ".env.neon")
    host = str(neon_env.get("DB_HOST") or "")
    user = str(neon_env.get("DB_USER") or "neondb_owner")
    password = str(neon_env.get("DB_PASSWORD") or "")
    db = str(neon_env.get("DB_NAME") or "neondb")

    if not host or "neon.tech" not in host:
        raise SystemExit("Invalid .env.neon DB_HOST")

    local_user = "postgres"
    local_pass = (
        os.environ.get("LOCAL_DB_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD")
        or "ArrowLimousine"
    )
    local_db = "almsdata"

    neon_uri = (
        f"postgresql://{q(user)}:{q(password)}@{host}:5432/{q(db)}?sslmode=require"
    )
    local_uri = (
        f"postgresql://{q(local_user)}:{q(local_pass)}@localhost:5432/{q(local_db)}?sslmode=disable"
    )

    local_backup = TMP / f"local_pre_neon_restore_{ts}.dump"
    neon_backup = TMP / f"neon_snapshot_{ts}.dump"

    print(f"Creating local safety backup: {local_backup}", flush=True)
    run(
        [
            "pg_dump",
            "--dbname",
            local_uri,
            "-n",
            "public",
            "--format=custom",
            "--file",
            str(local_backup),
            "--no-owner",
            "--no-privileges",
        ]
    )

    print(f"Creating Neon backup snapshot: {neon_backup}", flush=True)
    run(
        [
            "pg_dump",
            "--dbname",
            neon_uri,
            "-n",
            "public",
            "--format=custom",
            "--file",
            str(neon_backup),
            "--no-owner",
            "--no-privileges",
        ]
    )

    print("Dropping local public schema...", flush=True)
    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=local_db,
        user=local_user,
        password=local_pass,
        sslmode="disable",
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")

    for section in ("pre-data", "data", "post-data"):
        print(f"Restoring Neon section: {section}", flush=True)
        run(
            [
                "pg_restore",
                "--dbname",
                local_uri,
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                f"--section={section}",
                str(neon_backup),
            ]
        )

    print("DONE", flush=True)
    print(f"Local backup: {local_backup}", flush=True)
    print(f"Neon snapshot: {neon_backup}", flush=True)
