"""
Comprehensive T4 data cleanup and audit trail.
1. Backup current employee_t4_records
2. Log and delete 9 orphaned 2012 rows
3. Create audit trail with decisions
"""
from __future__ import annotations

import psycopg2
import json
from pathlib import Path
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

AUDIT_LOG = Path(r"L:\limo\reports\T4_CLEANUP_AUDIT_LOG.json")
BACKUP_SQL = Path(r"L:\limo\reports\T4_BACKUP_BEFORE_CLEANUP.sql")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def backup_and_cleanup():
    conn = connect_db()
    cur = conn.cursor()

    audit = {
        "timestamp": datetime.now().isoformat(),
        "actions": [],
        "backup_location": str(BACKUP_SQL),
    }

    try:
        print("📋 Step 1: Backup employee_t4_records before cleanup...")
        
        # Create backup SQL
        cur.execute("SELECT * FROM employee_t4_records ORDER BY employee_id, tax_year")
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        with open(BACKUP_SQL, "w") as f:
            f.write("-- Backup of employee_t4_records before cleanup\n")
            f.write(f"-- Created: {datetime.now().isoformat()}\n\n")
            f.write("BEGIN;\n")
            f.write("DELETE FROM employee_t4_records;\n")
            f.write(f"-- Original row count: {len(rows)}\n\n")
            
            for row in rows:
                vals = []
                for v in row:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, str):
                        vals.append(f"'{v.replace(chr(39), chr(39)*2)}'")
                    else:
                        vals.append(str(v))
                insert = f"INSERT INTO employee_t4_records ({', '.join(columns)}) VALUES ({', '.join(vals)});\n"
                f.write(insert)
            f.write("COMMIT;\n")
        
        audit["actions"].append({
            "action": "backup_created",
            "table": "employee_t4_records",
            "row_count": len(rows),
            "location": str(BACKUP_SQL),
        })
        print(f"✅ Backup created: {BACKUP_SQL} ({len(rows)} rows)")

        print("\n📋 Step 2: Delete 9 orphaned 2012 rows (employee_id = NULL)...")
        
        # Get orphaned rows first
        cur.execute("""
            SELECT 
                employee_id,
                tax_year,
                box_14_employment_income,
                box_22_income_tax,
                created_at
            FROM employee_t4_records
            WHERE tax_year = 2012
            AND employee_id IS NULL
        """)
        orphaned = cur.fetchall()
        
        # Document each orphaned row
        total_orphaned_income = 0
        for emp_id, year, box_14, box_22, created_at in orphaned:
            income = box_14 or 0
            total_orphaned_income += float(income)
            audit["actions"].append({
                "action": "delete_orphaned_row",
                "employee_id": emp_id,
                "tax_year": year,
                "box_14": float(income),
                "box_22": float(box_22) if box_22 else 0,
                "created_at": str(created_at),
                "reason": "orphaned record (employee_id=NULL, cannot be matched)",
            })
        
        # Delete orphaned rows
        cur.execute("""
            DELETE FROM employee_t4_records
            WHERE tax_year = 2012 AND employee_id IS NULL
        """)
        conn.commit()
        
        audit["actions"].append({
            "action": "summary_orphaned_deletion",
            "count": len(orphaned),
            "total_income_removed": total_orphaned_income,
        })
        print(f"✅ Deleted {len(orphaned)} orphaned rows (${total_orphaned_income:,.2f} income)")

        print("\n📋 Step 3: Identify 2012 employees needing SIN population...")
        
        cur.execute("""
            SELECT DISTINCT
                etr.employee_id,
                e.full_name,
                e.t4_sin,
                SUM(etr.box_14_employment_income) as total_income
            FROM employee_t4_records etr
            LEFT JOIN employees e ON etr.employee_id = e.employee_id
            WHERE etr.tax_year = 2012
            AND etr.employee_id IS NOT NULL
            AND (e.t4_sin IS NULL OR e.t4_sin = '')
            GROUP BY etr.employee_id, e.full_name, e.t4_sin
        """)
        missing_sins = cur.fetchall()
        
        for emp_id, name, sin, total_income in missing_sins:
            audit["actions"].append({
                "action": "missing_sin_identified",
                "employee_id": emp_id,
                "full_name": name,
                "t4_sin": sin or "(NULL)",
                "total_2012_income": float(total_income),
                "action_required": "POPULATE t4_sin field",
            })
            print(f"⚠️  emp_id={emp_id}: {name}, SIN missing, income=${total_income:,.2f}")

        print("\n✅ Cleanup complete!")
        print(f"\nSummary:")
        print(f"  Orphaned rows deleted: {len(orphaned)}")
        print(f"  Income removed: ${total_orphaned_income:,.2f}")
        print(f"  Missing SINs to populate: {len(missing_sins)}")

    except Exception as e:
        conn.rollback()
        audit["actions"].append({
            "action": "error",
            "error": str(e),
        })
        print(f"❌ Error: {e}")
        raise
    
    finally:
        # Save audit log
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "w") as f:
            json.dump(audit, f, indent=2)
        print(f"\n📋 Audit log saved: {AUDIT_LOG}")
        
        cur.close()
        conn.close()


if __name__ == "__main__":
    backup_and_cleanup()
