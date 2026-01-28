import os, sys, re, json
from pathlib import Path
import pandas as pd

CAND_DATE = [
    'date','transaction_date','posting date','posting_date','post date','posted date','value date','date posted'
]
CAND_DESC = [
    'description','memo','details','transaction details','payee','name','narrative','particulars','details 1','details 2'
]
CAND_DEBIT = ['debit','withdrawal','withdrawals','debit amount','debits','dr']
CAND_CREDIT = ['credit','deposit','deposits','credit amount','credits','cr']
CAND_AMOUNT = ['amount','amount ($)','transaction amount','amt']


def find_col(cols, candidates):
    lc = [c.lower() for c in cols]
    for cand in candidates:
        if cand in lc:
            return cols[lc.index(cand)]
    # fuzzy contains
    for i, c in enumerate(lc):
        for cand in candidates:
            if cand in c:
                return cols[i]
    return None


def normalize_df(df: pd.DataFrame):
    cols = list(df.columns)
    date_col = find_col(cols, CAND_DATE)
    desc_col = find_col(cols, CAND_DESC)
    debit_col = find_col(cols, CAND_DEBIT)
    credit_col = find_col(cols, CAND_CREDIT)
    amount_col = find_col(cols, CAND_AMOUNT)

    if not date_col:
        raise ValueError('No date-like column found')
    if not desc_col:
        desc_col = cols[1] if len(cols) > 1 else date_col

    out = pd.DataFrame()
    out['date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
    out['description'] = df[desc_col].astype(str)

    debit = pd.Series([0.0]*len(df))
    credit = pd.Series([0.0]*len(df))

    if debit_col:
        debit = pd.to_numeric(df[debit_col], errors='coerce').fillna(0.0)
    if credit_col:
        credit = pd.to_numeric(df[credit_col], errors='coerce').fillna(0.0)

    if not debit_col and not credit_col and amount_col:
        amt = pd.to_numeric(df[amount_col], errors='coerce').fillna(0.0)
        # Heuristic: positive means credit, negative means debit
        credit = amt.clip(lower=0)
        debit = (-amt).clip(lower=0)

    out['debit'] = debit
    out['credit'] = credit
    out['amount_signed'] = credit - debit
    return out


def main():
    if len(sys.argv) < 2:
        print('Usage: python ingest_top_level_bank_excels.py <folder> [year_filter]')
        sys.exit(1)
    folder = Path(sys.argv[1])
    year_filter = sys.argv[2] if len(sys.argv) > 2 else '2012'

    out_dir = Path('exports/banking/imported_csv')
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = []
    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        p = Path(entry.path)
        if p.suffix.lower() not in {'.xlsx', '.xlsm'}:
            continue
        name = p.name.lower()
        if year_filter and year_filter not in name:
            continue
        if not any(k in name for k in ['cibc', 'scotia', 'scotiabank', 'bank']):
            continue
        sources.append(p)

    results = []
    for p in sources:
        try:
            xls = pd.ExcelFile(str(p))
            for sheet in xls.sheet_names:
                try:
                    df = xls.parse(sheet)
                    if df.empty:
                        continue
                    norm = normalize_df(df)
                    # Filter by year on date when possible
                    if 'date' in norm:
                        norm = norm.dropna(subset=['date'])
                        norm = norm[(norm['date'].astype(str).str.startswith(year_filter))]
                    out_path = out_dir / f"{p.stem}_{re.sub(r'[^A-Za-z0-9]+','_',sheet)}.csv"
                    norm.to_csv(out_path, index=False)
                    results.append({'file': p.name, 'sheet': sheet, 'rows': len(norm), 'out': str(out_path)})
                except Exception as e:
                    results.append({'file': p.name, 'sheet': sheet, 'error': str(e)})
        except Exception as e:
            results.append({'file': p.name, 'error': str(e)})

    print(json.dumps({'parsed': results}, indent=2, default=str))

if __name__ == '__main__':
    main()
