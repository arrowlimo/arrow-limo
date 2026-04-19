from pathlib import Path
p=Path(r'l:\limo\desktop_app\employee_drill_down.py')
for i,line in enumerate(p.read_text(encoding='utf-8').splitlines(), start=1):
    if 1470 <= i <= 1485:
        print(i, repr(line))
