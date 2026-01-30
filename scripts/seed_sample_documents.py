import psycopg2
import os

def upsert_documents(rows):
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    )
    cur = conn.cursor()
    try:
        for title, category, file_path, file_size, tags in rows:
            cur.execute(
                """
                INSERT INTO documents (title, category, file_path, file_size, tags)
                SELECT %s, %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM documents WHERE title = %s AND category = %s
                )
                """,
                (title, category, file_path, file_size, tags, title, category)
            )
        conn.commit()
        print(f"✅ Seeded {len(rows)} sample documents (idempotent)")
    except Exception as e:
        conn.rollback()
        print(f"❌ Seed failed: {e}")
    finally:
        cur.close(); conn.close()

if __name__ == "__main__":
    samples = [
        ("Fleet Insurance Policy 2025", "Insurance", "L:/limo/docs/insurance_policy_2025.pdf", 1024*200, "fleet,policy,2025"),
        ("Vehicle Registration - Unit 12", "Licenses", "L:/limo/docs/unit12_registration.pdf", 1024*50, "vehicle,registration"),
        ("Dispatch SOP v1", "Legal", "L:/limo/docs/dispatch_sop_v1.pdf", 1024*180, "dispatch,procedures"),
    ]
    upsert_documents(samples)
