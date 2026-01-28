import psycopg2
import os

def main():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REMOVED***"),
    )
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size BIGINT,
                tags TEXT,
                upload_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
            CREATE INDEX IF NOT EXISTS idx_documents_upload_date ON documents(upload_date);
            """
        )
        conn.commit()
        print("✅ documents table ensured.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to create documents table: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()