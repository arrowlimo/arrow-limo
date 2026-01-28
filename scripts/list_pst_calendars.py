import sys
import os
import win32com.client
import pythoncom

def walk_folders(folder, results):
    try:
        default_type = getattr(folder, 'DefaultItemType', None)
    except Exception:
        default_type = None
    try:
        name = folder.Name
    except Exception:
        name = '<unknown>'
    try:
        items_count = folder.Items.Count
    except Exception:
        items_count = None

    # 1 = olAppointmentItem
    if default_type == 1 or (isinstance(name, str) and 'calendar' in name.lower()):
        results.append({
            'path': get_folder_path(folder),
            'name': name,
            'items': items_count,
        })

    # Recurse children
    try:
        for sub in folder.Folders:
            walk_folders(sub, results)
    except Exception:
        pass


def get_folder_path(folder):
    parts = []
    try:
        f = folder
        while True:
            parts.append(f.Name)
            parent = f.Parent
            if parent is None or parent == f:
                break
            f = parent
    except Exception:
        pass
    return '/'.join(reversed(parts))


def main():
    if len(sys.argv) < 2:
        print('Usage: python list_pst_calendars.py <pst_path>')
        sys.exit(1)
    pst_path = sys.argv[1]
    if not os.path.exists(pst_path):
        print(f'PST not found: {pst_path}')
        sys.exit(2)

    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.gencache.EnsureDispatch('Outlook.Application')
        namespace = outlook.GetNamespace('MAPI')

        # Attach PST if not already
        try:
            namespace.AddStore(pst_path)
        except Exception:
            # If already added, ignore
            pass

        calendars = []

        # Iterate all root folders
        try:
            # Prefer Stores (newer API) if available
            stores = getattr(namespace, 'Stores', None)
            if stores is not None:
                for store in stores:
                    try:
                        root_folder = store.GetRootFolder()
                        walk_folders(root_folder, calendars)
                    except Exception:
                        continue
            else:
                for root in namespace.Folders:
                    walk_folders(root, calendars)
        except Exception as e:
            print('Failed iterating stores:', e)

        # Print result
        found_arrow_new = False
        for c in calendars:
            print(f"CALENDAR | items={c['items']:<5} | {c['path']}")
            if c['name'] and str(c['name']).strip().lower() == 'arrow new':
                found_arrow_new = True
        print('\nSummary:')
        print(f'  Calendars found: {len(calendars)}')
        print(f"  'Arrow New' present: {'YES' if found_arrow_new else 'NO'}")

    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

if __name__ == '__main__':
    main()
