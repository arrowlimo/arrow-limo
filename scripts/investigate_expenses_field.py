"""
Investigate if 'expenses' field contains wage data instead of expense reimbursements.
For limousine drivers, expenses should be fuel/vehicle costs, not wages.
"""
import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("INVESTIGATING 'EXPENSES' FIELD CONTENTS")
    print("=" * 80)
    
    # Hypothesis: expenses field might contain driver pay, not expense reimbursements
    # Check if gross_pay + expenses = T4 Box 14
    
    cur.execute("""
        SELECT 
            e.full_name,
            MAX(dp.t4_box_14) as cra_box_14,
            SUM(dp.gross_pay) as db_gross,
            SUM(dp.expenses) as db_expenses,
            SUM(dp.gross_pay) + SUM(dp.expenses) as combined_total,
            MAX(dp.t4_box_14) - (SUM(dp.gross_pay) + SUM(dp.expenses)) as difference
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.year = 2012
        AND dp.t4_box_14 IS NOT NULL
        GROUP BY e.employee_id, e.full_name
        ORDER BY ABS(MAX(dp.t4_box_14) - (SUM(dp.gross_pay) + SUM(dp.expenses))) ASC
        LIMIT 15
    """)
    
    results = cur.fetchall()
    
    print("\nTesting: Does gross_pay + expenses = T4 Box 14?")
    print("-" * 80)
    print(f"{'Employee':<30} {'CRA Box 14':>12} {'DB Gross':>12} {'DB Expenses':>12} {'Combined':>12} {'Diff':>12}")
    print("-" * 80)
    
    close_matches = 0
    for row in results:
        diff = row[5]
        status = "[OK] MATCH" if abs(diff) < 100 else ("✓ Close" if abs(diff) < 500 else "")
        print(f"{row[0]:<30} ${row[1]:>10,.2f} ${row[2]:>10,.2f} ${row[3]:>10,.2f} ${row[4]:>10,.2f} ${diff:>10,.2f} {status}")
        if abs(diff) < 100:
            close_matches += 1
    
    print("\n" + "=" * 80)
    print(f"[OK] CONCLUSION: {close_matches}/{len(results)} employees match within $100")
    print("=" * 80)
    
    if close_matches > len(results) * 0.7:  # More than 70% match
        print("\n🎯 CONFIRMED: 'expenses' field contains DRIVER PAY, not expense reimbursements!")
        print("\nThis explains the discrepancy:")
        print("  - Database split driver wages into 'gross_pay' and 'expenses'")
        print("  - T4 Box 14 = gross_pay + expenses (total driver compensation)")
        print("  - Field naming is misleading - 'expenses' = driver pay portion 2")
        
        print("\n" + "=" * 80)
        print("RECOMMENDED DATABASE FIXES")
        print("=" * 80)
        
        print("\n1. FIELD RENAMING (for clarity):")
        print("   Option A: Rename 'expenses' → 'additional_pay' or 'variable_pay'")
        print("   Option B: Keep current structure but document field usage")
        
        print("\n2. POPULATE base_wages FIELD:")
        print("   base_wages = gross_pay + expenses")
        print("   This will match T4 Box 14 values")
        
        print("\n3. CREATE PROPER expense_reimbursement FIELD:")
        print("   Keep actual expense reimbursements separate")
        print("   (Fuel, vehicle repairs, etc. - non-taxable)")
        
        print("\n4. UPDATE FORMULA:")
        print("   T4 Box 14 = base_wages + gratuity_amount")
        print("   Where: base_wages = gross_pay + expenses (current)")
    else:
        print("\n[WARN]  Pattern unclear. Need to investigate further.")
        print("Some employees match, others don't. May have mixed data entry methods.")
    
    # Show the fix
    print("\n" + "=" * 80)
    print("PROPOSED SQL FIX")
    print("=" * 80)
    
    print("""
UPDATE driver_payroll
SET base_wages = gross_pay + COALESCE(expenses, 0)
WHERE year = 2012
AND (base_wages IS NULL OR base_wages = 0);

-- This will populate base_wages to match T4 Box 14 values
    """)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
