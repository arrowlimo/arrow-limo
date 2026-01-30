import os
import psycopg2


def main():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')

    conn = psycopg2.connect(host=host, dbname=name, user=user, password=password)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(client_id), 0) FROM clients")
    max_id = cur.fetchone()[0] or 0
    # Use regclass cast to avoid quoting issues
    cur.execute("SELECT setval(%s::regclass, %s, false)", ("clients_client_id_seq", max_id + 1))
    conn.commit()
    print(f"clients_client_id_seq set to {max_id + 1}")
    conn.close()


if __name__ == "__main__":
    main()
