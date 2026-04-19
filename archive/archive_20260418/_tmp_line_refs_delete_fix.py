from pathlib import Path
for fp, needles in [
    (Path(r'l:\limo\desktop_app\enhanced_banking_manager.py'), ['def _delete_transaction', 'DELETE FROM receipt_banking_links', 'DELETE FROM banking_transactions WHERE transaction_id']),
    (Path(r'l:\limo\desktop_app\manage_banking_widget.py'), ['def _delete_selected_transactions', 'DELETE FROM receipt_banking_links', 'UPDATE etransfer_transactions', 'DELETE FROM banking_transactions'])
]:
    lines=fp.read_text(encoding='utf-8').splitlines()
    print('\nFILE', fp)
    for n in needles:
        for i,l in enumerate(lines, start=1):
            if n in l:
                print(i, n)
                break
