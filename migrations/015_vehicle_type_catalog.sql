BEGIN;

CREATE TABLE IF NOT EXISTS public.vehicle_type_catalog (
    vehicle_type_id SERIAL PRIMARY KEY,
    type_name VARCHAR(120) NOT NULL UNIQUE,
    passenger_capacity INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    pricing_vehicle_type VARCHAR(120),
    is_charter_option BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.vehicle_type_catalog
    ADD COLUMN IF NOT EXISTS pricing_vehicle_type VARCHAR(120);

ALTER TABLE public.vehicle_type_catalog
    ADD COLUMN IF NOT EXISTS is_charter_option BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_vehicle_type_catalog_sort
    ON public.vehicle_type_catalog
        (passenger_capacity, sort_order, type_name);

INSERT INTO public.vehicle_type_catalog (
    type_name,
    passenger_capacity,
    sort_order,
    pricing_vehicle_type
)
VALUES
    ('Luxury Sedan', 3, 10, 'Executive Sedan'),
    ('Luxury Sedan (4 pax)', 4, 20, 'Executive Sedan'),
    ('Sedan', 4, 30, 'Sedan'),
    ('Luxury SUV (6 pax)', 6, 40, 'Executive SUV - 6 Pax'),
    ('Stretch Limo (6 pax)', 6, 50, 'Stretch Limo - 6 Pax'),
    ('car', 8, 60, NULL),
    ('Stretch Limo (10 pax)', 10, 70, NULL),
    ('SUV Limo (13 pax)', 13, 80, 'Stretch SUV - 13 Pax'),
    (
        'Shuttle Style Limo Bus (14 pax)',
        14,
        90,
        'Charter Bus - 14 Pax'
    ),
    ('Shuttle Bus (16 passenger)', 16, 100, NULL),
    (
        'Shuttle Style Limo Bus (18 pax)',
        18,
        110,
        'Charter Bus - 18 Pax'
    ),
    ('Party Bus (20 pax)', 20, 120, 'Party Bus - 20 Pax'),
    (
        'Party Bus (20 pax/washroom)',
        20,
        130,
        'Party Bus - 20 Pax / Lavatory'
    ),
    ('Party Bus (27 pax)', 27, 140, 'Extreme Party Bus - 27 Pax'),
    (
        'Shuttle Style Limo Bus (27 pax)',
        27,
        150,
        'Charter Bus - 27 Pax'
    ),
    ('Bus (30 passenger)', 30, 160, NULL),
    ('Bus (72 passenger)', 72, 170, NULL),
    ('Executive shuttle', NULL, 180, NULL)
ON CONFLICT (type_name) DO UPDATE SET
    passenger_capacity = COALESCE(
        public.vehicle_type_catalog.passenger_capacity,
        EXCLUDED.passenger_capacity
    ),
    pricing_vehicle_type = COALESCE(
        public.vehicle_type_catalog.pricing_vehicle_type,
        EXCLUDED.pricing_vehicle_type
    );

COMMIT;
