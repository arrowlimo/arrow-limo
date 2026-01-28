import psycopg2

# Neon connection
neon_conn = psycopg2.connect(
    host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    database='neondb',
    user='neondb_owner',
    password='***REMOVED***',
    sslmode='require',
)

neon_cur = neon_conn.cursor()

print("Creating vehicle_pricing_defaults table on Neon...")

create_sql = """
CREATE TABLE IF NOT EXISTS vehicle_pricing_defaults (
    vehicle_type VARCHAR(255) PRIMARY KEY,
    nrr DECIMAL(12, 2) NOT NULL DEFAULT 0,
    hourly_rate DECIMAL(12, 2) NOT NULL DEFAULT 0,
    daily_rate DECIMAL(12, 2) NOT NULL DEFAULT 0,
    standby_rate DECIMAL(12, 2) NOT NULL DEFAULT 0,
    airport_pickup_calgary DECIMAL(12, 2) NOT NULL DEFAULT 0,
    airport_pickup_edmonton DECIMAL(12, 2) NOT NULL DEFAULT 0,
    hourly_package DECIMAL(12, 2),
    fee_1 DECIMAL(12, 2) DEFAULT 0,
    fee_2 DECIMAL(12, 2) DEFAULT 0,
    fee_3 DECIMAL(12, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

neon_cur.execute(create_sql)
neon_conn.commit()

print("✓ Table created successfully")

neon_cur.close()
neon_conn.close()
