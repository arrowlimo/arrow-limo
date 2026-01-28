import csv
import os
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / 'reports' / 'reference_lists'
OUT_DIR = ROOT / 'reports' / 'mappings'
EPS_DIR = ROOT / 'epson_lists'
OUT_DIR.mkdir(parents=True, exist_ok=True)
EPS_DIR.mkdir(parents=True, exist_ok=True)

# Seed Epson lists if none provided yet
SEED_CLASSIFICATIONS = [
    'cash withdrawal', 'Banking service fee', 'Bank Charges & Interest', 'Cashed Check',
    'Square fees', 'Square sales', 'Square service charge', 'Square deposit account',
    'Fuel', 'Vehicle M/R', 'Vehicle R&M', 'Deposit Clearing', 'Petty Cash',
    'GST Remits', 'GST/HST Payable', 'GST/QST Payable', 'Payroll Expenses'
]
SEED_PAY_ACCOUNTS = [
    'Cash on hand', 'CIBC Bank 1615', 'CIBC Business Deposit account', 'CIBC checking account',
    'Square deposit account', 'Petty Cash', 'Undeposited Funds'
]
SEED_PAY_METHODS = ['Cash', 'Debit', 'Interac Debit', 'Visa', 'MasterCard', 'Cheque']


def seed_file(path: Path, header: List[str], rows: List[List[str]]):
    if path.exists():
        return
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def ensure_seed_inputs():
    seed_file(EPS_DIR / 'epson_classifications.csv', ['classification'], [[c] for c in SEED_CLASSIFICATIONS])
    seed_file(EPS_DIR / 'epson_pay_accounts.csv', ['pay_account'], [[p] for p in SEED_PAY_ACCOUNTS])
    seed_file(EPS_DIR / 'epson_pay_methods.csv', ['pay_method'], [[m] for m in SEED_PAY_METHODS])


def read_csv_col(path: Path, col: str) -> List[str]:
    vals: List[str] = []
    with open(path, encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            v = (row.get(col) or '').strip()
            if v:
                vals.append(v)
    return vals


def sim(a: str, b: str) -> float:
    return SequenceMatcher(a=a.lower(), b=b.lower()).ratio()


def best_map(sources: List[str], targets: List[str], top_k: int = 3) -> List[Tuple[str, List[Tuple[str, float]]]]:
    out: List[Tuple[str, List[Tuple[str, float]]]] = []
    for s in sources:
        scored = [(t, sim(s, t)) for t in targets]
        scored.sort(key=lambda x: x[1], reverse=True)
        out.append((s, scored[:top_k]))
    return out


def write_mapping(filename: str, header: List[str], rows: List[List[str]]):
    out_path = OUT_DIR / filename
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print('Wrote', out_path)


def main():
    ensure_seed_inputs()

    # Load reference lists
    coas = []
    with open(REF_DIR / 'chart_of_accounts.csv', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            coas.append((row['account_code'], row['account_name'], row.get('account_type',''), row.get('account_subtype','')))

    bank_accounts = read_csv_col(REF_DIR / 'bank_accounts.csv', 'account_name')
    cash_flow_cats = read_csv_col(REF_DIR / 'cash_flow_categories.csv', 'category_name') if (REF_DIR / 'cash_flow_categories.csv').exists() else []
    square_cats = read_csv_col(REF_DIR / 'square_payment_categories.csv', 'category') if (REF_DIR / 'square_payment_categories.csv').exists() else []
    payment_methods_all = read_csv_col(REF_DIR / 'payment_methods_distinct.csv', 'payment_method')

    # Load Epson lists
    eps_class = read_csv_col(EPS_DIR / 'epson_classifications.csv', 'classification')
    eps_accounts = read_csv_col(EPS_DIR / 'epson_pay_accounts.csv', 'pay_account')
    eps_methods = read_csv_col(EPS_DIR / 'epson_pay_methods.csv', 'pay_method')

    # Map classifications -> chart_of_accounts (by account_name)
    coa_names = [name for _, name, *_ in coas]
    class_map = best_map(eps_class, coa_names)
    class_rows: List[List[str]] = []
    for src, cands in class_map:
        top = cands[0] if cands else ("", 0.0)
        class_rows.append([src, top[0], f"{top[1]:.2f}", "; ".join([f"{t}:{s:.2f}" for t,s in cands])])
    write_mapping('epson_classifications_to_coa.csv', ['epson_classification','suggested_account_name','confidence','alternatives'], class_rows)

    # Map pay accounts -> bank/cash accounts
    account_targets = bank_accounts or coa_names
    acc_map = best_map(eps_accounts, account_targets)
    acc_rows: List[List[str]] = []
    for src, cands in acc_map:
        top = cands[0] if cands else ("", 0.0)
        acc_rows.append([src, top[0], f"{top[1]:.2f}", "; ".join([f"{t}:{s:.2f}" for t,s in cands])])
    write_mapping('epson_pay_accounts_to_accounts.csv', ['epson_pay_account','suggested_account_name','confidence','alternatives'], acc_rows)

    # Map pay methods -> canonical methods
    meth_map = best_map(eps_methods, payment_methods_all)
    meth_rows: List[List[str]] = []
    for src, cands in meth_map:
        top = cands[0] if cands else ("", 0.0)
        meth_rows.append([src, top[0], f"{top[1]:.2f}", "; ".join([f"{t}:{s:.2f}" for t,s in cands])])
    write_mapping('epson_pay_methods_to_canonical.csv', ['epson_pay_method','suggested_method','confidence','alternatives'], meth_rows)

    # Optional: classifications -> cash_flow categories (if present)
    if cash_flow_cats:
        cflow_map = best_map(eps_class, cash_flow_cats)
        rows = []
        for src, cands in cflow_map:
            top = cands[0] if cands else ("", 0.0)
            rows.append([src, top[0], f"{top[1]:.2f}", "; ".join([f"{t}:{s:.2f}" for t,s in cands])])
        write_mapping('epson_classifications_to_cash_flow_categories.csv', ['epson_classification','suggested_cash_flow_category','confidence','alternatives'], rows)

if __name__ == '__main__':
    main()
