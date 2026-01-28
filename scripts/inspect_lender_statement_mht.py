import sys
from email import message_from_bytes
from bs4 import BeautifulSoup


def load_html(path: str) -> str:
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        msg = message_from_bytes(raw)
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='ignore')
        return raw.decode('utf-8', errors='ignore')
    except Exception:
        return raw.decode('utf-8', errors='ignore')


def main():
    if len(sys.argv) < 2:
        print('Usage: python inspect_lender_statement_mht.py <file.mht>')
        sys.exit(1)
    path = sys.argv[1]
    html = load_html(path)
    print(f'HTML length: {len(html)}')
    soup = BeautifulSoup(html, 'lxml')
    tables = soup.find_all('table')
    print(f'Tables found: {len(tables)}')
    for i, table in enumerate(tables[:10]):
        rows = table.find_all('tr')
        header_cells = rows[0].find_all(['th','td']) if rows else []
        headers = [c.get_text(strip=True) for c in header_cells]
        print(f'-- Table {i}: rows={len(rows)} headers={headers}')
        # print first 3 body rows cell counts
        for r_i, row in enumerate(rows[1:4], start=1):
            cells = row.find_all(['td','th'])
            texts = [c.get_text(' ', strip=True) for c in cells]
            print(f'   row{r_i} cells={len(cells)} {texts}')

    # Write HTML snapshot for visual inspection
    out = path + '.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Wrote HTML snapshot: {out}')


if __name__ == '__main__':
    main()
