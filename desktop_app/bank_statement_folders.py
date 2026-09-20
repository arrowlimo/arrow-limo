"""Bank statement import folder layout.

The app creates one parent folder per institution and then waits for the admin
to drop downloaded statement files in, named ``<last4><mon><year>.xls``::

    Y:\\limo\\bankaccount\\
        CIBC\\
            1615jan2026.xls
            8362jan2026.xlsx
        TD\\
            1234jan2026.xls
        ATB\\
            5678jan2026.csv

Institution folders are derived from the ``bank_accounts`` registry, so newly
registered accounts pick up folders automatically. A same-named subfolder is
also accepted, so ``CIBC\\1615jan2026\\statement.xls`` works too.

Root location resolves in this order:
    1. ``ARROW_BANK_STATEMENTS_DIR`` environment variable
    2. QSettings("ArrowLimo", "Desktop") -> "banking/statements_dir"
    3. ``Y:\\limo\\bankaccount`` (default)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from bank_statement_parser import StatementParseError, parse_statement

logger = logging.getLogger(__name__)

ENV_VAR = "ARROW_BANK_STATEMENTS_DIR"
SETTINGS_KEY = "banking/statements_dir"
DEFAULT_ROOT = Path(r"Y:\limo\bankaccount")

MONTH_ABBR = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]

# e.g. "1615jan2026", "8362jan26"
FOLDER_RE = re.compile(
    r"^(?P<last4>\d{3,4})(?P<month>" + "|".join(MONTH_ABBR) + r")(?P<year>\d{4}|\d{2})$",
    re.IGNORECASE,
)

INSTITUTION_SLUGS = {
    "canadian imperial bank of commerce": "CIBC",
    "cibc": "CIBC",
    "bank of nova scotia": "Scotiabank",
    "scotiabank": "Scotiabank",
    "toronto-dominion bank": "TD",
    "toronto dominion bank": "TD",
    "td canada trust": "TD",
    "td": "TD",
    "alberta treasury branches": "ATB",
    "atb financial": "ATB",
    "atb": "ATB",
}


def institution_slug(institution_name: str) -> str:
    """Short, stable folder name for an institution (CIBC, TD, ATB...)."""
    name = (institution_name or "").lower()
    for key, slug in INSTITUTION_SLUGS.items():
        if key in name:
            return slug
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", institution_name or "").strip("_")
    return cleaned or "unknown"


def account_last4(account_number: str) -> str:
    """Last 4 digits, which is how the admin names statement folders."""
    digits = re.sub(r"\D", "", account_number or "")
    return digits[-4:] if len(digits) >= 4 else (digits or "xxxx")


def statement_name(account_number: str, year: int, month: int,
                   suffix: str = "") -> str:
    """Build a statement name such as ``1615jan2026`` (or ``1615jan2026.xls``)."""
    base = f"{account_last4(account_number)}{MONTH_ABBR[month - 1]}{year}"
    return f"{base}{suffix}" if suffix else base


# Backwards-compatible alias: the naming scheme is shared by files and folders.
month_folder_name = statement_name


def parse_statement_name(name: str):
    """Parse ``1615jan2026`` -> ``("1615", 2026, 1)``. Returns None if unmatched.

    Two-digit years are interpreted as 2000-2099, matching how the admin
    abbreviates (``jan26`` means 2026). Pass a filename stem, not the suffix.
    """
    match = FOLDER_RE.match((name or "").strip())
    if not match:
        return None
    year = int(match.group("year"))
    if year < 100:
        year += 2000
    month = MONTH_ABBR.index(match.group("month").lower()) + 1
    return match.group("last4"), year, month


parse_month_folder = parse_statement_name


@dataclass(frozen=True)
class AccountPaths:
    bank_id: int
    institution: str
    account_number: str
    account_name: str
    last4: str
    institution_dir: Path

    def month_dir(self, year: int, month: int) -> Path:
        return self.institution_dir / statement_name(self.account_number, year, month)


def get_statements_root(settings=None) -> Path:
    """Resolve the statement root directory for this machine."""
    env_value = os.environ.get(ENV_VAR)
    if env_value:
        return Path(env_value).expanduser()

    if settings is None:
        try:
            from PyQt6.QtCore import QSettings

            settings = QSettings("ArrowLimo", "Desktop")
        except Exception:  # pragma: no cover - non-GUI contexts
            settings = None

    if settings is not None:
        try:
            configured = settings.value(SETTINGS_KEY, "", type=str)
        except Exception:
            configured = ""
        if configured:
            return Path(configured).expanduser()

    return DEFAULT_ROOT


def set_statements_root(path, settings=None) -> Path:
    """Persist a user-selected statement root."""
    resolved = Path(path).expanduser()
    if settings is None:
        from PyQt6.QtCore import QSettings

        settings = QSettings("ArrowLimo", "Desktop")
    settings.setValue(SETTINGS_KEY, str(resolved))
    return resolved


def fetch_accounts(conn, include_inactive: bool = False):
    """Read the account registry. Closed accounts are skipped by default."""
    query = """
        SELECT bank_id, institution_name, account_number, account_name
          FROM bank_accounts
         {where}
         ORDER BY institution_name, account_number
    """.format(where="" if include_inactive else "WHERE is_active IS TRUE")
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def plan_accounts(conn, root=None, include_inactive: bool = False):
    """Compute per-account paths without touching the filesystem."""
    base = Path(root) if root is not None else get_statements_root()
    accounts = []
    for bank_id, institution, account_number, account_name in fetch_accounts(
        conn, include_inactive
    ):
        accounts.append(
            AccountPaths(
                bank_id=bank_id,
                institution=institution,
                account_number=account_number,
                account_name=account_name,
                last4=account_last4(account_number),
                institution_dir=base / institution_slug(institution),
            )
        )
    return base, accounts


def ensure_folders(conn, root=None, include_inactive: bool = False):
    """Create the institution parent folders if missing. Safe to re-run.

    Only the institution level is created; the admin drops statement files in
    directly, so there is nothing further to scaffold.
    """
    base, accounts = plan_accounts(conn, root, include_inactive)
    created = []

    for path in [base] + [a.institution_dir for a in accounts]:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    if created:
        logger.info("Created %d bank statement folder(s) under %s", len(created), base)
    return base, accounts, created


STATEMENT_SUFFIXES = {".xls", ".xlsx", ".csv", ".ofx", ".qfx", ".pdf", ".txt"}


def scan_statements(conn, root=None, include_inactive: bool = False):
    """Find downloaded statements and report what the admin has provided.

    Accepts either a file (``1615jan2026.xls``) or a same-named subfolder
    (``1615jan2026\\anything.xls``) directly under the institution folder.

    Returns ``(base, accounts, found, unknown)`` where ``found`` maps
    ``bank_id`` to a sorted list of ``(year, month, path, size_bytes)`` and
    ``unknown`` lists entries matching no registered account.
    """
    base, accounts = plan_accounts(conn, root, include_inactive)

    by_last4 = {}
    for account in accounts:
        by_last4.setdefault(account.last4, account)

    found = {account.bank_id: [] for account in accounts}
    unknown = []
    scanned = set()

    for account in accounts:
        directory = account.institution_dir
        if not directory.is_dir() or directory in scanned:
            continue
        scanned.add(directory)

        for child in sorted(directory.iterdir()):
            if child.is_file() and child.suffix.lower() not in STATEMENT_SUFFIXES:
                continue

            parsed = parse_statement_name(child.stem if child.is_file() else child.name)
            owner = by_last4.get(parsed[0]) if parsed else None
            if owner is None:
                unknown.append(child)
                continue

            _last4, year, month = parsed
            if child.is_file():
                statement_path = child
                size = child.stat().st_size
            else:
                files = [
                    f for f in child.iterdir()
                    if f.is_file() and f.suffix.lower() in STATEMENT_SUFFIXES
                ]
                if len(files) != 1:
                    # Empty or ambiguous folders cannot be imported safely.
                    unknown.append(child)
                    continue
                statement_path = files[0]
                size = statement_path.stat().st_size
            covered_months = [(year, month)]
            if statement_path.suffix.lower() in {".csv", ".txt", ".xlsx", ".xlsm"}:
                try:
                    covered_months = parse_statement(statement_path).months()
                except (StatementParseError, OSError) as exc:
                    logger.warning(
                        "Could not inspect statement months for %s: %s",
                        statement_path,
                        exc,
                    )
            for covered_year, covered_month in covered_months:
                found[owner.bank_id].append(
                    (covered_year, covered_month, statement_path, size)
                )

    for bank_id in found:
        found[bank_id].sort(key=lambda entry: (entry[0], entry[1]))
    return base, accounts, found, unknown


def _month_range(start: date, end: date):
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            month, year = 1, year + 1


def last_complete_month(today: date | None = None) -> date:
    """First day of the most recently completed month."""
    today = today or date.today()
    return (date(today.year, today.month, 1) - timedelta(days=1)).replace(day=1)


def missing_months(conn, root=None, through: date | None = None,
                   include_inactive: bool = False):
    """Report months with no downloaded statement, per account.

    The window runs from the month of the account's last imported transaction
    through ``through`` (default: last complete month), so it answers "what
    still needs downloading" rather than flagging all history.
    """
    if through is None:
        through = last_complete_month()

    base, accounts, found, unknown = scan_statements(conn, root, include_inactive)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bank_id, max(transaction_date)
              FROM banking_transactions
             WHERE bank_id IS NOT NULL
             GROUP BY bank_id
            """
        )
        last_txn = dict(cur.fetchall())

    report = {}
    for account in accounts:
        latest = last_txn.get(account.bank_id)
        if latest is None:
            report[account.bank_id] = []
            continue
        # Re-check the month of the last transaction: a partial month may still
        # be missing its remaining statements.
        start = date(latest.year, latest.month, 1)
        have = {(y, m) for y, m, _path, _n in found.get(account.bank_id, [])}
        report[account.bank_id] = [
            (y, m) for y, m in _month_range(start, through) if (y, m) not in have
        ]
    return base, accounts, found, report, unknown


