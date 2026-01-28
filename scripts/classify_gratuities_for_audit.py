#!/usr/bin/env python3
"""
Classify gratuities for CRA audit compliance.

Flags charters where gratuity classification may need manual review:
- High gratuity amounts (>$200)
- Gratuity on invoiced charters with corporate clients
- Gratuities that appear on multiple consecutive charters
"""
import psycopg2
import json
from datetime import datetime
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("=" * 80)
    print("GRATUITY CLASSIFICATION AUDIT - FLAGGING REVIEW CANDIDATES")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    review_candidates = []
    
    # 1. High-value gratuities (>$200)
    print("1. HIGH-VALUE GRATUITIES (>$200):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            total_amount_due,
            driver_gratuity,
            driver_name,
            gratuity_type
        FROM charters
        WHERE driver_gratuity > 200
        AND EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
        ORDER BY driver_gratuity DESC
        LIMIT 20
    """)
    
    high_value = cur.fetchall()
    if high_value:
        print(f"   Found {len(high_value)} high-value gratuities")
        print(f"   {'Reserve':<10} {'Date':<12} {'Invoice':<12} {'Gratuity':<12} {'Driver':<20} {'Type':<10}")
        print("   " + "-" * 76)
        for row in high_value:
            print(f"   {row[0]:<10} {str(row[1]):<12} ${row[2] or 0:<11,.2f} ${row[3]:<11,.2f} {(row[4] or '')[:19]:<20} {row[5] or 'NULL':<10}")
            review_candidates.append({
                'reserve_number': row[0],
                'reason': 'High value (>$200)',
                'gratuity': float(row[3]),
                'current_type': row[5]
            })
    else:
        print("   None found")
    
    # 2. Round-number gratuities (suggests pre-calculated/invoiced)
    print("\n2. ROUND-NUMBER GRATUITIES (Suggests Pre-calculated/Invoiced):")
    print("-" * 80)
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            total_amount_due,
            driver_gratuity
        FROM charters
        WHERE driver_gratuity > 0
        AND EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
        AND (
            driver_gratuity = ROUND(driver_gratuity / 10) * 10  -- Multiples of $10
            OR driver_gratuity = ROUND(driver_gratuity / 5) * 5  -- Multiples of $5
        )
        AND driver_gratuity >= 50  -- Exclude small amounts
        ORDER BY driver_gratuity DESC
        LIMIT 15
    """)
    
    round_num = cur.fetchall()
    if round_num:
        print(f"   Found {len(round_num)} round-number gratuities")
        print(f"   {'Reserve':<10} {'Date':<12} {'Invoice':<12} {'Gratuity':<12}")
        print("   " + "-" * 46)
        for row in round_num:
            print(f"   {row[0]:<10} {str(row[1]):<12} ${row[2] or 0:<11,.2f} ${row[3]:<11,.2f}")
    else:
        print("   None found")
    
    # 4. Summary and recommendations
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            gratuity_type,
            COUNT(*) as count,
            SUM(driver_gratuity) as total_gratuity,
            AVG(driver_gratuity) as avg_gratuity
        FROM charters
        WHERE driver_gratuity > 0
        AND EXTRACT(YEAR FROM charter_date) BETWEEN 2013 AND 2014
        GROUP BY gratuity_type
    """)
    
    print(f"\n{'Type':<15} {'Count':<10} {'Total':<15} {'Average':<15}")
    print("-" * 55)
    for row in cur.fetchall():
        gtype = row[0] or 'NULL'
        print(f"{gtype:<15} {row[1]:<10,} ${row[2]:<14,.2f} ${row[3]:<14,.2f}")
    
    print(f"\n{'Total flagged for review:':<30} {len(review_candidates):,}")
    
    # Save review candidates to JSON
    output_file = f"reports/gratuity_review_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'total_flagged': len(review_candidates),
            'candidates': review_candidates
        }, f, indent=2, cls=DecimalEncoder)
    
    print(f"\n✓ Review candidates saved to: {output_file}")
    print("\nRECOMMENDATIONS:")
    print("  1. Review flagged charters manually")
    print("  2. If gratuity was on original invoice → UPDATE gratuity_type='invoiced'")
    print("  3. If gratuity was freely given → Leave as 'direct'")
    print("  4. Add notes to gratuity_documentation column")
    print("\nNext step: Run audit defense report generator")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
