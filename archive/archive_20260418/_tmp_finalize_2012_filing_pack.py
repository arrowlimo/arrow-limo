from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import csv
import re

AUDIT_DIR = Path(r"l:\limo\data\audit")
CRA_DIR = Path(r"l:\limo\data\cra")
YEAR = 2012


@dataclass
class MethodResult:
    method: str
    revenue: Decimal | None
    expenses: Decimal | None
    net_income: Decimal | None
    source_file: Path
    notes: str


def parse_money(raw: str) -> Decimal:
    cleaned = raw.replace(",", "").replace("$", "").strip()
    return Decimal(cleaned)


def latest(pattern: str) -> Path:
    files = sorted(AUDIT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No files matched: {pattern}")
    return files[-1]


def read_text_auto(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def extract_with_regex(text: str, pattern: str) -> Decimal | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    return parse_money(m.group(1))


def extract_after_label(text: str, label: str) -> Decimal | None:
    # Match the first money-like value appearing on the same line after a label.
    pattern = rf"{re.escape(label)}[^\n\r$]*\$\s*([\-0-9,]+\.[0-9]{{2}})"
    return extract_with_regex(text, pattern)


def build():
    pack_file = latest(f"financial_report_pack_{YEAR}_*.txt")
    t2_file = latest(f"t2_corporate_{YEAR}_run_*.txt")
    gl_adj_file = latest(f"t2_gl_adjusted_{YEAR}_run_*.txt")

    pack_text = read_text_auto(pack_file)
    t2_text = read_text_auto(t2_file)
    gl_text = read_text_auto(gl_adj_file)

    pack = MethodResult(
        method="Pack_PnL_Classifier",
        revenue=extract_with_regex(pack_text, r"Revenue:\s*\$\s*([\-0-9,]+\.[0-9]{2})"),
        expenses=extract_with_regex(pack_text, r"Expenses:\s*\$\s*([\-0-9,]+\.[0-9]{2})"),
        net_income=extract_with_regex(pack_text, r"Net Income:\s*\$\s*([\-0-9,]+\.[0-9]{2})"),
        source_file=pack_file,
        notes="Derived from generated report pack P&L classification by account type/prefix.",
    )

    t2 = MethodResult(
        method="T2_Corporate_Script",
        revenue=extract_after_label(t2_text, "Charter Revenue (GL 4100)"),
        expenses=extract_after_label(t2_text, "Total Operating Expenses"),
        net_income=extract_after_label(t2_text, "NET INCOME (LOSS) BEFORE TAXES"),
        source_file=t2_file,
        notes="Uses GL 4100 charter revenue plus GL 5000+ expenses and payroll/benefits overlay.",
    )

    gl_adj = MethodResult(
        method="T2_GL_Adjusted_Script",
        revenue=extract_after_label(gl_text, "Revenue data extracted:"),
        expenses=extract_after_label(gl_text, "Expense data extracted:"),
        net_income=extract_after_label(gl_text, "Net income calculated:"),
        source_file=gl_adj_file,
        notes="Extractor-based GL adjusted financial package used for T2 support workbook.",
    )

    methods = [pack, t2, gl_adj]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    bridge_csv = AUDIT_DIR / f"net_income_bridge_{YEAR}_{ts}.csv"
    with bridge_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["method", "revenue", "expenses", "net_income", "source_file", "notes"])
        for m in methods:
            w.writerow([
                m.method,
                "" if m.revenue is None else f"{m.revenue:.2f}",
                "" if m.expenses is None else f"{m.expenses:.2f}",
                "" if m.net_income is None else f"{m.net_income:.2f}",
                str(m.source_file),
                m.notes,
            ])

    delta_csv = AUDIT_DIR / f"net_income_deltas_{YEAR}_{ts}.csv"
    with delta_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["baseline_method", "compare_method", "baseline_net_income", "compare_net_income", "delta_compare_minus_baseline"])
        baseline = methods[0]
        for m in methods[1:]:
            if baseline.net_income is None or m.net_income is None:
                delta = ""
            else:
                delta = f"{(m.net_income - baseline.net_income):.2f}"
            w.writerow([
                baseline.method,
                m.method,
                "" if baseline.net_income is None else f"{baseline.net_income:.2f}",
                "" if m.net_income is None else f"{m.net_income:.2f}",
                delta,
            ])

    manifest = AUDIT_DIR / f"final_2012_filing_pack_index_{ts}.txt"
    lines = []
    lines.append(f"FINAL 2012 FILING PACK INDEX")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("Core Financial Pack")
    lines.append(f"- {pack_file}")
    lines.append(f"- {latest(f'profit_loss_{YEAR}_*.csv')}")
    lines.append(f"- {latest(f'trial_balance_{YEAR}_*.csv')}")
    lines.append(f"- {latest(f'gst_itc_summary_{YEAR}_*.csv')}")
    lines.append(f"- {latest(f'journal_entry_types_{YEAR}_*.csv')}")
    lines.append(f"- {latest(f'general_journal_entries_{YEAR}_*.csv')}")
    lines.append("")
    lines.append("T2 / Tax Support")
    lines.append(f"- {t2_file}")
    lines.append(f"- {gl_adj_file}")
    lines.append(f"- {CRA_DIR / 'T2_2012_GL_Adjusted_Summary.xls'}")
    lines.append(f"- {CRA_DIR / 'T2_2012_GL_Adjusted_Summary.pdf'}")
    lines.append("")
    lines.append("Reconciliation Bridge")
    lines.append(f"- {bridge_csv}")
    lines.append(f"- {delta_csv}")
    lines.append("")
    lines.append("Net Income Alignment (reported)")
    for m in methods:
        ni = "N/A" if m.net_income is None else f"${m.net_income:,.2f}"
        lines.append(f"- {m.method}: {ni}")
    if methods[0].net_income is not None and methods[1].net_income is not None:
        d = methods[1].net_income - methods[0].net_income
        lines.append(f"- Delta T2_Corporate_Script minus Pack_PnL_Classifier: ${d:,.2f}")
    if methods[0].net_income is not None and methods[2].net_income is not None:
        d = methods[2].net_income - methods[0].net_income
        lines.append(f"- Delta T2_GL_Adjusted_Script minus Pack_PnL_Classifier: ${d:,.2f}")

    lines.append("")
    lines.append("Interpretation Notes")
    lines.append("- Differences are expected because each method applies different inclusion and classification logic.")
    lines.append("- Pack_PnL_Classifier is account-type/prefix driven from full GL trial rows.")
    lines.append("- T2_Corporate_Script uses GL 4100 charter revenue and adds payroll/benefits with GL 5000+ expense focus.")
    lines.append("- T2_GL_Adjusted_Script is extractor-driven for T2 support package outputs.")

    manifest.write_text("\n".join(lines), encoding="utf-8")

    print(f"MANIFEST={manifest}")
    print(f"BRIDGE={bridge_csv}")
    print(f"DELTAS={delta_csv}")


if __name__ == "__main__":
    build()
