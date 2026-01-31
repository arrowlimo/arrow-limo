import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Get the chart of accounts
cur.execute("""
    SELECT 
        account_code,
        account_name,
        account_type,
        description,
        is_active
    FROM chart_of_accounts
    WHERE is_active = true
    ORDER BY account_code
""")

accounts = cur.fetchall()

print("MASTER CHART OF ACCOUNTS:\n")
print(f"{'Account Code':<15} {'Account Name':<50} {'Type':<20} {'Active':<8}")
print('-' * 100)

for acc in accounts:
    code, name, acc_type, desc, active = acc
    print(f"{code:<15} {name[:50]:<50} {acc_type:<20} {str(active):<8}")

print(f"\n\nTotal accounts: {len(accounts)}")

print("\n" + "="*100)
print("\nFor Welcome Wagon (advertising service), which GL account would apply?")
print("\nRelevant options might be:")
print("  - 5200 - MARKETING & ADVERTISING")
print("  - 5300 - PROMOTIONAL EXPENSES") 
print("  - 5800 - MISCELLANEOUS EXPENSES")
print("  - Other?")

cur.close()
conn.close()
