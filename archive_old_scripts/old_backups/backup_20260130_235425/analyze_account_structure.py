"""
Analyze Chart of Accounts structure to understand QB accounting categories
"""

import psycopg2

# Connect
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Get all accounts with their structure
cur.execute("""
    SELECT 
        account_number,
        account_name,
        account_type,
        account_level,
        parent_account_id,
        is_active
    FROM chart_of_accounts
    WHERE account_number IS NOT NULL
    ORDER BY account_number
""")

accounts = cur.fetchall()

print(f"Total accounts with numbers: {len(accounts)}\n")

# Standard QB/Accounting categories by first digit
category_names = {
    "1": "ASSETS (1000-1999)",
    "2": "LIABILITIES (2000-2999)", 
    "3": "EQUITY (3000-3999)",
    "4": "INCOME/REVENUE (4000-4999)",
    "5": "COST OF GOODS SOLD (5000-5999)",
    "6": "EXPENSES (6000-6999)",
    "7": "OTHER INCOME (7000-7999)",
    "8": "OTHER EXPENSES (8000-8999)",
    "9": "SPECIAL ACCOUNTS (9000-9999)"
}

# Group by first digit
categories = {}
for acc in accounts:
    num, name, acc_type, level, parent, active = acc
    first_digit = str(num)[0] if num else "?"
    if first_digit not in categories:
        categories[first_digit] = []
    categories[first_digit].append((num, name, acc_type, level, active))

# Display each category
for digit in sorted(categories.keys()):
    print(f"\n{'='*70}")
    print(f"{category_names.get(digit, f'Category {digit}')}")
    print(f"{'='*70}")
    
    accts = categories[digit]
    print(f"Total: {len(accts)} accounts\n")
    
    # Show all accounts in this category
    for num, name, acc_type, level, active in accts:
        status = "✓" if active else "✗"
        indent = "  " * (level - 1 if level else 0)
        num_str = str(num) if num else "????"
        print(f"{status} {num_str:>4s} · {indent}{name[:50]}")
        if acc_type:
            print(f"       {indent}  Type: {acc_type}")

# Also show account types breakdown
print(f"\n{'='*70}")
print("ACCOUNT TYPES BREAKDOWN")
print(f"{'='*70}")

cur.execute("""
    SELECT 
        account_type,
        COUNT(*) as count,
        STRING_AGG(CAST(account_number AS TEXT) || ' · ' || account_name, ', ' ORDER BY account_number) as examples
    FROM chart_of_accounts
    WHERE account_number IS NOT NULL
    GROUP BY account_type
    ORDER BY count DESC
""")

type_breakdown = cur.fetchall()
for acc_type, count, examples in type_breakdown:
    print(f"\n{acc_type or 'NULL'}: {count} accounts")
    if examples:
        example_list = examples.split(", ")[:3]  # First 3 examples
        for ex in example_list:
            print(f"  - {ex}")
        if len(examples.split(", ")) > 3:
            print(f"  ... and {len(examples.split(', '))-3} more")

cur.close()
conn.close()

print("\n" + "="*70)
print("Analysis complete!")
