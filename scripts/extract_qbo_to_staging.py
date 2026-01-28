#!/usr/bin/env python3
"""
Extract all CIBC .qbo files to a staging table, match transactions to almsdata, and report discrepancies.
"""
import os
import re
import psycopg2
from datetime import datetime
from pathlib import Path

QBO_DIR = r"L:\limo\CIBC UPLOADS\verify this data\New folder"
QBO_FILES = [f"pcbanking ({i}).qbo" for i in range(1, 7)]
STAGING_TABLE = "cibc_qbo_staging"

# QBO transaction regex
TRN_REGEX = re.compile(r"<STMTTRN>.*?<TRNTYPE>(.*?)\n.*?<DTPOSTED>(.*?)\n.*?<TRNAMT>(.*?)\n.*?<FITID>(.*?)\n.*?<NAME>(.*?)\n.*?<MEMO>(.*?)\n.*?</STMTTRN>", re.DOTALL)

def connect_db():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', '')
    )

def create_staging_table(conn):
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {STAGING_TABLE} (
                id SERIAL PRIMARY KEY,
                file_name TEXT,
                trntype TEXT,
                dtposted DATE,
                trnamt NUMERIC,
                fitid TEXT,
                name TEXT,
                memo TEXT
            )
        """)
        conn.commit()

def extract_qbo_files_to_staging(conn):
    create_staging_table(conn)
    for fname in QBO_FILES:
        fpath = os.path.join(QBO_DIR, fname)
        if not os.path.exists(fpath):
            print(f"Missing: {fpath}")
            continue
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            for match in TRN_REGEX.finditer(content):
                trntype, dtposted, trnamt, fitid, name, memo = match.groups()
                # Parse date
                try:
                    dt = datetime.strptime(dtposted[:8], "%Y%m%d").date()
                except Exception:
                    dt = None
                # Parse amount
                try:
                    amt = float(trnamt)
                except Exception:
                    amt = None
                with conn.cursor() as cur:
                    cur.execute(f"""
                        INSERT INTO {STAGING_TABLE} (file_name, trntype, dtposted, trnamt, fitid, name, memo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (fname, trntype, dt, amt, fitid, name, memo))
        print(f"Extracted: {fname}")
    conn.commit()

def match_staging_to_almsdata(conn):
    with conn.cursor() as cur:
        # Try to match by date and amount to payments table
        cur.execute(f"""
            SELECT s.id, s.dtposted, s.trnamt, s.name, s.memo,
                   p.payment_id, p.payment_date, p.amount, p.notes
            FROM {STAGING_TABLE} s
            LEFT JOIN payments p
              ON s.dtposted = p.payment_date AND s.trnamt = p.amount
        """)
        results = cur.fetchall()
        missing = [r for r in results if r[5] is None]
        funky = [r for r in results if r[5] is not None and (abs(r[2] - r[7]) > 0.01 or (r[3] and r[8] and r[3] != r[8]))]
        print(f"Total transactions: {len(results)}")
        print(f"Missing in almsdata: {len(missing)}")
        print(f"Potential mismatches: {len(funky)}")
        # Save report
        with open("l:/limo/reports/qbo_staging_discrepancies.csv", "w", encoding="utf-8") as f:
            f.write("id,dtposted,trnamt,name,memo,payment_id,payment_date,amount,notes\n")
            for r in missing:
                f.write(",".join([str(x) if x is not None else "" for x in r]) + "\n")
            for r in funky:
                f.write(",".join([str(x) if x is not None else "" for x in r]) + "\n")
        print("Discrepancy report saved to reports/qbo_staging_discrepancies.csv")

def main():
    conn = connect_db()
    extract_qbo_files_to_staging(conn)
    match_staging_to_almsdata(conn)
    conn.close()

if __name__ == "__main__":
    main()
