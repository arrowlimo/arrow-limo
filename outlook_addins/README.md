# Outlook Email-to-Charter Add-In

## Overview
This Outlook VBA macro allows you to copy selected email content directly into charter dispatcher notes with a single click.

## Features
✅ **Copy to Clipboard** - Extract email and paste into charter form  
✅ **Auto-detect Reserve Number** - Extracts reserve # from email subject  
✅ **Formatted Output** - Includes sender, date, subject, body  
✅ **Direct Database Insert** (optional) - Writes directly to database

---

## Installation Steps

### 1. Enable Outlook Developer Tab
1. Open Outlook
2. **File** → **Options** → **Customize Ribbon**
3. Check ☑ **Developer** on the right side
4. Click **OK**

### 2. Import VBA Macro
1. Click **Developer** tab
2. Click **Visual Basic** (or press **ALT+F11**)
3. In VBA Editor: **File** → **Import File...**
4. Browse to: `L:\limo\outlook_addins\CopyEmailToCharter.bas`
5. Click **Import**

### 3. Add Required References
1. In VBA Editor: **Tools** → **References...**
2. Check ☑ **Microsoft Forms 2.0 Object Library**
3. (For database version) Check ☑ **Microsoft ActiveX Data Objects 6.1 Library**
4. Click **OK**

### 4. Add Button to Outlook Ribbon

**Option A: Quick Access Toolbar (Easiest)**
1. In Outlook, click the **▼** dropdown at top-left (Quick Access Toolbar)
2. Click **More Commands...**
3. In "Choose commands from" dropdown, select **Macros**
4. Find `CopyEmailToCharterNotes` in the list
5. Click **Add >>**
6. Click **Modify...** to choose an icon (suggest: 📧 or 📋)
7. Name it: **Copy to Charter**
8. Click **OK**

**Option B: Custom Ribbon Tab (Advanced)**
- Use Outlook Ribbon customization (requires XML manifest)
- See Microsoft docs for custom ribbon XML

---

## Usage

### Method 1: Clipboard Copy (Recommended)

1. **Select an email** in Outlook containing charter info
2. Click the **Copy to Charter** button (Quick Access Toolbar)
3. Email content is copied to clipboard
4. Open charter in desktop app
5. Click in **Dispatcher Notes** field
6. **Paste** (Ctrl+V)

**Email Subject Format:**
- Include reserve number for auto-detection:
  - `Re: [012345] Wedding Transportation`
  - `Reserve #012345 - Airport Pickup`
  - `Res#012345 Question`

### Method 2: Direct Database Insert (Advanced)

1. **Select an email** with reserve # in subject
2. Run macro: `CopyEmailToCharterDatabase` (via VBA Editor or custom button)
3. Email content is written directly to `charters.dispatcher_notes`
4. Refresh charter form to see changes

⚠️ **Database version requires:**
- PostgreSQL ODBC driver installed
- Network access to database server
- Reserve number in email subject (auto-detected)

---

## Output Format

```
================================
EMAIL COPIED: 2026-01-24 03:45 PM
RESERVE #: 012345
================================
FROM: John Smith <john@example.com>
DATE: 2026-01-24 02:30 PM
SUBJECT: Re: [012345] Wedding Transportation
--------------------------------

Hi Arrow Limousine,

Can we change the pickup time to 4:00 PM instead of 3:30 PM?
Also, we'll need an extra stop at the florist before the venue.

Thanks,
John

================================
```

---

## Troubleshooting

**Problem: Button doesn't appear**
- Solution: Check Quick Access Toolbar customization, ensure macro is enabled

**Problem: "Macro not found"**
- Solution: Verify `CopyEmailToCharterNotes` is imported and visible in VBA Editor

**Problem: "ActiveX component can't create object"**
- Solution: Add Microsoft Forms 2.0 reference (Tools → References)

**Problem: Database version fails**
- Solution: Check database connection string, ensure PostgreSQL ODBC driver installed

**Problem: Reserve number not detected**
- Solution: Email subject must contain `[012345]`, `Reserve #012345`, or `Res#012345`

---

## Database Schema Update

Add the `dispatcher_notes` column to the `charters` table:

```sql
-- Add dispatcher_notes column if it doesn't exist
ALTER TABLE charters 
ADD COLUMN IF NOT EXISTS dispatcher_notes TEXT;

-- Add index for faster searches
CREATE INDEX IF NOT EXISTS idx_charters_dispatcher_notes 
ON charters USING gin(to_tsvector('english', dispatcher_notes));
```

Run this via:
```powershell
cd L:\limo
.\.venv\Scripts\python.exe -c "
import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute('ALTER TABLE charters ADD COLUMN IF NOT EXISTS dispatcher_notes TEXT')
conn.commit()
print('✅ dispatcher_notes column added')
cur.close()
conn.close()
"
```

---

## Security Notes

⚠️ **Database Password**: The direct database version contains the password in plain text. Consider:
- Using Windows Authentication instead
- Storing connection string in separate config file
- Restricting macro access to authorized users only

---

## Future Enhancements

- [ ] Auto-save attachments to charter folder
- [ ] Parse email body for pickup time, address changes
- [ ] Two-way sync with Outlook calendar
- [ ] Email template responses
- [ ] Search dispatcher notes from Outlook

---

## Support

For issues or questions, contact IT support or review the VBA code in:
`L:\limo\outlook_addins\CopyEmailToCharter.bas`
