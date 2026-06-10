"""
GIFI (General Index of Financial Information) mapping for T2 returns.

Maps Arrow Limo's internal GL account codes to CRA GIFI codes used on
Schedule 125 (Income Statement) and Schedule 100 (Balance Sheet).

The GL→GIFI mapping drives the auto-fill on the T2 data entry widget.
Unmapped GL codes are accumulated in the GIFI 9923 (Other Expenses) bucket.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# GIFI code → description lookup (subset relevant to a small limo company)
# ---------------------------------------------------------------------------
GIFI_DESCRIPTIONS: dict[str, str] = {
    # Income Statement (Schedule 125)
    "8000": "Sales, commissions, and fees",
    "8089": "Other income",
    "8518": "Cost of sales",
    "8513": "Salaries, wages, and bonuses",
    "8523": "Employee benefits",
    "9060": "Advertising and promotion",
    "8590": "Bad debts",
    "8711": "Interest and bank charges",
    "9270": "Insurance",
    "8810": "Office expenses",
    "8860": "Professional and consulting fees",
    "9180": "Property taxes",
    "8690": "Rent",
    "9130": "Repairs and maintenance",
    "9200": "Travel",
    "9281": "Motor vehicle expenses (not CCA)",
    "9150": "Meals and entertainment (50%)",
    "9370": "Telephone and utilities",
    "9923": "Other expenses",
    # Balance Sheet (Schedule 100)
    "1000": "Cash and deposits",
    "1060": "Accounts receivable",
    "1100": "Inventory",
    "1600": "Property, plant, and equipment (net)",
    "2000": "Accounts payable",
    "2600": "Long-term debt",
    "3600": "Retained earnings",
}

# ---------------------------------------------------------------------------
# Schedule 125 expense field → GIFI code
# (used in reverse during save/export)
# ---------------------------------------------------------------------------
SCH125_FIELD_TO_GIFI: dict[str, str] = {
    "sch125_revenue": "8000",
    "sch125_other_income": "8089",
    "sch125_cost_of_sales": "8518",
    "sch125_salaries": "8513",
    "sch125_benefits": "8523",
    "sch125_rent": "8690",
    "sch125_repairs": "9130",
    "sch125_bad_debts": "8590",
    "sch125_interest": "8711",
    "sch125_insurance": "9270",
    "sch125_office": "8810",
    "sch125_professional_fees": "8860",
    "sch125_property_tax": "9180",
    "sch125_travel": "9200",
    "sch125_vehicle": "9281",
    "sch125_other_expenses": "9923",
}

# ---------------------------------------------------------------------------
# Non-deductible GL codes — never flow into Schedule 125 expense fields
# (handled as add-backs on Schedule 1 instead)
# ---------------------------------------------------------------------------
NON_DEDUCTIBLE_GL_CODES: frozenset[str] = frozenset({
    "3020",   # Owner's Draw
    "5880",   # Owner Personal (Non-Deductible)
    "2910",   # Expense Claims Payable (liability movement)
    "2550",   # Related Party Repayments
    "2560",   # Related Party Expenses Paid In
})

# ---------------------------------------------------------------------------
# Explicit overrides: GL code → Schedule 125 field name
# Highest-priority; checked before keyword fallback.
# ---------------------------------------------------------------------------
GL_CODE_TO_SCH125_FIELD: dict[str, str] = {
    "5210": "sch125_salaries",        # Driver Wages / Payroll
    # Meals & Entertainment (50% already applied by extractor)
    "6100": "sch125_travel",
}

# ---------------------------------------------------------------------------
# Keyword-based fallback: keywords in GL account_name → Schedule 125 field
# Checked in ORDER — first match wins.
# ---------------------------------------------------------------------------
ACCOUNT_NAME_KEYWORD_MAP: list[tuple[list[str], str]] = [
    # Driver wages / payroll
    (
        [
            "wage",
            "salary",
            "salaries",
            "payroll",
            "driver pay",
            "driver wage",
        ],
        "sch125_salaries",
    ),
    # Employee benefits, CPP/EI
    (
        [
            "benefit",
            "cpp",
            " ei ",
            "employment insurance",
            "health benefit",
            "group insur",
        ],
        "sch125_benefits",
    ),
    # Insurance (must come AFTER 'employment insurance' above)
    (["insurance", "insur"], "sch125_insurance"),
    # Vehicle / fuel
    (
        [
            "vehicle",
            "fuel",
            "gas ",
            "gasoline",
            "mileage",
            "auto expense",
            "oil change",
        ],
        "sch125_vehicle",
    ),
    # Repairs / maintenance
    (
        [
            "repair",
            "maintenance",
            "maint",
            "upkeep",
            "service call",
        ],
        "sch125_repairs",
    ),
    # Rent / lease
    (
        ["rent", "lease payment", "office lease", "building"],
        "sch125_rent",
    ),
    # Interest / bank charges
    (
        [
            "interest",
            "bank charge",
            "bank fee",
            "nsf",
            "finance charge",
            "overdraft",
        ],
        "sch125_interest",
    ),
    # Professional fees
    (
        [
            "professional",
            "legal",
            "accounting",
            "audit",
            "bookkeep",
            "consult",
        ],
        "sch125_professional_fees",
    ),
    # Property tax
    (
        [
            "property tax",
            "municipal tax",
            "real estate tax",
            "school tax",
        ],
        "sch125_property_tax",
    ),
    # Telephone / utilities (checked before generic office keywords)
    (
        [
            "telephone",
            "phone",
            "cellphone",
            "cell phone",
            "internet",
            "utility",
            "utilities",
            "hydro",
            "electric",
        ],
        "sch125_office",
    ),
    # Office / supplies
    (
        [
            "office",
            "supply",
            "supplies",
            "stationery",
            "postage",
            "courier",
        ],
        "sch125_office",
    ),
    # Travel / meals
    (
        [
            "travel",
            "hotel",
            "accommodation",
            "parking",
            "meal",
            "food",
            "restaurant",
            "entertainment",
            "dining",
            "taxi",
        ],
        "sch125_travel",
    ),
    # Bad debts / write-offs
    (
        [
            "bad debt",
            "write-off",
            "writeoff",
            "uncollect",
            "write off",
        ],
        "sch125_bad_debts",
    ),
    # Cost of sales / direct
    (
        [
            "cost of sale",
            "inventory",
            "cogs",
            "direct cost",
            "direct labour",
            "direct material",
        ],
        "sch125_cost_of_sales",
    ),
    # Advertising
    (["advertis", "promot", "marketing", "sponsor"], "sch125_other_expenses"),
]


def gl_to_sch125_field(
    gl_code: str,
    account_name: str,
) -> str | None:
    """
    Return the Schedule 125 spinbox field name for a GL code/account name.

    Returns None for non-deductible GL codes
    (they go to Schedule 1 add-backs only).
    Returns 'sch125_other_expenses' when no specific match is found.
    """
    # Skip non-deductible GL codes entirely
    if gl_code in NON_DEDUCTIBLE_GL_CODES:
        return None

    # Skip income GL codes (4xxx range — revenue is handled separately)
    if gl_code.startswith("4"):
        return None

    # Skip balance-sheet GL codes (1xxx, 2xxx, 3xxx — not expense)
    if gl_code and gl_code[0] in ("1", "2", "3"):
        return None

    # Explicit GL code override
    if gl_code in GL_CODE_TO_SCH125_FIELD:
        return GL_CODE_TO_SCH125_FIELD[gl_code]

    # Keyword fallback on account name (case-insensitive)
    name_lower = (account_name or "").lower()
    for keywords, field in ACCOUNT_NAME_KEYWORD_MAP:
        if any(kw in name_lower for kw in keywords):
            return field

    # Default catch-all
    return "sch125_other_expenses"
