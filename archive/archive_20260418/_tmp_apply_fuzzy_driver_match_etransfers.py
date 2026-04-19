import csv
import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2

DRY_RUN = False
OUT_CSV = Path(r"l:\limo\data\intake\etransfer_fuzzy_driver_matches.csv")
MIN_CONFIDENCE = 0.86
MIN_GAP = 0.06

BLOCK_TOKENS = {
    "HEFFNER",
    "INSURANCE",
    "AUTO",
    "SALES",
    "LEASING",
    "LIQUOR",
    "MONEY MART",
    "FORD",
    "HUT",
    "TRACTOR",
    "FIBRENEW",
    "SQ",
    "LEXUS",
    "RESTAURANT",
    "HOT TUB",
}

# User-provided typo tolerance, plus common short forms.
FORCED_NAME_ALIASES = {
    "JEANNIE": "SHILLINGTON, JEANNIE",
    "JENNEE": "SHILLINGTON, JEANNIE",
    "JEANY": "SHILLINGTON, JEANNIE",
    "JENNY": "SHILLINGTON, JEANNIE",
    "JENNIE": "SHILLINGTON, JEANNIE",
}

NAME_PATTERNS = [
    re.compile(
        r"(?:INTERNET\s+BANKING\s+)?(?:E-TRANSFER|ETRANSFER|EMAIL\s+TRANSFER)\s*[0-9\-* ]{0,30}\s*([A-Za-z][A-Za-z .,'-]{2,80}?)(?:\s+4506\*|\s+4506|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:E-TRANSFER|ETRANSFER|EMAIL\s+TRANSFER)\s+TO\s+([A-Za-z][A-Za-z .,'-]{2,80}?)(?:\s+ID|\s*$)",
        re.IGNORECASE,
    ),
]


@dataclass
class Employee:
    employee_id: int
    display_name: str
    aliases: List[str]
    alias_tokens: List[List[str]]


def norm_text(s: str) -> str:
    s = (s or "").upper().replace(",", " ")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def token_sort_key(s: str) -> str:
    toks = [t for t in norm_text(s).split() if t]
    toks.sort()
    return " ".join(toks)


def parse_employee_name(full_name: str) -> Tuple[str, str]:
    raw = (full_name or "").strip()
    if "," in raw:
        last, first = [x.strip() for x in raw.split(",", 1)]
    else:
        parts = raw.split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
        elif len(parts) == 1:
            first, last = parts[0], ""
        else:
            first, last = "", ""
    return first, last


def employee_aliases(display_name: str) -> List[str]:
    first, last = parse_employee_name(display_name)
    aliases = {display_name}
    if first and last:
        aliases.add(f"{first} {last}")
        aliases.add(f"{last} {first}")
        aliases.add(last)
        aliases.add(first)
    elif first:
        aliases.add(first)
    return [a for a in aliases if a.strip()]


def load_employees(cur) -> List[Employee]:
    cur.execute(
        """
        SELECT employee_id,
               COALESCE(NULLIF(full_name, ''),
                        NULLIF(TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')), ''),
                        NULLIF(name, ''),
                        'EMPLOYEE ' || employee_id::text) AS display_name
        FROM employees
        ORDER BY employee_id
        """
    )
    rows = cur.fetchall()

    emps: List[Employee] = []
    by_display: Dict[str, Employee] = {}
    for emp_id, nm in rows:
        aliases = employee_aliases(nm)
        norm_aliases = sorted({norm_text(a) for a in aliases if norm_text(a)})
        emp = Employee(
            employee_id=emp_id,
            display_name=nm,
            aliases=norm_aliases,
            alias_tokens=[a.split() for a in norm_aliases],
        )
        emps.append(emp)
        by_display[norm_text(nm)] = emp

    for alias, target in FORCED_NAME_ALIASES.items():
        target_emp = by_display.get(norm_text(target))
        if target_emp:
            na = norm_text(alias)
            if na and na not in target_emp.aliases:
                target_emp.aliases.append(na)
                target_emp.alias_tokens.append(na.split())

    return emps


