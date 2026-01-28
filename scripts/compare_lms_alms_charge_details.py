#!/usr/bin/env python3
"""
Compare LMS charges vs almsdata charges for a sample charter to understand discrepancies.
Shows exact charge line items side-by-side.
"""

import psycopg2
import pyodbc

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

LMS_PATH = r"L:\limo\backups\lms.mdb"

SAMPLE_RESERVES = ["019233", "015190", "019572", "018359", "019355"]


def get_almsdata_charges(reserve, alms_cur):
    """Get all charge lines for a reserve from almsdata."""
    alms_cur.execute("""
        SELECT charge_id, amount, description, last_updated_by, created_at
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY amount DESC
    """, (reserve,))
    
    rows = alms_cur.fetchall()
    charges = []
    for row in rows:
        charges.append({
            'id': row[0],
            'amount': float(row[1]),
            'desc': row[2] or '',
            'updated_by': row[3] or '',
            'created_at': str(row[4]) if row[4] else ''
        })
    return charges


def get_lms_charges(reserve, lms_cur):
    """Get all charge lines for a reserve from LMS."""
    charges = []
    try:
        lms_cur.execute("SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
        
        reserve_field = None
        amount_field = None
        desc_field = None
        
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
            if "desc" in cl:
                desc_field = col
        
        if not reserve_field or not amount_field:
            return charges
        
        desc_select = f"[{desc_field}]" if desc_field else "NULL"
        lms_cur.execute(
            f"SELECT [{amount_field}], {desc_select} FROM Charge WHERE [{reserve_field}] = ? ORDER BY [{amount_field}] DESC",
            (reserve,)
        )
        
        for row in lms_cur.fetchall():
            amount = float(row[0] or 0)
            desc = (str(row[1]).strip() if row[1] is not None else "") if len(row) > 1 else ""
            charges.append({
                'amount': amount,
                'desc': desc
            })
    except Exception as e:
        print(f"Error fetching LMS charges for {reserve}: {e}")
    
    return charges


def main():
    alms_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    lms_conn = pyodbc.connect(lms_conn_str)
    
    alms_cur = alms_conn.cursor()
    lms_cur = lms_conn.cursor()
    
    for reserve in SAMPLE_RESERVES:
        print("=" * 100)
        print(f"RESERVE: {reserve}")
        print("=" * 100)
        
        alms_charges = get_almsdata_charges(reserve, alms_cur)
        lms_charges = get_lms_charges(reserve, lms_cur)
        
        print(f"\nLMS Charges ({len(lms_charges)} lines):")
        print(f"{'Amount':<15} {'Description':<50}")
        print("-" * 65)
        lms_total = 0.0
        for c in lms_charges:
            print(f"${c['amount']:<14.2f} {c['desc']:<50}")
            lms_total += c['amount']
        print("-" * 65)
        print(f"LMS Total: ${lms_total:.2f}")
        
        print(f"\nalmsdata Charges ({len(alms_charges)} lines):")
        print(f"{'Amount':<15} {'Description':<50} {'Updated By':<30}")
        print("-" * 95)
        alms_total = 0.0
        for c in alms_charges:
            print(f"${c['amount']:<14.2f} {c['desc']:<50} {c['updated_by']:<30}")
            alms_total += c['amount']
        print("-" * 95)
        print(f"almsdata Total: ${alms_total:.2f}")
        
        print(f"\nDifference: ${alms_total - lms_total:.2f} (almsdata - LMS)")
        print()
    
    alms_cur.close()
    alms_conn.close()
    lms_cur.close()
    lms_conn.close()


if __name__ == "__main__":
    main()
