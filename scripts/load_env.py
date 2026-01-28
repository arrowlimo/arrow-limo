import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOTENV = ROOT / '.env'

def load_env():
    # Load simple KEY=VALUE pairs into environment if .env exists
    if DOTENV.exists():
        for line in DOTENV.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                if k and v is not None:
                    os.environ.setdefault(k.strip(), v.strip())


def get_env(name: str, default: str = None):
    return os.environ.get(name, default)

if __name__ == '__main__':
    load_env()
    # Print masked summary
    u = get_env('EMAIL_USERNAME', '')
    p = get_env('EMAIL_PASSWORD', '')
    print('EMAIL_USERNAME:', u)
    print('EMAIL_PASSWORD:', ('*' * len(p)) if p else '(not set)')