def load_email_name_aliases(cur, employees: List[Employee]) -> int:
    patterns = [
        re.compile(r"INTERAC\s+E-TRANSFER:\s+YOUR\s+MONEY\s+TRANSFER\s+TO\s+(.+?)\s+WAS\s+DEPOSITED", re.IGNORECASE),
        re.compile(r"INTERAC\s+E-TRANSFER:\s+(.+?)\s+SENT\s+YOU\s+MONEY", re.IGNORECASE),
        re.compile(r"INTERAC\s+E-TRANSFER:\s+(.+?)\s+ACCEPTED\s+YOUR\s+MONEY\s+TRANSFER", re.IGNORECASE),
        re.compile(r"INTERAC\s+E-TRANSFER:\s+WE\s+CANNOT\s+NOTIFY\s+(.+?)\s+ABOUT\s+YOUR\s+MONEY\s+TRANSFER", re.IGNORECASE),
    ]

    cur.execute(
        """
        SELECT subject
        FROM email_financial_events
        WHERE (subject ILIKE '%interac%' OR subject ILIKE '%e-transfer%')
          AND email_date >= CURRENT_DATE - INTERVAL '8 years'
        """
    )
    subjects = [r[0] for r in cur.fetchall() if r[0]]

    added = 0
    for subj in subjects:
        extracted = ""
        for pat in patterns:
            m = pat.search(subj)
            if m:
                extracted = norm_text(m.group(1))
                break

        if not extracted or blocked_text(extracted):
            continue

        best_emp = None
        best = 0.0
        second = 0.0
        for emp in employees:
            s = score_match(extracted, emp)
            if s > best:
                second = best
                best = s
                best_emp = emp
            elif s > second:
                second = s

        if best_emp is None:
            continue

        # Strict threshold: email alias only when very likely and not ambiguous.
        if best >= 0.91 and (best - second) >= 0.08:
            if extracted not in best_emp.aliases:
                best_emp.aliases.append(extracted)
                best_emp.alias_tokens.append(extracted.split())
                added += 1

    return added


def extract_candidate_name(description: str, vendor_extracted: Optional[str]) -> str:
    d = description or ""
    for pat in NAME_PATTERNS:
        m = pat.search(d)
        if m:
            val = norm_text(m.group(1))
            if val:
                return val

    v = norm_text(vendor_extracted or "")
    if v and not any(tok in v for tok in BLOCK_TOKENS):
        return v

    dnorm = norm_text(d)
    # Fallback: strip known prefixes and keep trailing words.
    dnorm = re.sub(r"^INTERNET BANKING\s+", "", dnorm)
    dnorm = re.sub(r"^(E TRANSFER|ETRANSFER|EMAIL TRANSFER)\s+[0-9 ]+", "", dnorm)
    dnorm = re.sub(r"\s+4506\s*\*+.*$", "", dnorm)
    dnorm = dnorm.strip()
    return dnorm


def blocked_text(s: str) -> bool:
    n = norm_text(s)
    return any(tok in n for tok in BLOCK_TOKENS)


def is_related_party_reimbursement_text(s: str) -> bool:
    n = norm_text(s)
    return ("DAVID RICHARD" in n) or ("KAREN RICHARD" in n)


def score_match(candidate: str, emp: Employee) -> float:
    c = norm_text(candidate)
    if not c:
        return 0.0

    best = 0.0
    c_sorted = token_sort_key(c)
    c_toks = c.split()
    for a, a_toks in zip(emp.aliases, emp.alias_tokens):
        ratio_raw = difflib.SequenceMatcher(None, c, a).ratio()
        ratio_sorted = difflib.SequenceMatcher(None, c_sorted, token_sort_key(a)).ratio()

        # Boost when last-name token exactly appears with close first-name token.
        overlap = len(set(c_toks) & set(a_toks))
        overlap_boost = 0.04 if overlap >= 1 else 0.0
        if len(a_toks) >= 2 and a_toks[-1] in c_toks:
            overlap_boost += 0.05

        score = max(ratio_raw, ratio_sorted) + overlap_boost
        if score > best:
            best = score
    return min(best, 0.999)


def choose_employee(candidate: str, employees: List[Employee]) -> Tuple[Optional[Employee], float, float]:
    scored = []
    for emp in employees:
        s = score_match(candidate, emp)
        if s > 0:
            scored.append((s, emp))
    if not scored:
        return None, 0.0, 0.0

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_emp = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    return best_emp, best_score, second_score


