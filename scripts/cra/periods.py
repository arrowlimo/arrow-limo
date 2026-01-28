from dataclasses import dataclass
from datetime import date

@dataclass
class Period:
    start: date
    end: date
    label: str


def parse_period(s: str) -> Period:
    """Supported forms: 2025Q1, 2025Q2, 2025Q3, 2025Q4, 2025, 2025-01..2025-03.
    Returns inclusive start/end dates.
    """
    s = s.strip().upper()
    if len(s) == 6 and s.endswith(('Q1','Q2','Q3','Q4')):
        year = int(s[:4])
        q = int(s[-1])
        if q == 1:
            return Period(date(year,1,1), date(year,3,31), f"{year}Q1")
        if q == 2:
            return Period(date(year,4,1), date(year,6,30), f"{year}Q2")
        if q == 3:
            return Period(date(year,7,1), date(year,9,30), f"{year}Q3")
        return Period(date(year,10,1), date(year,12,31), f"{year}Q4")
    if len(s) == 4 and s.isdigit():
        year = int(s)
        return Period(date(year,1,1), date(year,12,31), f"{year}")
    if '..' in s:
        a,b = s.split('..',1)
        ya,ma = [int(x) for x in a.split('-',1)]
        yb,mb = [int(x) for x in b.split('-',1)]
        from calendar import monthrange
        return Period(date(ya,ma,1), date(yb,mb,monthrange(yb,mb)[1]), f"{a}..{b}")
    raise ValueError(f"Unsupported period format: {s}")
