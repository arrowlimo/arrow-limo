import pyodbc

mdb_path = r"L:\limo\backups\lms.mdb"
conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# List all tables
print("Tables in MDB:")
for table_info in cursor.tables(tableType='TABLE'):
    print(f"  {table_info[2]}")

# Find Reserve table
cursor.execute("SELECT * FROM Reserve WHERE 1=0")  # Get columns only
print("\nReserve table columns:")
for i, col in enumerate(cursor.description, 1):
    print(f"  {i:3}. {col[0]}")

# Sample a few records
cursor.execute("SELECT TOP 5 * FROM Reserve")
print(f"\nFirst 5 records from Reserve:")
cols = [col[0] for col in cursor.description]
for row in cursor.fetchall():
    print(f"\n  Record:")
    for i, val in enumerate(row[:15]):  # First 15 columns only
        print(f"    {cols[i]:20} = {val}")
    print("    ...")

conn.close()
