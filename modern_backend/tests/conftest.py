import pathlib
import sys

# Ensure repository root is on sys.path for package import
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
