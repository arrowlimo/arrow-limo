# Extract lender statement transactions from MHT (web archive) format
# Usage: python extract_lender_statement_mht.py <input_file>

import sys
import re
from bs4 import BeautifulSoup
from datetime import datetime
from email import message_from_bytes

# Requires: pip install beautifulsoup4 lxml

def _load_mht_html(mht_path: str) -> str:
    # Try to parse as MHTML (multipart/related) and extract the text/html part
    with open(mht_path, "rb") as f:
        raw = f.read()
    try:
        msg = message_from_bytes(raw)
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/html":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="ignore")
        # Fallback: treat whole file as html text
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        # Last resort decode
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return ""

def _to_float(s: str) -> float:
    if not s:
        return 0.0
    s = s.replace(",", "").replace("$", "").strip()
    # handle parentheses for negatives
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except Exception:
        return 0.0

def parse_mht_table(mht_path):
    html = _load_mht_html(mht_path)
    soup = BeautifulSoup(html, "lxml")
    transactions = []

    def extract_dates(col_text: str):
        # Match mm/dd/yyyy where digits may contain internal spaces (e.g., '0 5 / 2 3 / 2 0 2 5')
        d2 = r"[0-9]\s*[0-9]"
        d4 = r"[0-9]\s*[0-9]\s*[0-9]\s*[0-9]"
        pattern = re.compile(fr"({d2})\s*/\s*({d2})\s*/\s*({d4})")
        dates = []
        for m in pattern.finditer(col_text):
            mm, dd, yyyy = m.groups()
            mm = mm.replace(" ", "")
            dd = dd.replace(" ", "")
            yyyy = yyyy.replace(" ", "")
            try:
                dates.append(datetime.strptime(f"{mm}/{dd}/{yyyy}", "%m/%d/%Y").date())
            except Exception:
                continue
        return dates

    def extract_amounts(col_text: str):
        # Remove all spaces so numbers like '2 , 69 2 . 21' normalize
        s = col_text.replace(" ", "")
        # Grab currency-like tokens, handling parentheses negatives
        tokens = re.findall(r"\(\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)|-?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?", s)
        vals = []
        for t in tokens:
            vals.append(_to_float(t))
        return vals

    def normalize_markers(s: str) -> str:
        # Normalize key markers to aid splitting into per-item descriptions
        repls = [
            (r"I\s*N\s*V\s*#", "INV#"),
            (r"P\s*M\s*T\s*#", "PMT#"),
            (r"N\s*S\s*F\.?", "NSF"),
            (r"I\s*n\s*t\s*e\s*r\s*e\s*s\s*t\.?", "Interest"),
            (r"G\s*E\s*N\s*J\s*R\s*N\s*L", "GENJRNL"),
            (r"B\s*a\s*l\s*a\s*n\s*c\s*e\s*f\s*o\s*r\s*w\s*a\s*r\s*d", "Balance forward"),
        ]
        out = s
        for pat, rep in repls:
            out = re.sub(pat, rep, out, flags=re.IGNORECASE)
        return out

    def split_descriptions(desc: str, n: int):
        desc_norm = normalize_markers(desc)
        # Insert separators before markers
        sep_pat = re.compile(r"(?=(INV#|PMT#|NSF|Interest|GENJRNL|Balance forward))", re.IGNORECASE)
        parts = [p.strip(" -\n\r\t") for p in sep_pat.split(desc_norm) if p.strip()]
        # Recombine token+text so we keep the marker with its text
        combined = []
        i = 0
        while i < len(parts):
            if parts[i] in {"INV#", "PMT#", "NSF", "Interest", "GENJRNL", "Balance forward"}:
                token = parts[i]
                text = parts[i+1] if i+1 < len(parts) else ""
                combined.append(f"{token} {text}".strip())
                i += 2
            else:
                combined.append(parts[i])
                i += 1
        if len(combined) == n:
            return combined
        # Fallback: truncate or pad with empty strings
        if len(combined) > n:
            return combined[:n]
        return combined + [""] * (n - len(combined))

    # Walk all tables and extract events
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        # Find header row by scanning first few rows
        header_idx = -1
        for idx in range(min(5, len(rows))):
            raw_header = [c.get_text(strip=True).lower() for c in rows[idx].find_all(["th","td"])]
            norm_header = [re.sub(r"[^a-z]", "", h) for h in raw_header]
            if (any("date" in h for h in norm_header) and any("description" in h for h in norm_header)
                    and any("amount" in h for h in norm_header) and any("balance" in h for h in norm_header)):
                header_idx = idx
                break
        if header_idx == -1:
            continue
        # Body rows may actually be a single logical row with multiple values per cell
        for row in rows[header_idx+1:]:
            cells = row.find_all(["td","th"])
            if len(cells) < 4:
                continue
            dates = extract_dates(cells[0].get_text(" ", strip=True))
            desc_block = cells[1].get_text(" ", strip=True)
            amts = extract_amounts(cells[2].get_text(" ", strip=True))
            bals = extract_amounts(cells[3].get_text(" ", strip=True))

            n = min(len(dates), len(amts), len(bals))
            if n == 0:
                continue
            desc_parts = split_descriptions(desc_block, n)
            for i in range(n):
                transactions.append({
                    "date": dates[i],
                    "description": desc_parts[i],
                    "amount": amts[i],
                    "balance": bals[i]
                })

    return transactions

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_lender_statement_mht.py <input_mht_file> [output_csv]")
        sys.exit(1)
    input_file = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else None
    transactions = parse_mht_table(input_file)
    print("date,description,amount,balance")
    for t in transactions:
        desc = ' '.join((t['description'] or '').replace(',', ' ').split())
        print(f"{t['date']},{desc},{t['amount']},{t['balance']}")
    if output_csv:
        import csv
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["date","description","amount","balance"])
            for t in transactions:
                writer.writerow([t['date'], t['description'], t['amount'], t['balance']])
        print(f"Wrote {len(transactions)} rows to {output_csv}")
    print(f"Parsed {len(transactions)} rows from {input_file}")
