"""Bank statement import folder layout.

Resolves where downloaded bank statements live on the machine running the app
and scaffolds one folder per active account in ``bank_accounts``.

Location is resolved in this order:
    1. ``ARROW_BANK_STATEMENTS_DIR`` environment variable
    2. QSettings("ArrowLimo", "Desktop") -> "banking/statements_dir"
    3. ``~/Documents/Arrow_Limousine_Bank_Statements`` (default)

Folders are derived from the account registry rather than hardcoded, so newly
registered accounts (e.g. TD, ATB) get folders automatically.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_VAR = "ARROW_BANK_STATEMENTS_DIR"
SETTINGS_KEY = "banking/statements_dir"
DEFAULT_DIR_NAME = "Arrow_Limousine_Bank_Statements"

# Downloaded statements are dropped here; the importer moves them out once
# committed so a folder that is not empty always means "work pending".
INBOX_SUBDIR = "_inbox"
PROCESSED_SUBDIR = "_processed"
REJECTED_SUBDIR = "_rejected"

README_TEXT = """Arrow Limousine - Bank Statement Import
=======================================

Put each downloaded statement in the matching account's {inbox} folder.

Banks only let you download one month at a time, so download month by month.
Name files however your bank produces them; the importer reads the account and
the real date range from inside the file and uses the filename only as a hint.
If the two disagree the file is rejected rather than imported into the wrong
account.

After an import:
  {inbox}     files still waiting to be reviewed and committed
  {processed} files already committed to the database
  {rejected}  files that could not be matched to this account

Folders are generated from the account registry. If an account is missing here,
it has not been registered in the database yet.
"""


def _slugify(value: str) -> str:
    """Make a string safe to use as a folder name."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_")
    return cleaned or "unknown"


def _institution_slug(institution_name: str) -> str:
    """Short, stable folder name for an institution."""
    name = (institution_name or "").lower()
    known = {
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
    for key, slug in known.items():
        if key in name:
            return slug
    return _slugify(institution_name)


def account_folder_name(account_number: str, account_name: str) -> str:
    """Folder name for one account, e.g. ``8362_Business_Checking``.

    Uses the last 4 digits, which is how the admin identifies accounts, but
    keeps the descriptive name so folders are not just opaque numbers.
    """
    digits = re.sub(r"\D", "", account_number or "")
    last4 = digits[-4:] if len(digits) >= 4 else (digits or "xxxx")

    label = account_name or ""
    # Drop a leading institution prefix so folders don't read "CIBC/CIBC_...".
    label = re.sub(
        r"^(CIBC|Scotiabank|TD|ATB)\b[\s\-]*", "", label, flags=re.IGNORECASE
    )
    label = re.sub(r"\((?:Legacy|Historical)[^)]*\)", "", label, flags=re.IGNORECASE)
    return f"{last4}_{_slugify(label)}".rstrip("_")


@dataclass(frozen=True)
class AccountFolder:
    bank_id: int
    institution: str
    account_number: str
    account_name: str
    path: Path

    @property
    def inbox(self) -> Path:
        return self.path / INBOX_SUBDIR

    @property
    def processed(self) -> Path:
        return self.path / PROCESSED_SUBDIR

    @property
    def rejected(self) -> Path:
        return self.path / REJECTED_SUBDIR


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

    return Path.home() / "Documents" / DEFAULT_DIR_NAME


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


def plan_folders(conn, root=None, include_inactive: bool = False):
    """Compute the folder layout without touching the filesystem."""
    base = Path(root) if root is not None else get_statements_root()
    folders = []
    for bank_id, institution, account_number, account_name in fetch_accounts(
        conn, include_inactive
    ):
        path = (
            base
            / _institution_slug(institution)
            / account_folder_name(account_number, account_name)
        )
        folders.append(
            AccountFolder(
                bank_id=bank_id,
                institution=institution,
                account_number=account_number,
                account_name=account_name,
                path=path,
            )
        )
    return base, folders


def ensure_folders(conn, root=None, include_inactive: bool = False):
    """Create the statement folder tree if missing. Safe to re-run."""
    base, folders = plan_folders(conn, root, include_inactive)
    created = []

    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        created.append(base)

    readme = base / "README.txt"
    if not readme.exists():
        readme.write_text(
            README_TEXT.format(
                inbox=INBOX_SUBDIR,
                processed=PROCESSED_SUBDIR,
                rejected=REJECTED_SUBDIR,
            ),
            encoding="utf-8",
        )

    for folder in folders:
        for path in (folder.inbox, folder.processed, folder.rejected):
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created.append(path)

    if created:
        logger.info("Created %d bank statement folder(s) under %s", len(created), base)
    return base, folders, created


def describe_layout(conn, root=None, include_inactive: bool = False) -> str:
    """Human-readable tree, for showing the admin where files go."""
    base, folders = plan_folders(conn, root, include_inactive)
    lines = [str(base)]
    current_institution = None
    for folder in folders:
        institution = _institution_slug(folder.institution)
        if institution != current_institution:
            lines.append(f"  {institution}/")
            current_institution = institution
        exists = "" if folder.path.exists() else "   (missing)"
        lines.append(f"    {folder.path.name}/{INBOX_SUBDIR}/{exists}")
    return "\n".join(lines)
