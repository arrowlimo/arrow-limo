"""Shared access to the vehicle type catalog used by fleet and charters."""

from db_error_handling import DatabaseContext


VEHICLE_TYPE_SEED = (
    ("Luxury Sedan", 3, 10, "Executive Sedan"),
    ("Luxury Sedan (4 pax)", 4, 20, "Executive Sedan"),
    ("Sedan", 4, 30, "Sedan"),
    ("Luxury SUV (6 pax)", 6, 40, "Executive SUV - 6 Pax"),
    ("Stretch Limo (6 pax)", 6, 50, "Stretch Limo - 6 Pax"),
    ("car", 8, 60, None),
    ("Stretch Limo (10 pax)", 10, 70, None),
    ("SUV Limo (13 pax)", 13, 80, "Stretch SUV - 13 Pax"),
    ("Shuttle Style Limo Bus (14 pax)", 14, 90, "Charter Bus - 14 Pax"),
    ("Shuttle Bus (16 passenger)", 16, 100, None),
    ("Shuttle Style Limo Bus (18 pax)", 18, 110, "Charter Bus - 18 Pax"),
    ("Party Bus (20 pax)", 20, 120, "Party Bus - 20 Pax"),
    (
        "Party Bus (20 pax/washroom)",
        20,
        130,
        "Party Bus - 20 Pax / Lavatory",
    ),
    ("Party Bus (27 pax)", 27, 140, "Extreme Party Bus - 27 Pax"),
    ("Shuttle Style Limo Bus (27 pax)", 27, 150, "Charter Bus - 27 Pax"),
    ("Bus (30 passenger)", 30, 160, None),
    ("Bus (72 passenger)", 72, 170, None),
    ("Executive shuttle", None, 180, None),
)


def ensure_vehicle_type_catalog(db) -> None:
    """Ensure the shared catalog exists without replacing user sort choices."""
    with DatabaseContext(db, auto_commit=True) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.vehicle_type_catalog (
                vehicle_type_id SERIAL PRIMARY KEY,
                type_name VARCHAR(120) NOT NULL UNIQUE,
                passenger_capacity INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                pricing_vehicle_type VARCHAR(120),
                is_charter_option BOOLEAN NOT NULL DEFAULT TRUE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            ALTER TABLE public.vehicle_type_catalog
            ADD COLUMN IF NOT EXISTS pricing_vehicle_type VARCHAR(120)
        """)
        cur.execute("""
            ALTER TABLE public.vehicle_type_catalog
            ADD COLUMN IF NOT EXISTS is_charter_option BOOLEAN NOT NULL
            DEFAULT TRUE
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_vehicle_type_catalog_sort
            ON public.vehicle_type_catalog
                (passenger_capacity, sort_order, type_name)
        """)
        cur.executemany(
            """
            INSERT INTO public.vehicle_type_catalog (
                type_name,
                passenger_capacity,
                sort_order,
                pricing_vehicle_type
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (type_name) DO UPDATE SET
                passenger_capacity = COALESCE(
                    public.vehicle_type_catalog.passenger_capacity,
                    EXCLUDED.passenger_capacity
                ),
                pricing_vehicle_type = COALESCE(
                    public.vehicle_type_catalog.pricing_vehicle_type,
                    EXCLUDED.pricing_vehicle_type
                )
            """,
            VEHICLE_TYPE_SEED,
        )


def fetch_vehicle_type_catalog(db, *, charter_only: bool = False) -> list[tuple]:
    """Return active catalog rows in passenger-capacity and custom sort order."""
    where = "is_active = TRUE"
    if charter_only:
        where += " AND is_charter_option = TRUE"
    with DatabaseContext(db, auto_commit=False) as cur:
        cur.execute(
            f"""
            SELECT type_name, passenger_capacity, pricing_vehicle_type
            FROM public.vehicle_type_catalog
            WHERE {where}
            ORDER BY
                passenger_capacity IS NULL,
                passenger_capacity,
                sort_order,
                type_name
            """
        )
        return cur.fetchall() or []


def register_vehicle_type(
    db, type_name: str, passenger_capacity: int | None
) -> bool:
    """Add a newly typed vehicle type; return True when a row was inserted."""
    type_name = (type_name or "").strip()
    if not type_name:
        return False
    with DatabaseContext(db, auto_commit=True) as cur:
        cur.execute(
            """
            SELECT 1
            FROM public.vehicle_type_catalog
            WHERE type_name = %s
            """,
            (type_name,),
        )
        if cur.fetchone():
            return False
        cur.execute(
            """
            SELECT COALESCE(MAX(sort_order), 0) + 10
            FROM public.vehicle_type_catalog
            WHERE passenger_capacity IS NOT DISTINCT FROM %s
            """,
            (passenger_capacity,),
        )
        next_sort = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO public.vehicle_type_catalog
                (type_name, passenger_capacity, sort_order)
            VALUES (%s, %s, %s)
            """,
            (type_name, passenger_capacity, next_sort),
        )
    return True


def resolve_pricing_vehicle_type(cursor, vehicle_type: str) -> str:
    """Map a canonical catalog name to its legacy pricing-table key."""
    value = (vehicle_type or "").strip()
    if not value:
        return ""
    cursor.execute(
        """
        SELECT COALESCE(pricing_vehicle_type, type_name)
        FROM public.vehicle_type_catalog
        WHERE type_name = %s OR pricing_vehicle_type = %s
        ORDER BY CASE WHEN type_name = %s THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (value, value, value),
    )
    row = cursor.fetchone()
    return str(row[0]) if row and row[0] else value
