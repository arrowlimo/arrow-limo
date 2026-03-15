"""
Scan all Python files for f-string errors and generate fix report
"""
import subprocess
import re
from pathlib import Path

desktop_app = Path("l:/limo/desktop_app")
skip_patterns = ['backup', 'BACKUP', 'OLD', 'BROKEN', 'CLEAN']

errors = []

for py_file in sorted(desktop_app.glob("*.py")):
    if any(pattern in py_file.name for pattern in skip_patterns):
        continue
    
    result = subprocess.run(
        ['python', '-m', 'py_compile', str(py_file)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        # Extract line number from error
        match = re.search(r'line (\d+)', result.stderr)
        if match:
            line_num = int(match.group(1))
            errors.append((py_file.name, line_num))
            print(f"{py_file.name}:{line_num}")

print(f"\nTotal: {len(errors)} files with errors")
