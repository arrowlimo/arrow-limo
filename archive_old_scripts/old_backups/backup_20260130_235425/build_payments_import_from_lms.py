import os
import csv
import argparse
from collections import defaultdict

try:
    import pyodbc
except ImportError as e:
    pyodbc = None


def read_overrides(path):
    overrides = []
    if not path or not os.path.exists(path):
        return overrides
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys
            o = {
                "reference_number": (row.get("reference_number") or "").strip(),
                "payment_id": (row.get("payment_id") or "").strip(),
                "reserve_number": (row.get("reserve_number") or "").strip(),
                "allocated_amount": row.get("allocated_amount"),
                "classification": (row.get("classification") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            }
            if o["allocated_amount"] is not None and o["allocated_amount"] != "":
                try:
                    o["allocated_amount"] = float(o["allocated_amount"]) 
                except Exception:
                    o["allocated_amount"] = None
            overrides.append(o)
    return overrides


def fetch_lms_payments(mdb_path):
    if pyodbc is None:
        raise RuntimeError("pyodbc is required to read LMS .mdb; please install it.")
    conn = pyodbc.connect(rf'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};')
    cur = conn.cursor()
    # Minimal fields; adjust if schema includes more
    cur.execute("SELECT PaymentID, Reserve_No, Amount FROM Payment ORDER BY PaymentID")
    rows = []
    for r in cur.fetchall():
        payment_id = str(r[0]).strip() if r[0] is not None else ""
        reserve = str(r[1]).strip() if r[1] is not None else ""
        amount = float(r[2] or 0)
        rows.append({"payment_id": payment_id, "reserve_number": reserve, "amount": amount})
    cur.close()
    conn.close()
    return rows


def build_proposed_import(lms_rows, overrides, include_liabilities=True):
    # Index overrides by (payment_id, reference_number)
    by_key = defaultdict(list)
    for o in overrides:
        key = (o.get("payment_id") or "", o.get("reference_number") or "")
        by_key[key].append(o)

    proposed = []
    summary = {
        "total_lms_payments": len(lms_rows),
        "total_lms_amount": sum(r["amount"] for r in lms_rows),
        "overrides_rows": len(overrides),
        "split_groups": 0,
        "liability_rows": 0,
        "manual_repairs": 0,
    }

    for r in lms_rows:
        payment_id = r["payment_id"]
        # Default reference if none provided in overrides
        default_ref = f"LMS-Payment-{payment_id}" if payment_id else "LMS-Payment"
        key_candidates = [(payment_id, default_ref)]

        # If any overrides reference this payment_id (regardless of reference_number), collect all
        override_hits = []
        for (pid, ref), vals in by_key.items():
            if pid == payment_id:
                override_hits.extend([(ref, v) for v in vals])

        if override_hits:
            # Group by reference_number for split detection
            grouped = defaultdict(list)
            for ref, v in override_hits:
                grouped[ref].append(v)
            summary["split_groups"] += sum(1 for _ in grouped)
            for ref_num, rows in grouped.items():
                for v in rows:
                    classification = (v.get("classification") or "").lower()
                    reserve_number = v.get("reserve_number") or ""
                    allocated_amount = v.get("allocated_amount")
                    notes = v.get("notes") or ""

                    if classification == "deposit_liability":
                        if not include_liabilities:
                            continue
                        summary["liability_rows"] += 1
                        proposed.append({
                            "reserve_number": "",
                            "amount": allocated_amount if allocated_amount is not None else r["amount"],
                            "payment_method": "unknown",
                            "reference_number": ref_num or default_ref,
                            "classification": "deposit_liability",
                            "notes": notes or "Unused non-refundable deposit",
                        })
                    elif classification in ("manual_repair", "trade_of_services", "charity", "multi_charter_split"):
                        if classification == "manual_repair":
                            summary["manual_repairs"] += 1
                        proposed.append({
                            "reserve_number": reserve_number,
                            "amount": allocated_amount if allocated_amount is not None else r["amount"],
                            "payment_method": "trade_of_services" if classification == "trade_of_services" else "unknown",
                            "reference_number": ref_num or default_ref,
                            "classification": classification,
                            "notes": notes,
                        })
                    else:
                        # Unknown classification: fall back to LMS single-row mapping
                        proposed.append({
                            "reserve_number": r["reserve_number"],
                            "amount": r["amount"],
                            "payment_method": "unknown",
                            "reference_number": ref_num or default_ref,
                            "classification": "",
                            "notes": notes,
                        })
        else:
            # No overrides — single charter payment mapping
            proposed.append({
                "reserve_number": r["reserve_number"],
                "amount": r["amount"],
                "payment_method": "unknown",
                "reference_number": default_ref,
                "classification": "",
                "notes": "",
            })

    return proposed, summary


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "reserve_number",
        "amount",
        "payment_method",
        "reference_number",
        "classification",
        "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    parser = argparse.ArgumentParser(description="Build proposed ALMS payments import from LMS with overrides (dry-run)")
    parser.add_argument("--lms-mdb", default=r"L:\\limo\\backups\\lms.mdb", help="Path to LMS .mdb/.accdb file")
    parser.add_argument("--overrides", default=r"L:\\limo\\data\\payment_overrides.csv", help="CSV overrides file path")
    parser.add_argument("--out", default=r"L:\\limo\\reports\\PROPOSED_ALMS_PAYMENTS_IMPORT.csv", help="Output CSV path")
    parser.add_argument("--exclude-liabilities", action="store_true", help="Exclude deposit_liability rows from proposed output")
    args = parser.parse_args()

    overrides = read_overrides(args.overrides)
    lms_rows = fetch_lms_payments(args.lms_mdb)
    proposed, summary = build_proposed_import(lms_rows, overrides, include_liabilities=not args.exclude_liabilities)
    write_csv(args.out, proposed)

    print("Proposed import written:", args.out)
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"  proposed_rows: {len(proposed)}")


if __name__ == "__main__":
    main()
