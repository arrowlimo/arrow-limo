import pyodbc

LMS_PATH = r"l:\lms2026c.mdb"
conn_str = rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

# List all tables
print("Tables in LMS:")
try:
    lms_cur.execute("SELECT Name FROM MSysObjects WHERE Type=1 ORDER BY Name")
    for row in lms_cur:
        print(f"  {row.Name}")
except Exception as e:
    print(f"  Error listing tables: {e}")

# Try to get table structure for Reserve
print("\nTrying to query Reserve table...")
try:
    lms_cur.execute("SELECT * FROM Reserve LIMIT 5")
    for i, row in enumerate(lms_cur.fetchmany(5)):
        print(f"  Row {i}: {row}")
        if i == 0:
            print(f"  Columns: {[desc[0] for desc in lms_cur.description]}")
except Exception as e:
    print(f"  Error: {e}")

# Try Payment table
print("\nTrying to query Payment table...")
try:
    lms_cur.execute("SELECT * FROM Payment LIMIT 5")
    for i, row in enumerate(lms_cur.fetchmany(5)):
        print(f"  Row {i}: {row}")
        if i == 0:
            print(f"  Columns: {[desc[0] for desc in lms_cur.description]}")
except Exception as e:
    print(f"  Error: {e}")

lms_conn.close()
