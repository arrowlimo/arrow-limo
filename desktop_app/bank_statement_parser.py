"""CIBC bank statement parser.

CIBC exports a headerless 4-column CSV::

    2019-12-31,Branch Transaction ACC FEE- FULL SERV,25.00,
    2019-12-04,Automated Banking Machine ABM DEPOSIT ...,,600.00

Columns are ``date, description, debit, credit``. Exactly one of debit/credit
is populated per row. The file carries **no account number and no header**, so
the owning account comes from the filename (``1615jan2026.xls``) or from an
explicit caller choice -- never guessed from the contents.

Duplicate handling is occurrence-aware: a bank statement can legitimately
contain the same date/description/amount more than once (three identical ABM
withdrawals in one day is real), so each row is hashed with its occurrence
index and compared against the count already stored.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

logger = logging.getLogger(__name__)

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y")

# Trailing card fragment CIBC appends, e.g. "4506*********534".
CARD_RE = re.compile(r"(\d{4})\*+(\d{3,4})\s*$")


class StatementParseError(Exception):
    """Raised when a statement file cannot be interpreted."""


@dataclass
class StatementRow:
    transaction_date: date
    description: str
    debit_amount: Decimal | None
    credit_amount: Decimal | None
    occurrence: int = 1
    card_last4: str | None = None
    row_number: int = 0

    @property
    def signed_amount(self) -> Decimal:
        return (self.credit_amount or Decimal("0")) - (
            self.debit_amount or Decimal("0")
        )


@dataclass
class ParsedStatement:
    path: Path
    rows: list[StatementRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def min_date(self):
        return min((r.transaction_date for r in self.rows), default=None)

    @property
    def max_date(self):
        return max((r.transaction_date for r in self.rows), default=None)

    def months(self):
        return sorted({(r.transaction_date.year, r.transaction_date.month)
                       for r in self.rows})


def _cell_text(cell) -> str:
    """Render an Excel cell as text the CSV-oriented parsers understand.

    Excel stores dates as native datetimes and amounts as floats; ``str()``
    would produce ``2026-01-05 00:00:00`` and ``100.49999999`` respectively,
    neither of which the date/amount parsers accept.
    """
    if isinstance(cell, datetime):
        return cell.date().isoformat()
    if isinstance(cell, date):
        return cell.isoformat()
    if isinstance(cell, bool):
        return ""
    if isinstance(cell, float):
        return f"{Decimal(str(cell)):f}"
    return str(cell)


def _parse_date(value: str):
    text = (value or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(value: str):
    """Parse an amount, tolerating ``$``, thousands separators and ``(123)``."""
    text = (value or "").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if negative:
        amount = -amount
    return amount


def _extract_card(description: str):
    match = CARD_RE.search(description or "")
    return match.group(2)[-4:] if match else None


def _iter_raw_rows(path: Path):
    """Yield raw cell lists from a CSV or Excel statement."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            for row in csv.reader(handle, dialect):
                yield row
        return

    if suffix in {".xls", ".xlsx", ".xlsm"}:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise StatementParseError(
                "Reading Excel statements requires openpyxl."
            ) from exc
        if suffix == ".xls":
            raise StatementParseError(
                "Legacy .xls is not supported. Re-save the download as .xlsx "
                "or .csv, which is what CIBC/TD/ATB offer directly."
            )
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for row in workbook[workbook.sheetnames[0]].iter_rows(values_only=True):
                yield ["" if cell is None else _cell_text(cell) for cell in row]
        finally:
            workbook.close()
        return

    raise StatementParseError(f"Unsupported statement format: {path.suffix}")


def parse_statement(path) -> ParsedStatement:
    """Parse a CIBC-style statement export into normalized rows."""
    path = Path(path)
    if not path.is_file():
        raise StatementParseError(f"File not found: {path}")

    result = ParsedStatement(path=path)
    seen = Counter()

    for index, raw in enumerate(_iter_raw_rows(path), start=1):
        cells = [(c or "").strip() for c in raw]
        if not any(cells):
            continue

        transaction_date = _parse_date(cells[0] if cells else "")
        if transaction_date is None:
            # Header or preamble line; skip quietly on the first row, warn after.
            if index > 1 and len(cells) > 1:
                result.warnings.append(f"Row {index}: unrecognized date {cells[0]!r}")
            continue

        if len(cells) < 3:
            result.warnings.append(f"Row {index}: expected at least 3 columns")
            continue

        description = cells[1]
        debit = _parse_amount(cells[2]) if len(cells) > 2 else None
        credit = _parse_amount(cells[3]) if len(cells) > 3 else None

        if debit is None and credit is None:
            result.warnings.append(f"Row {index}: no debit or credit amount")
            continue
        if debit is not None and credit is not None:
            result.warnings.append(
                f"Row {index}: both debit and credit populated; treating as credit"
            )
            debit = None

        key = (transaction_date, description, debit, credit)
        seen[key] += 1

        result.rows.append(
            StatementRow(
                transaction_date=transaction_date,
                description=description,
                debit_amount=debit,
                credit_amount=credit,
                occurrence=seen[key],
                card_last4=_extract_card(description),
                row_number=index,
            )
        )

    if not result.rows:
        raise StatementParseError(
            f"No transactions found in {path.name}. "
            "Check this is a bank statement export."
        )
    return result


