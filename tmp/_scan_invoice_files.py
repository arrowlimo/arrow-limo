from pathlib import Path
from pypdf import PdfReader
import datetime
root = Path(r"L:/Confirmation")
files = sorted(root.glob("*invoice*.pdf"))
print("COUNT", len(files))
for f in files:
    st = f.stat()
    print("FILE", f.name, "|", st.st_size, "|", datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
    try:
        txt = (PdfReader(str(f)).pages[0].extract_text() or "").replace("\n", " ")
    except Exception as e:
        txt = f"ERR:{e}"
    print("SNIP", txt[:320])
