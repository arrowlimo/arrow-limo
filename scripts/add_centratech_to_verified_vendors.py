"""
Add Centratech Technical Services to verified vendor list with fire extinguisher services classification.
Also ensure Centex (fuel) is correctly classified separately.
"""
import psycopg2


def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )
    cur = conn.cursor()

    # First, check for any Centex/Centratech confusion in receipts
    print("=" * 80)
    print("CHECKING FOR CENTEX/CENTRATECH CONFUSION")
    print("=" * 80)

    cur.execute(
        """
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            category
        FROM receipts
        WHERE UPPER(vendor_name) LIKE '%CENTEX%'
           OR UPPER(vendor_name) LIKE '%CENTRATECH%'
        ORDER BY receipt_date DESC
        LIMIT 20
    """
    )

    results = cur.fetchall()
    print(f"\nFound {len(results)} receipts with Centex/Centratech variations:")
    for rid, rdate, vendor, amount, desc, category in results:
        print(f"  {rdate} | {vendor:<35} | ${amount:>8.2f} | {category:<20} | {desc[:40]}")

    # Now identify which are Centex (fuel) vs Centratech (fire extinguisher)
    print("\n" + "=" * 80)
    print("CLASSIFICATION:")
    print("=" * 80)

    fuel_keywords = ["petroleum", "petrol", "fuel", "gas", "gasoline", "deerpark", "c-stor"]
    fire_keywords = ["fire", "extinguisher", "safety", "tech", "services"]

    for rid, rdate, vendor, amount, desc, category in results:
        full_text = (vendor + " " + (desc or "")).upper()

        is_fuel = any(kw in full_text for kw in fuel_keywords)
        is_fire = any(kw in full_text for kw in fire_keywords)

        if is_fuel and not is_fire:
            print(f"  ✓ FUEL: {vendor} (category should be: fuel)")
        elif is_fire and not is_fuel:
            print(f"  ✓ FIRE: {vendor} (category should be: maintenance)")
        elif is_fuel and is_fire:
            print(f"  ? MIXED: {vendor} - unclear, needs manual review")
        else:
            print(f"  ? UNKNOWN: {vendor} - unclear from description")

    # Document the vendor names
    print("\n" + "=" * 80)
    print("VERIFIED VENDOR LIST UPDATE:")
    print("=" * 80)
    print("""
✓ Centex Deerpark (or similar variations)
  - Service: Fuel/Gasoline for fleet vehicles
  - Category: fuel
  - Notes: Gas station, multiple location variants (Deerpark, C-STOR)
  
✓ Centratech Technical Services (or variations)
  - Service: Fire extinguisher services, maintenance
  - Category: maintenance (or new: safety_services)
  - Notes: Distinct from Centex fuel vendor; different service entirely
  
ACTION: Any receipt currently categorized as "fuel" with Centratech should be RECATEGORIZED to maintenance.
    """)

    # Query for Centratech fire extinguisher payments specifically
    cur.execute(
        """
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            category
        FROM receipts
        WHERE UPPER(vendor_name) LIKE '%CENTRATECH%'
           OR (UPPER(vendor_name) LIKE '%CENTEX%' AND UPPER(COALESCE(description, '')) LIKE '%FIRE%')
        ORDER BY receipt_date DESC
    """
    )

    fire_receipts = cur.fetchall()
    if fire_receipts:
        print(f"\nFire extinguisher service receipts (Centratech):")
        for rid, rdate, vendor, amount, category in fire_receipts:
            print(
                f"  Receipt {rid}: {rdate} | {vendor:<35} | ${amount:>8.2f} | Current category: {category}"
            )

    cur.close()
    conn.close()

    print("\nTo update categories, run:")
    print(
        """
UPDATE receipts 
SET category = 'maintenance'
WHERE vendor_name ILIKE '%Centratech%'
  AND category != 'maintenance';
    """
    )


if __name__ == "__main__":
    main()