def describe_layout(conn, root=None, include_inactive: bool = False) -> str:
    """Human-readable summary of expected statements and what is present."""
    base, accounts, found, report, unknown = missing_months(
        conn, root, include_inactive=include_inactive
    )
    lines = [str(base)]
    current = None
    for account in accounts:
        slug = institution_slug(account.institution)
        if slug != current:
            marker = "" if account.institution_dir.exists() else "   (missing)"
            lines.append(f"  {slug}\\{marker}")
            current = slug
        downloaded = found.get(account.bank_id, [])
        missing = report.get(account.bank_id, [])
        example = statement_name(account.account_number, 2026, 1, ".xls")
        lines.append(
            f"    {account.last4}  ({account.account_name}) "
            f"e.g. {example}  downloaded={len(downloaded)} missing={len(missing)}"
        )
        for year, month in missing[:6]:
            lines.append(
                "        needs "
                + statement_name(account.account_number, year, month, ".xls")
            )
        if len(missing) > 6:
            lines.append(f"        ... and {len(missing) - 6} more")
    for path in unknown:
        lines.append(f"  ?? unrecognized: {path}")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_ROOT",
    "ENV_VAR",
    "SETTINGS_KEY",
    "STATEMENT_SUFFIXES",
    "AccountPaths",
    "account_last4",
    "describe_layout",
    "ensure_folders",
    "get_statements_root",
    "institution_slug",
    "last_complete_month",
    "missing_months",
    "month_folder_name",
    "parse_month_folder",
    "parse_statement_name",
    "plan_accounts",
    "scan_statements",
    "set_statements_root",
    "statement_name",
]
