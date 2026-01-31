#!/usr/bin/env python3
import pyodbc
from pathlib import Path

LMS_PATH = Path(r"L:\limo\backups\lms.mdb")

print(f"LMS file: {LMS_PATH}")
if not LMS_PATH.exists():
    raise SystemExit("LMS file not found")

conn = pyodbc.connect(rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};")
cur = conn.cursor()

print("\n--- Reserve columns ---")
cur.execute("SELECT * FROM Reserve WHERE 1=0")
cols = [d[0] for d in cur.description]
for c in cols:
    print(f"  - {c}")

print("\n--- Reserve routing-ish sample (first 5) ---")
cur.execute(
    """
    SELECT TOP 5
        Reserve_No,
        PU_Date,
        PU_Time,
        Drop_Off,
        Line_1,
        Line_2,
        Routing,
        Notes,
        Trip_Notes
    FROM Reserve
    ORDER BY Reserve_No
    """
)
for row in cur.fetchall():
    print(row)

print("\n--- Field population counts ---")
count_fields = [
    ("Line_1", "Line_1 <> ''"),
    ("Line_2", "Line_2 <> ''"),
    ("Routing", "Routing <> ''"),
    ("From_To", "From_To <> ''"),
    ("Trip_Notes", "Trip_Notes <> ''"),
]
for label, predicate in count_fields:
    cur.execute(f"SELECT COUNT(*) FROM Reserve WHERE {predicate}")
    n = cur.fetchone()[0]
    print(f"{label:12s}: {n}")

print("\n--- Sample with non-empty Routing ---")
cur.execute(
    """
    SELECT TOP 5 Reserve_No, Line_1, Line_2, Routing
    FROM Reserve
    WHERE Routing <> ''
    ORDER BY Reserve_No
    """
)
for row in cur.fetchall():
    print(row)

print("\n--- Additional timing/address sample (first 5) ---")
cur.execute(
    """
    SELECT TOP 5
        Reserve_No,
        PU_Date,
        PU_Time,
        Do_Time,
        Drop_Off,
        From_To,
        Line_1,
        Line_2
    FROM Reserve
    ORDER BY Reserve_No
    """
)
for row in cur.fetchall():
    print(row)

print("\n--- Sample with non-empty Line_2 (first 5) ---")
cur.execute(
    """
    SELECT TOP 5
        Reserve_No,
        Line_1,
        Line_2,
        From_To
    FROM Reserve
    WHERE Line_2 <> ''
    ORDER BY Reserve_No
    """
)
for row in cur.fetchall():
    print(row)

print("\n--- Tables containing route/stop ---")
tables = []
try:
    tables = [r[0] for r in conn.cursor().execute("SELECT name FROM MSysObjects WHERE Type=1 AND Flags=0").fetchall()]
except Exception as e:
    print(f"Unable to list MSysObjects: {e}")

if tables:
    for t in sorted(tables):
        t_lower = t.lower()
        if any(key in t_lower for key in ["route", "routing", "stop"]):
            print(f"  - {t}")

    print("\n--- Table column preview for Route-like tables ---")
    for t in sorted(tables):
        t_lower = t.lower()
        if any(key in t_lower for key in ["route", "routing", "stop"]):
            try:
                c2 = conn.cursor()
                c2.execute(f"SELECT * FROM [{t}] WHERE 1=0")
                cols2 = [d[0] for d in c2.description]
                print(f"{t}: {', '.join(cols2)}")
            except Exception as e:
                print(f"{t}: error reading columns ({e})")

conn.close()
