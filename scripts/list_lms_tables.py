import pyodbc

LMS_PATH = r'L:\limo\database_backups\lms2026.mdb'
conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
cur = conn.cursor()

print("LMS Database Tables:")
print("="*80)
for table_info in cur.tables(tableType='TABLE'):
    print(f"  {table_info.table_name}")

cur.close()
conn.close()
