import pyodbc

mdb_path = r"L:\limo\backups\lms.mdb"
try:
    conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("Tables in MDB:")
    for table_info in cursor.tables(tableType='TABLE'):
        print(f"  {table_info[2]}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
