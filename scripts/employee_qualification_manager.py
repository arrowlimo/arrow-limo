#!/usr/bin/env python3
"""
Simple qualification management for employees
Add/view/update qualifications with dates
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def add_qualification(employee_id, qual_type, qual_date, expiry_date=None, notes=""):
    """Add a qualification record"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO employee_qualifications 
            (employee_id, qualification_type, qualification_date, expiry_date, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (employee_id, qual_type, qual_date, expiry_date, notes))
        
        conn.commit()
        print(f"✅ Added {qual_type} for employee_id={employee_id}, date={qual_date}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def get_employee_qualifications(employee_id):
    """Fetch all qualifications for an employee"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        cur.execute("""
            SELECT qualification_id, qualification_type, qualification_date, 
                   expiry_date, notes
            FROM employee_qualifications
            WHERE employee_id = %s
            ORDER BY qualification_date DESC
        """, (employee_id,))
        
        quals = cur.fetchall()
        cur.close()
        conn.close()
        return quals
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def update_qualification(qualification_id, expiry_date=None, notes=""):
    """Update a qualification record"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE employee_qualifications
            SET expiry_date = COALESCE(%s, expiry_date),
                notes = COALESCE(%s, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE qualification_id = %s
        """, (expiry_date, notes if notes else None, qualification_id))
        
        conn.commit()
        print(f"✅ Updated qualification_id={qualification_id}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def get_employees_missing_qualifications():
    """Find employees missing required qualifications"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Check for missing common qualifications
        cur.execute("""
            SELECT e.employee_id, e.full_name, e.employee_number,
                   CASE WHEN pq.qualification_id IS NULL THEN 'Missing'
                        WHEN pq.expiry_date < CURRENT_DATE THEN 'Expired'
                        ELSE 'Current'
                   END as proserve_status,
                   CASE WHEN vq.qualification_id IS NULL THEN 'Missing'
                        WHEN vq.expiry_date < CURRENT_DATE THEN 'Expired'
                        ELSE 'Current'
                   END as vulnerable_sector_status
            FROM employees e
            LEFT JOIN employee_qualifications pq ON e.employee_id = pq.employee_id 
                                                   AND pq.qualification_type = 'ProServe'
            LEFT JOIN employee_qualifications vq ON e.employee_id = vq.employee_id 
                                                   AND vq.qualification_type = 'Vulnerable Sector Check'
            WHERE e.is_chauffeur = true
            ORDER BY e.full_name
        """)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

if __name__ == "__main__":
    # Example usage
    print("=" * 80)
    print("EMPLOYEE QUALIFICATION MANAGEMENT")
    print("=" * 80)
    
    # Check for missing qualifications
    print("\nChauffeurs with missing/expired qualifications:")
    missing = get_employees_missing_qualifications()
    for emp_id, name, emp_num, proserve, vsc in missing:
        if proserve != 'Current' or vsc != 'Current':
            print(f"  {name} ({emp_num}): ProServe={proserve}, VSC={vsc}")