def row_hash(account_number: str, row: StatementRow) -> str:
    """Stable identity for one statement line, including its occurrence.

    Occurrence is part of the hash so three identical same-day withdrawals
    produce three distinct hashes and are not collapsed into one.
    """
    debit = "" if row.debit_amount is None else f"{row.debit_amount:.2f}"
    credit = "" if row.credit_amount is None else f"{row.credit_amount:.2f}"
    payload = "|".join(
        [
            str(account_number),
            row.transaction_date.isoformat(),
            " ".join((row.description or "").split()),
            debit,
            credit,
            str(row.occurrence),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_rows(conn, account_number: str, statement: ParsedStatement):
    """Split parsed rows into new vs already-imported.

    Matching runs in two passes:

    1. Exact natural key (date + description + amounts), counted by occurrence
       so a statement re-downloaded with one extra transaction imports only
       that transaction.
    2. Date + amounts only, ignoring description. Descriptions of already
       imported rows are frequently hand-edited (the bank's
       "Branch Transaction WITHDRAWAL ..." becomes "PETTY CASH FUNDING"), so
       without this pass those rows would be re-imported as duplicates.

    Rows matched only by the second pass are returned as ``likely_duplicates``
    for review rather than being silently imported or silently skipped.
    """
    if not statement.rows:
        return [], [], []

    start = statement.min_date
    end = statement.max_date

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT transaction_date, description, debit_amount, credit_amount
              FROM banking_transactions
             WHERE account_number = %s
               AND transaction_date BETWEEN %s AND %s
            """,
            (account_number, start, end),
        )
        stored = cur.fetchall()

    exact_pool = Counter(
        (row[0], " ".join((row[1] or "").split()), row[2], row[3]) for row in stored
    )
    amount_pool = Counter((row[0], row[2], row[3]) for row in stored)

    new_rows, duplicate_rows, likely_duplicates = [], [], []

    # Pass 1: exact matches consume from both pools.
    pending = []
    for row in statement.rows:
        key = (
            row.transaction_date,
            " ".join((row.description or "").split()),
            row.debit_amount,
            row.credit_amount,
        )
        if exact_pool[key] > 0:
            exact_pool[key] -= 1
            amount_pool[(row.transaction_date, row.debit_amount,
                         row.credit_amount)] -= 1
            duplicate_rows.append(row)
        else:
            pending.append(row)

    # Pass 2: remaining rows matched on amount alone are probable renames.
    for row in pending:
        amount_key = (row.transaction_date, row.debit_amount, row.credit_amount)
        if amount_pool[amount_key] > 0:
            amount_pool[amount_key] -= 1
            likely_duplicates.append(row)
        else:
            new_rows.append(row)

    return new_rows, duplicate_rows, likely_duplicates


def import_rows(conn, account_number: str, bank_id: int,
                statement: ParsedStatement, rows, import_batch: str,
                commit: bool = True) -> int:
    """Insert the given statement rows. Returns the number inserted."""
    if not rows:
        return 0

    payload = [
        (
            account_number,
            row.transaction_date,
            row.description,
            row.debit_amount,
            row.credit_amount,
            row.card_last4,
            statement.path.name,
            import_batch,
            bank_id,
            row_hash(account_number, row),
        )
        for row in rows
    ]

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO banking_transactions (
                account_number, transaction_date, description,
                debit_amount, credit_amount, card_last4_detected,
                source_file, import_batch, bank_id, transaction_hash,
                created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            """,
            payload,
        )
        inserted = cur.rowcount

    if commit:
        conn.commit()
    logger.info(
        "Imported %d transaction(s) for account %s from %s",
        len(payload), account_number, statement.path.name,
    )
    return inserted if inserted and inserted > 0 else len(payload)


def make_batch_name(account_number: str, statement: ParsedStatement) -> str:
    """Traceable import batch label, e.g. ``1615_2019-01-03_2019-12-31_stmt``."""
    return (
        f"{account_number}_{statement.min_date}_{statement.max_date}_stmt"
    )


__all__ = [
    "ParsedStatement",
    "StatementParseError",
    "StatementRow",
    "classify_rows",
    "import_rows",
    "make_batch_name",
    "parse_statement",
    "row_hash",
]
