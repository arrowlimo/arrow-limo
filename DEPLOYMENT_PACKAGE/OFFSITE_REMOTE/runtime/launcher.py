import os
import runpy
import sys
from pathlib import Path


def main() -> int:
    install_root = Path(__file__).resolve().parent
    desktop_app = install_root / "desktop_app"
    main_py = desktop_app / "main.py"

    if not main_py.exists():
        print(f"Desktop application entrypoint not found: {main_py}")
        return 1

    os.chdir(str(desktop_app))
    for path_candidate in (str(desktop_app), str(install_root)):
        if path_candidate not in sys.path:
            sys.path.insert(0, path_candidate)

    runpy.run_path(str(main_py), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())