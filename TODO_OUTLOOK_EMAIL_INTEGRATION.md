# TODO: Outlook Email Integration for Charter Dispatcher Notes

**Status:** Ready for Implementation  
**Priority:** Medium  
**Created:** January 24, 2026 - 3:50 PM

---

## Tasks Remaining

### 1. Database Schema Update
- [ ] Add `dispatcher_notes` column to `charters` table
- [ ] Test column creation
- [ ] Verify text storage (no length limits)

**Command:**
```powershell
cd L:\limo
.\.venv\Scripts\python.exe -c "import psycopg2; conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***'); cur = conn.cursor(); cur.execute('ALTER TABLE charters ADD COLUMN IF NOT EXISTS dispatcher_notes TEXT'); conn.commit(); print('✅ Added dispatcher_notes column'); cur.close(); conn.close()"
```

### 2. Desktop App Integration
- [ ] Update `load_charter()` to populate `self.dispatcher_notes` field
- [ ] Update `save_charter()` to persist `dispatcher_notes` to database
- [ ] Test new fields display correctly
- [ ] Load client warning flags from accounts table

### 3. Outlook VBA Installation
- [ ] Enable Developer tab in Outlook
- [ ] Import `CopyEmailToCharter.bas` macro
- [ ] Add Microsoft Forms 2.0 reference
- [ ] Add Quick Access Toolbar button
- [ ] Test clipboard copy functionality

### 4. User Testing
- [ ] Test email copy → paste workflow
- [ ] Test reserve number auto-detection
- [ ] Test multiple emails appending to same charter
- [ ] Verify formatted output is readable

### 5. Optional: Direct Database Version
- [ ] Install PostgreSQL ODBC driver (if not already installed)
- [ ] Test `CopyEmailToCharterDatabase` macro
- [ ] Test auto-save to database
- [ ] Security review (password in plain text)

---

## Files Created (Ready to Use)

✅ **Desktop App:**
- `l:\limo\desktop_app\drill_down_widgets.py` - Updated with:
  - Dispatcher Notes section (large text area)
  - Driver Instructions (renamed from driver notes)
  - Client Warning Flags display (red banner)

✅ **Outlook Add-in:**
- `l:\limo\outlook_addins\CopyEmailToCharter.bas` - VBA macro
- `l:\limo\outlook_addins\README.md` - Installation guide

---

## What Works Now vs What Needs Work

**✅ Ready:**
- UI fields created in charter form
- VBA macro written and tested (logic)
- Installation documentation complete

**⚠️ Needs Implementation:**
- Database column doesn't exist yet
- Load/save logic not wired up
- Outlook button not installed
- Client warnings not loading from accounts table

---

## Notes for Next Session

**Key Points:**
- Dispatcher notes = email/phone logs (internal operations)
- Driver instructions = pickup directions (for driver)
- Client warnings = loaded from accounts table (never pays, theft, drugs, violent, etc.)
- Outlook macro extracts reserve # from subject: `[012345]` or `Reserve #012345`

**Questions to Answer:**
- What fields exist in accounts table for warnings? (needs schema check)
- Should dispatcher notes append or replace on paste?
- Do we need timestamps for each email entry?

---

**Resume Point:** Run database schema update, then test load/save in charter form.
