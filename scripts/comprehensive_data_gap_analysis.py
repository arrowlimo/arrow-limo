"""
Comprehensive data gap analysis for 2012-2025.
Checks banking, receipts, payments, charters, clients, employees, vehicles, GL.
Cross-references with QuickBooks All_Time CSV exports.
Generates a detailed gap report showing what's missing by year.
"""
import os
import csv
import psycopg2
from collections import defaultdict
from datetime import datetime


def env(name, default=None):
    return os.environ.get(name, default)


def get_db_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        dbname=env("DB_NAME", "almsdata"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "***REMOVED***"),
    )


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def get_table_columns(cur, table):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def get_available_tables(cur):
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        ORDER BY table_name
        """
    )
    return {r[0] for r in cur.fetchall()}


def analyze_db_by_year(conn, years):
    """Analyze database presence for each table by year."""
    cur = conn.cursor()
    tables = get_available_tables(cur)
    
    table_configs = {
        'banking_transactions': {'date_col': 'transaction_date', 'count_col': '*', 'sum_cols': ['debit_amount', 'credit_amount']},
        'receipts': {'date_col': 'receipt_date', 'count_col': '*', 'sum_cols': ['gross_amount', 'gst_amount']},
        'payments': {'date_col': 'payment_date', 'count_col': '*', 'sum_cols': ['amount']},
        'charters': {'date_col': 'charter_date', 'count_col': '*', 'sum_cols': ['total_amount_due', 'paid_amount']},
        'clients': {'date_col': 'created_at', 'count_col': '*', 'sum_cols': []},
        'employees': {'date_col': 'hire_date', 'count_col': '*', 'sum_cols': []},
        'vehicles': {'date_col': 'created_at', 'count_col': '*', 'sum_cols': []},
        'unified_general_ledger': {'date_col': 'transaction_date', 'count_col': '*', 'sum_cols': ['debit_amount', 'credit_amount']},
    }
    
    results = {}
    
    for table_name, config in table_configs.items():
        if table_name not in tables:
            results[table_name] = {y: {'exists': False} for y in years}
            continue
        
        # Check if date column exists
        cols = get_table_columns(cur, table_name)
        date_col = config['date_col']
        if date_col not in cols:
            # Try alternative date columns
            for alt in ['created_at', 'date', 'transaction_date', 'updated_at']:
                if alt in cols:
                    date_col = alt
                    break
            else:
                results[table_name] = {y: {'exists': True, 'no_date_col': True} for y in years}
                continue
        
        results[table_name] = {}
        
        for year in years:
            start = f"{year}-01-01"
            end = f"{year}-12-31"
            
            # Build sum expressions
            sum_exprs = []
            for col in config['sum_cols']:
                if col in cols:
                    sum_exprs.append(f"COALESCE(SUM({col}),0) as {col}_total")
            
            sum_clause = ", " + ", ".join(sum_exprs) if sum_exprs else ""
            
            try:
                query = f"""
                    SELECT COUNT(*){sum_clause}
                    FROM {table_name}
                    WHERE {date_col} >= %s AND {date_col} <= %s
                """
                cur.execute(query, (start, end))
                row = cur.fetchone()
                
                year_data = {
                    'exists': True,
                    'count': int(row[0]) if row else 0,
                }
                
                for i, col in enumerate(config['sum_cols']):
                    if col in cols:
                        year_data[f"{col}_total"] = float(row[i + 1]) if row and len(row) > i + 1 else 0.0
                
                results[table_name][year] = year_data
            except Exception as e:
                results[table_name][year] = {'exists': True, 'error': str(e)}
    
    return results


def analyze_qb_exports(export_files):
    """Analyze QuickBooks CSV exports to find year coverage."""
    qb_data = {}
    
    for file_path in export_files:
        if not os.path.exists(file_path):
            continue
        
        file_name = os.path.basename(file_path)
        export_type = file_name.replace('_All_Time.csv', '').replace('_', ' ')
        
        year_counts = defaultdict(int)
        total_rows = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                
                # Find date columns
                date_cols = [h for h in headers if 'date' in h.lower() or 'time' in h.lower()]
                
                for row in reader:
                    total_rows += 1
                    
                    # Try to extract year from any date column
                    for date_col in date_cols:
                        val = row.get(date_col, '')
                        if val:
                            # Try various date formats
                            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                                try:
                                    dt = datetime.strptime(val[:10], fmt)
                                    year_counts[dt.year] += 1
                                    break
                                except:
                                    continue
                            # Also try just extracting 4-digit year
                            import re
                            m = re.search(r'\b(20\d{2}|19\d{2})\b', val)
                            if m:
                                year_counts[int(m.group(1))] += 1
        except Exception as e:
            year_counts['error'] = str(e)
        
        qb_data[export_type] = {
            'total_rows': total_rows,
            'years': dict(year_counts),
        }
    
    return qb_data


def write_report(db_results, qb_results, years, out_path):
    """Write comprehensive gap analysis report."""
    lines = []
    lines.append("# Comprehensive Data Gap Analysis (2012-2025)")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Database summary
    lines.append("## Database Coverage by Year and Table")
    lines.append("")
    
    for table, year_data in sorted(db_results.items()):
        lines.append(f"### {table}")
        lines.append("")
        
        if not year_data:
            lines.append("- Table does not exist")
            lines.append("")
            continue
        
        # Check if any year has data
        has_any_data = any(y.get('count', 0) > 0 for y in year_data.values() if isinstance(y, dict))
        
        if not has_any_data:
            first_year_info = list(year_data.values())[0]
            if first_year_info.get('no_date_col'):
                lines.append("- Table exists but no date column found")
            elif first_year_info.get('error'):
                lines.append(f"- Query error: {first_year_info['error']}")
            else:
                lines.append("- **NO DATA for any year 2012-2025**")
            lines.append("")
            continue
        
        lines.append("Year | Count | Additional Info")
        lines.append("---|---:|---")
        
        for year in sorted(years):
            info = year_data.get(year, {})
            count = info.get('count', 0)
            
            # Build additional info
            extras = []
            for key, val in info.items():
                if key not in ['exists', 'count', 'no_date_col', 'error'] and val:
                    if isinstance(val, float):
                        extras.append(f"{key}: ${val:,.2f}")
                    else:
                        extras.append(f"{key}: {val}")
            
            extra_str = ", ".join(extras) if extras else "-"
            
            if count == 0:
                lines.append(f"{year} | **0** [FAIL] | {extra_str}")
            else:
                lines.append(f"{year} | {count:,} ✓ | {extra_str}")
        
        lines.append("")
    
    # QuickBooks exports summary
    lines.append("## QuickBooks All_Time Export Coverage")
    lines.append("")
    
    for export_type, data in sorted(qb_results.items()):
        lines.append(f"### {export_type}")
        lines.append(f"- Total rows: {data['total_rows']:,}")
        
        if 'error' in data['years']:
            lines.append(f"- Error: {data['years']['error']}")
        elif data['years']:
            lines.append("- Years found:")
            for year in sorted(data['years'].keys()):
                if isinstance(year, int):
                    lines.append(f"  - {year}: {data['years'][year]:,} records")
        else:
            lines.append("- No date information found")
        
        lines.append("")
    
    # Gap summary
    lines.append("## Missing Data Summary")
    lines.append("")
    
    for year in sorted(years):
        missing = []
        for table, year_data in sorted(db_results.items()):
            info = year_data.get(year, {})
            if info.get('exists') and info.get('count', 0) == 0:
                missing.append(table)
        
        if missing:
            lines.append(f"### {year} - Missing Tables")
            for t in missing:
                lines.append(f"- {t}")
        else:
            lines.append(f"### {year} - [OK] All core tables have data")
        
        lines.append("")
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def main():
    years = list(range(2012, 2026))  # 2012-2025
    
    export_files = [
        "L:\\limo\\quickbooks_exports\\Vendor_List_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\AR_Aging_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Balance_Sheet_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Chart_of_Accounts_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Customer_List_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Employee_List_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\General_Journal_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Invoice_List_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Profit_and_Loss_All_Time.csv",
        "L:\\limo\\quickbooks_exports\\Vehicle_List_All_Time.csv",
    ]
    
    print("Analyzing database coverage 2012-2025...")
    conn = get_db_connection()
    try:
        db_results = analyze_db_by_year(conn, years)
    finally:
        try:
            conn.close()
        except:
            pass
    
    print("Analyzing QuickBooks All_Time exports...")
    qb_results = analyze_qb_exports(export_files)
    
    out_dir = os.path.join("exports", "audit")
    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, "comprehensive_data_gap_analysis_2012_2025.md")
    
    write_report(db_results, qb_results, years, out_path)
    
    print(f"\n[OK] Comprehensive gap analysis report: {out_path}")
    
    # Print quick summary
    print("\nQuick Summary:")
    for table, year_data in sorted(db_results.items()):
        if not year_data:
            continue
        zero_years = [y for y in years if year_data.get(y, {}).get('count', 0) == 0]
        if zero_years:
            print(f"  {table}: MISSING data for years {zero_years}")


if __name__ == "__main__":
    main()
