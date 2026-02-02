"""
Create audit_logs table for eHOS compliance and security tracking
"""

import os

import psycopg2


def setup_audit_logs_table():
    """Create audit_logs table if it doesn't exist"""
    conn_params = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "database": os.environ.get("DB_NAME", "almsdata"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD"),
    }

    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()

    try:
        # Create audit_logs table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                audit_id SERIAL PRIMARY KEY,
                user_id INTEGER,
                action VARCHAR(255) NOT NULL,
                charter_id INTEGER,
                ip_address VARCHAR(45),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details JSONB,

                FOREIGN KEY (user_id) REFERENCES employees(employee_id)
                    ON DELETE SET NULL,
                FOREIGN KEY (charter_id) REFERENCES charters(charter_id)
                    ON DELETE SET NULL
            )
        """
        )

        # Create index on timestamp for fast queries
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp
            ON audit_logs(timestamp DESC)
        """
        )

        # Create index on action for filtering
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_action
            ON audit_logs(action)
        """
        )

        # Create index on charter_id for charter-specific audits
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_charter
            ON audit_logs(charter_id)
        """
        )

        conn.commit()
        print("✓ audit_logs table created successfully")

    except psycopg2.Error as e:
        print(f"✗ Error creating table: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    setup_audit_logs_table()
