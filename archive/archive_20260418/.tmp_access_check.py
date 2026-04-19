import pyodbc
import pandas as pd

DB_PATH = r"L:\lms2026b.mdb"
RESERVES = ("012154", "012574", "013357")

conn = pyodbc.connect(
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + DB_PATH + ";"
)

placeholders = ",".join(["?"] * len(RESERVES))
q = (
    "SELECT Account_No, Reserve_No, Amount, [Key] AS pkey, LastUpdated, PaymentID "
    "FROM Payment "
    f"WHERE Reserve_No IN ({placeholders}) "
    "ORDER BY Reserve_No, LastUpdated, PaymentID"
)

df = pd.read_sql(q, conn, params=RESERVES)
conn.close()

print(df.to_string(index=False))
print("\nTotals:")
print(df.groupby("Reserve_No", as_index=False)["Amount"].sum().to_string(index=False))
