#!/usr/bin/env python3
"""Populate bottle/can deposit amounts for beverages.

Rules (Alberta-style deposits, simplified):
- Default per container <= 1L: $0.10
- Per container > 1L: $0.25
- Packs: deposit = container_deposit * pack_count
- Only fills rows where deposit_amount is NULL or 0 (does not overwrite non-zero).
"""

import re
import psycopg2


def classify(item_name: str):
    name = item_name.lower()

    # Pack counts
    for count in (24, 12, 6):
        if f"{count}-pack" in name or f"{count} pack" in name:
            return count, None  # pack count, size unknown -> assume <=1L

    # Sizes
    size_map = {
        "50ml": 0.05,
        "200ml": 0.2,
        "355ml": 0.355,
        "375ml": 0.375,
        "473ml": 0.473,
        "500ml": 0.5,
        "750ml": 0.75,
        "1l": 1.0,
        "1000ml": 1.0,
        "1.5l": 1.5,
        "1500ml": 1.5,
        "1.75l": 1.75,
        "1750ml": 1.75,
    }

    for token, liters in size_map.items():
        if token in name:
            return 1, liters  # single container, size in liters

    return None, None


def deposit_for(liters: float) -> float:
    if liters is None:
        return 0.10  # conservative default
    return 0.25 if liters > 1.0 else 0.10


def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )
    cur = conn.cursor()

    cur.execute(
        """
        SELECT item_id, item_name, deposit_amount
        FROM beverage_products
        WHERE COALESCE(deposit_amount, 0) = 0
        ORDER BY item_id
        """
    )

    rows = cur.fetchall()
    updates = []
    default_fills = []

    for item_id, name, _ in rows:
        count, liters = classify(name)
        if count is None:
            # Unknown size/pack: fall back to flat $0.10 per item
            default_fills.append((0.10, item_id))
            continue
        per_container = deposit_for(liters)
        deposit = round(per_container * count, 2)
        updates.append((deposit, item_id))

    for deposit, item_id in updates:
        cur.execute(
            "UPDATE beverage_products SET deposit_amount = %s WHERE item_id = %s",
            (deposit, item_id),
        )

    for deposit, item_id in default_fills:
        cur.execute(
            "UPDATE beverage_products SET deposit_amount = %s WHERE item_id = %s",
            (deposit, item_id),
        )

    conn.commit()

    print("=" * 80)
    print("POPULATE BEVERAGE DEPOSITS")
    print("=" * 80)
    print(f"Items examined: {len(rows)}")
    print(f"Deposits set (sized):   {len(updates)}")
    print(f"Deposits set (default): {len(default_fills)}")

    cur.execute(
        "SELECT COUNT(*) FROM beverage_products WHERE COALESCE(deposit_amount, 0) = 0"
    )
    remaining, = cur.fetchone()
    print(f"Remaining with 0/null deposit: {remaining}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
