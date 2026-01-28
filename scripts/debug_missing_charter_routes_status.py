#!/usr/bin/env python3
import os
import json
import psycopg2

MISSING_PATH = r"l:/limo/reports/ROUTING_XLSX_AUDIT_20260116_145637_missing.json"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def main():
    with open(MISSING_PATH, "r", encoding="utf-8") as f:
        missing = json.load(f)
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    seen = set()
    has_charter = []
    no_charter = []
    zero_routes = []

    for rec in missing:
        reserve = rec.get("reserve_no") or rec.get("reserve")
        if not reserve or reserve in seen:
            continue
        seen.add(reserve)
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number=%s LIMIT 1", (reserve,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT charter_id FROM charters WHERE ltrim(reserve_number,'0') = ltrim(%s,'0') LIMIT 1", (reserve,))
            row = cur.fetchone()
        if row:
            has_charter.append((reserve, row[0]))
            cur.execute("SELECT COUNT(*) FROM charter_routes WHERE charter_id=%s", (row[0],))
            cnt = cur.fetchone()[0]
            if cnt == 0:
                zero_routes.append((reserve, row[0]))
        else:
            no_charter.append(reserve)

    print("Total unique reserves:", len(seen))
    print("With charter:", len(has_charter))
    print("Without charter:", len(no_charter))
    print("With charter and zero routes:", len(zero_routes))
    print("\nExamples (first 10) with charter and zero routes:")
    for r, cid in zero_routes[:10]:
        print("  ", r, "charter_id", cid)

    cur.close(); conn.close()


if __name__ == "__main__":
    main()
