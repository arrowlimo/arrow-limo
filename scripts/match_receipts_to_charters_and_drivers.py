#!/usr/bin/env python3
"""
Link payment-like receipts to charters (via reserve_number/payment matches) and
fuzzy-match driver names for reimbursements. Generates matched and unmatched reports.
"""
import os
import csv
import math
import datetime as dt
from difflib import SequenceMatcher

import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

def clean_name(name: str) -> str:
    if not name:
        return ""
    return "".join(ch for ch in name.lower() if ch.isalnum())

def best_driver_match(target: str, driver_index):
    target_clean = clean_name(target)
    if not target_clean:
        return None
    best = None
    for emp_id, variants in driver_index.items():
        for variant in variants:
            ratio = SequenceMatcher(None, target_clean, variant).ratio()
            if ratio >= 0.86:  # tolerate truncation
                if not best or ratio > best[2]:
                    best = (emp_id, variant, ratio)
    return best

def load_drivers(cur):
    cur.execute(
        """
        SELECT employee_id, COALESCE(full_name, name, legacy_name, '') AS primary,
               COALESCE(legacy_name, '') AS legacy,
               COALESCE(name, '') AS alt,
               COALESCE(driver_code, '') AS code,
               COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') AS first_last
        FROM employees
    """
    )
    index = {}
    for row in cur.fetchall():
        emp_id, primary, legacy, alt, code, first_last = row
        variants = {clean_name(v) for v in [primary, legacy, alt, code, first_last] if v}
        variants = {v for v in variants if v}
        if variants:
            index[emp_id] = variants
    return index

