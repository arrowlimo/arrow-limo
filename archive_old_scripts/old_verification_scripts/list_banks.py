import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', password='ArrowLimousine', dbname='almsdata')
cur = conn.cursor()

output = []
output.append("\n" + "="*80)
output.append("ALL BANKING ACCOUNTS")
output.append("="*80)

# GL Codes
output.append("\n1. BANKING GL CODES (Chart of Accounts)")
output.append("-"*80)

cur.execute("""
    SELECT account_code, account_name, bank_account_number, is_active
    FROM chart_of_accounts
    WHERE account_code BETWEEN '1000' AND '1199'
    AND is_active = TRUE
    ORDER BY account_code
""")

for code, name, bank_num, active in cur.fetchall():
    bank_display = f" ({bank_num})" if bank_num else ""
    output.append(f"  {code} - {name}{bank_display}")

# Physical bank accounts
output.append("\n2. PHYSICAL BANK ACCOUNTS")
output.append("-"*80)

cur.execute("""
    SELECT account_number, account_name, institution_name, account_type
    FROM bank_accounts
    WHERE is_active = TRUE
    ORDER BY bank_id
""")

for acct_num, acct_name, institution, acct_type in cur.fetchall():
    output.append(f"  {acct_num}: {acct_name} - {institution} ({acct_type})")

# Write and print
result = "\n".join(output)
with open('l:\\limo\\banking_accounts_list.txt', 'w') as f:
    f.write(result)

print(result)
print(f"\n(Also saved to l:\\limo\\banking_accounts_list.txt)")

conn.close()