def fetch_candidates(cur):
    cur.execute(
        """
        SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted,
               reconciliation_status, is_transfer
        FROM banking_transactions
        WHERE debit_amount > 0
          AND receipt_id IS NULL
          AND reconciled_receipt_id IS NULL
          AND reconciled_payment_id IS NULL
          AND reconciled_charter_id IS NULL
          AND reconciliation_status IS DISTINCT FROM 'CASH_BOX_REVIEW'
          AND (
                description ILIKE '%e-transfer%'
                OR description ILIKE '%etransfer%'
                OR description ILIKE '%email transfer%'
              )
        ORDER BY transaction_date, transaction_id
        """
    )
    return cur.fetchall()


def main():
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine"
    )
    conn.autocommit = False
    cur = conn.cursor()

    employees = load_employees(cur)
    email_aliases_added = load_email_name_aliases(cur, employees)
    candidates = fetch_candidates(cur)

    proposed = []
    skipped_blocked = 0
    skipped_related_party = 0
    skipped_low = 0

    for tid, tdate, amt, desc, vendor, status, is_transfer in candidates:
        if is_related_party_reimbursement_text(desc or ""):
            skipped_related_party += 1
            continue

        if blocked_text(desc or ""):
            skipped_blocked += 1
            continue

        extracted = extract_candidate_name(desc or "", vendor)
        if is_related_party_reimbursement_text(extracted):
            skipped_related_party += 1
            continue

        if not extracted or blocked_text(extracted):
            skipped_blocked += 1
            continue

        emp, best, second = choose_employee(extracted, employees)
        if emp is None:
            skipped_low += 1
            continue

        if best < MIN_CONFIDENCE or (best - second) < MIN_GAP:
            skipped_low += 1
            continue

        proposed.append(
            {
                "transaction_id": tid,
                "transaction_date": str(tdate),
                "debit_amount": str(amt),
                "description": desc or "",
                "vendor_extracted": vendor or "",
                "candidate_name": extracted,
                "employee_id": emp.employee_id,
                "employee_name": emp.display_name,
                "confidence": f"{best:.4f}",
                "second_confidence": f"{second:.4f}",
                "prior_status": status or "",
                "prior_is_transfer": "true" if is_transfer else "false",
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "transaction_id",
                "transaction_date",
                "debit_amount",
                "description",
                "vendor_extracted",
                "candidate_name",
                "employee_id",
                "employee_name",
                "confidence",
                "second_confidence",
                "prior_status",
                "prior_is_transfer",
            ],
        )
        writer.writeheader()
        writer.writerows(proposed)

    print(f"CANDIDATES_TOTAL={len(candidates)}")
    print(f"EMAIL_ALIASES_ADDED={email_aliases_added}")
    print(f"PROPOSED_MATCHES={len(proposed)}")
    print(f"SKIPPED_BLOCKED={skipped_blocked}")
    print(f"SKIPPED_RELATED_PARTY={skipped_related_party}")
    print(f"SKIPPED_LOWCONF={skipped_low}")
    print(f"REPORT_CSV={OUT_CSV}")

    if proposed:
        print("TOP_MATCH_SAMPLES")
        for row in sorted(proposed, key=lambda r: float(r["confidence"]), reverse=True)[:20]:
            print(
                f"{row['transaction_id']}|{row['debit_amount']}|{row['candidate_name']}|"
                f"{row['employee_name']}|{row['confidence']}|{row['prior_status']}"
            )

    if DRY_RUN or not proposed:
        conn.rollback()
        cur.close()
        conn.close()
        print("DRY_RUN_NO_DB_UPDATE")
        return

    updated = 0
    for row in proposed:
        cur.execute(
            """
            UPDATE banking_transactions
            SET
                is_transfer = TRUE,
                category = 'DRIVER_PAY_REIMBURSEMENT',
                reconciliation_status = 'DRIVER_PAY_FUZZY',
                reconciliation_notes = COALESCE(reconciliation_notes || E'\n', '') || %s
            WHERE transaction_id = %s
              AND receipt_id IS NULL
              AND reconciled_receipt_id IS NULL
              AND reconciled_payment_id IS NULL
              AND reconciled_charter_id IS NULL
              AND reconciliation_status IS DISTINCT FROM 'CASH_BOX_REVIEW'
            """,
            (
                f"[AUTO] etransfer_fuzzy_driver_match: employee={row['employee_name']} "
                f"(id={row['employee_id']}, conf={row['confidence']})",
                int(row["transaction_id"]),
            ),
        )
        updated += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    print(f"UPDATED_ROWS={updated}")
    print("ETRANSFER_FUZZY_DRIVER_MATCH_DONE")


if __name__ == "__main__":
    main()