def load_charters(cur):
    cur.execute("SELECT charter_id, reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    return {rsv: cid for cid, rsv in cur.fetchall() if rsv}

def load_payments(cur):
    cur.execute(
        """
        SELECT payment_id, reserve_number, charter_id, amount, payment_date, payment_method, square_payment_id, square_customer_name, square_customer_email
        FROM payments
        WHERE amount IS NOT NULL
    """
    )
    rows = cur.fetchall()
    payments = []
    for pid, rsv, cid, amt, pdate, method, sq_id, sq_name, sq_email in rows:
        payments.append({
            "payment_id": pid,
            "reserve_number": rsv,
            "charter_id": cid,
            "amount": float(amt),
            "payment_date": pdate,
            "payment_method": method,
            "square_id": sq_id,
            "square_name": sq_name,
            "square_email": sq_email,
        })
    return payments

def load_candidate_receipts(cur):
    # Get ALL revenue receipts (customer payments) - zero have charter/employee links currently
    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, description, revenue, gross_amount,
               payment_method, pay_method, canonical_pay_method, source_system,
               source_reference, banking_transaction_id, reserve_number, charter_id,
               employee_id, canonical_vendor
        FROM receipts
        WHERE revenue IS NOT NULL AND revenue > 0
    """
    )
    rows = cur.fetchall()
    receipts = []
    for row in rows:
        (rid, rdate, vendor, desc, revenue, gross, pay_method, pay_method2,
         canonical_pay_method, source_system, source_ref, banking_txn_id,
         reserve_number, charter_id, employee_id, canonical_vendor) = row
        amount = revenue if revenue is not None else gross
        receipts.append({
            "receipt_id": rid,
            "receipt_date": rdate,
            "vendor_name": vendor,
            "description": desc,
            "amount": float(amount) if amount is not None else None,
            "payment_method": pay_method,
            "pay_method": pay_method2,
            "canonical_pay_method": canonical_pay_method,
            "source_system": source_system,
            "source_reference": source_ref,
            "banking_transaction_id": banking_txn_id,
            "reserve_number": reserve_number,
            "charter_id": charter_id,
            "employee_id": employee_id,
            "canonical_vendor": canonical_vendor,
        })
    return receipts

def pick_payment_match(receipt, payments):
    amount = receipt["amount"]
    rdate = receipt["receipt_date"]
    if amount is None or rdate is None:
        return None
    candidates = []
    for p in payments:
        if abs(p["amount"] - amount) <= 0.01:
            if p["payment_date"] is None:
                continue
            days = abs((rdate - p["payment_date"]).days)
            if days <= 5:
                candidates.append((days, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]["payment_id"]))
    return candidates[0][1]

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print("Loading drivers, charters, payments, and receipts...")
    driver_index = load_drivers(cur)
    charters_by_reserve = load_charters(cur)
    payments = load_payments(cur)
    receipts = load_candidate_receipts(cur)

    matched_rows = []
    unmatched_rows = []

    for r in receipts:
        match_source = None
        match_reserve = None
        match_charter = None
        match_payment_id = None
        match_payment_date = None

        # Direct reserve_number on receipt
        if r["reserve_number"] and r["reserve_number"] in charters_by_reserve:
            match_reserve = r["reserve_number"]
            match_charter = charters_by_reserve[r["reserve_number"]]
            match_source = "receipt_reserve"

        # Direct charter_id on receipt
        if not match_source and r["charter_id"]:
            match_charter = r["charter_id"]
            match_source = "receipt_charter_id"

        # Payment-based match (date + amount within 5 days)
        if not match_source:
            p = pick_payment_match(r, payments)
            if p:
                match_payment_id = p["payment_id"]
                match_payment_date = p["payment_date"]
                match_reserve = p["reserve_number"]
                match_charter = p["charter_id"]
                match_source = "payment_date_amount"

        # Driver matching: EMAIL TRANSFER - <name> or driver reimbursements
        # Look for "EMAIL TRANSFER -" or driver name patterns in vendor_name/description
        driver_match = None
        if r.get("vendor_name"):
            # Extract name after "EMAIL TRANSFER -" if present
            vendor_lower = r["vendor_name"].lower()
            if "email transfer" in vendor_lower and "-" in vendor_lower:
                # Extract part after "-" as driver name
                parts = r["vendor_name"].split("-", 1)
                if len(parts) == 2:
                    name_part = parts[1].strip()
                    driver_match = best_driver_match(name_part, driver_index)
            
            # Fall back to full vendor_name fuzzy match
            if not driver_match:
                driver_match = best_driver_match(r["vendor_name"], driver_index)
        
        # Try description if vendor didn't match
        if not driver_match and r.get("description"):
            driver_match = best_driver_match(r["description"], driver_index)
        
        driver_emp_id = driver_match[0] if driver_match else r.get("employee_id")
        driver_score = round(driver_match[2], 3) if driver_match else None

        output_row = {
            "receipt_id": r["receipt_id"],
            "receipt_date": r["receipt_date"],
            "vendor_name": r["vendor_name"],
            "description": r.get("description"),
            "amount": r["amount"],
            "source_system": r["source_system"],
            "reserve_number_matched": match_reserve,
            "charter_id_matched": match_charter,
            "match_source": match_source,
            "payment_id": match_payment_id,
            "payment_date": match_payment_date,
            "existing_employee_id": r["employee_id"],
            "driver_match_id": driver_emp_id,
            "driver_match_score": driver_score,
        }

        if match_source or driver_emp_id:
            matched_rows.append(output_row)
        else:
            unmatched_rows.append(output_row)

    matched_path = os.path.join(REPORT_DIR, "receipt_charter_driver_matches.csv")
    unmatched_path = os.path.join(REPORT_DIR, "receipt_charter_driver_unmatched.csv")

    headers = [
        "receipt_id", "receipt_date", "vendor_name", "description", "amount", "source_system",
        "reserve_number_matched", "charter_id_matched", "match_source", "payment_id", "payment_date",
        "existing_employee_id", "driver_match_id", "driver_match_score"
    ]

    with open(matched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(matched_rows)

    with open(unmatched_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(unmatched_rows)

    print(f"Matched receipts: {len(matched_rows):,}")
    print(f"Unmatched receipts: {len(unmatched_rows):,}")
    print(f"Matched report: {matched_path}")
    print(f"Unmatched report: {unmatched_path}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
