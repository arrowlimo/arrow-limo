import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import get_db_connection  # type: ignore

# This orchestrates: create tables (via migration), load CSVs, then apply to receipts
from scripts.load_epson_mappings import main as load_mappings  # type: ignore
from scripts.apply_epson_mappings_to_receipts import main as apply_mappings  # type: ignore

MIGRATION = ROOT / 'migrations' / '2025-09-25_create_epson_mapping_tables.sql'


def run_migration():
    sql = MIGRATION.read_text(encoding='utf-8')
    conn = get_db_connection(); conn.autocommit = False
    try:
        cur = conn.cursor(); cur.execute(sql); conn.commit()
        print('[OK] Migration applied or already in place.')
    except Exception as e:
        conn.rollback(); print(f'[ERROR] migration failed: {e}'); raise
    finally:
        conn.close()


def main():
    run_migration()
    load_mappings()
    apply_mappings()

if __name__ == '__main__':
    main()
