"""
Clean deduplication strategy for T4 records.
Rules:
1. Exact match = duplicate (keep first, mark rest for deletion)
2. Same income + tax but different CPP = potential amendment (flag for review)
3. Orphaned records (no employee_id) = always delete
4. Version tracking (old vs amended) via source notes
"""
from __future__ import annotations

import psycopg2
import json
from decimal import Decimal
from pathlib import Path
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

DEDUP_STRATEGY = Path(r"L:\limo\reports\T4_DEDUPLICATION_STRATEGY.json")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def analyze_current_state():
    """Analyze current T4 state after cleanup."""
    conn = connect_db()
    cur = conn.cursor()

    strategy = {
        "timestamp": datetime.now().isoformat(),
        "rules": [
            {
                "name": "Exact Match = Duplicate",
                "description": "Same employee_id, year, and all 6 boxes → keep first, delete rest",
                "action": "DELETE",
            },
            {
                "name": "Orphaned Records",
                "description": "employee_id IS NULL → always delete (uncorrectable)",
                "action": "DELETE",
            },
            {
                "name": "Income+Tax Match, Different CPP",
                "description": "Potential amendment from CRA → flag, keep newest, document old version",
                "action": "FLAG_FOR_REVIEW",
            },
            {
                "name": "Suspicious Amounts",
                "description": "Income < $10 AND tax = $0 AND cpp = $0 → flag for manual review",
                "action": "FLAG_FOR_REVIEW",
            },
        ],
        "analysis_by_year": {},
        "cleanup_actions": [],
    }

    for year in [2013, 2014]:
        cur.execute(f"""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT employee_id) as distinct_employees,
                COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as orphaned
            FROM employee_t4_records
            WHERE tax_year = {year}
        """)
        total, distinct, orphaned = cur.fetchone()
        
        strategy["analysis_by_year"][year] = {
            "total_rows": total,
            "distinct_employees": distinct,
            "orphaned_rows": orphaned,
        }

        # Find exact duplicates
        cur.execute(f"""
            SELECT 
                employee_id,
                box_14_employment_income,
                box_16_cpp_contributions,
                box_18_ei_premiums,
                box_22_income_tax,
                box_24_ei_insurable_earnings,
                box_26_cpp_pensionable_earnings,
                COUNT(*) as count
            FROM employee_t4_records
            WHERE tax_year = {year}
            AND employee_id IS NOT NULL
            GROUP BY 
                employee_id,
                box_14_employment_income,
                box_16_cpp_contributions,
                box_18_ei_premiums,
                box_22_income_tax,
                box_24_ei_insurable_earnings,
                box_26_cpp_pensionable_earnings
            HAVING COUNT(*) > 1
        """)
        exact_dups = cur.fetchall()
        
        if exact_dups:
            strategy["analysis_by_year"][year]["exact_duplicates"] = {
                "count": len(exact_dups),
                "entries": [
                    {
                        "employee_id": e[0],
                        "box_14": float(e[1]) if e[1] else 0,
                        "duplicate_count": e[7],
                    }
                    for e in exact_dups[:10]
                ],
            }

    # Query suspicious entries
    for year in [2013, 2014]:
        cur.execute(f"""
            SELECT 
                employee_id,
                box_14_employment_income,
                box_22_income_tax,
                COUNT(*) as count
            FROM employee_t4_records
            WHERE tax_year = {year}
            AND employee_id IS NOT NULL
            AND COALESCE(box_14_employment_income, 0) < 10
            AND COALESCE(box_22_income_tax, 0) = 0
            GROUP BY employee_id, box_14_employment_income, box_22_income_tax
        """)
        suspicious = cur.fetchall()
        
        if suspicious:
            strategy["analysis_by_year"][year]["suspicious_amounts"] = {
                "count": len(suspicious),
                "entries": [
                    {
                        "employee_id": e[0],
                        "box_14": float(e[1]) if e[1] else 0,
                        "reason": "income < $10 AND tax = $0",
                    }
                    for e in suspicious
                ],
            }

    cur.close()
    conn.close()
    return strategy


def main():
    strategy = analyze_current_state()
    
    DEDUP_STRATEGY.parent.mkdir(parents=True, exist_ok=True)
    with open(DEDUP_STRATEGY, "w") as f:
        json.dump(strategy, f, indent=2)
    
    print(f"✅ Deduplication strategy saved: {DEDUP_STRATEGY}\n")
    print("Deduplication Rules:")
    for rule in strategy["rules"]:
        print(f"  {rule['name']}: {rule['action']}")
    
    print("\n\nCurrent T4 State (after cleanup):")
    for year in sorted(strategy["analysis_by_year"].keys()):
        data = strategy["analysis_by_year"][year]
        print(f"\n{year}:")
        print(f"  Total rows: {data['total_rows']}")
        print(f"  Distinct employees: {data['distinct_employees']}")
        print(f"  Orphaned rows: {data['orphaned_rows']}")
        if "exact_duplicates" in data:
            print(f"  Exact duplicates: {data['exact_duplicates']['count']}")
        if "suspicious_amounts" in data:
            print(f"  Suspicious amounts: {data['suspicious_amounts']['count']}")
    
    print("\n\nNext Steps:")
    print("1. ✅ Backup created: T4_BACKUP_BEFORE_CLEANUP.sql")
    print("2. ✅ Orphaned rows deleted: 9 rows, $50,869.53 removed")
    print("3. ⏳ Populate 3 missing SINs: Flinn Winston, Derksen Daryl, DEANS Gordon")
    print("4. ⏳ Apply deduplication rules via cleanup script")
    print("5. ⏳ Re-reconcile 2013-2014 T4 vs PD7A after cleanup")


if __name__ == "__main__":
    main()
