# Calendar Fixes & Installer Information

**Date:** January 30, 2026

---

## Question 1: Why Are Calendar Events Squishy and Empty?

### Problems Identified

Looking at your screenshot, I found **3 issues**:

#### Issue 1: Events Don't Span Proper Time Duration ❌
**Current behavior:** All events show as small 1.5-hour blocks at the top of their time slot  
**Why:** Code in `outlook_style_calendar_widget.py` line 547 hardcodes:
```python
height = int(self.hour_height * 1.5)  # Always 1.5 hours!
```

**Fix needed:** Calculate actual duration from pickup_time to dropoff_time or estimated duration

#### Issue 2: No Filter Options ❌
**Current behavior:** Calendar shows ALL charters (quotes + bookings + cancelled)  
**What you want:** Filter options to display:
- All events
- Only bookings (confirmed charters)
- Only quotes
- Only assigned (with driver/vehicle)
- Hide cancelled

**Fix needed:** Add checkboxes at top: `☑ Bookings  ☑ Quotes  ☐ Cancelled  ☑ Assigned  ☐ Unassigned`

#### Issue 3: Other Calendar Tabs Are Empty ❌
**Tabs affected:**
- Driver Calendar - should show only specific driver's assignments
- Dispatcher Calendar (Table View) - working (as shown)
- Unbooked Events - shows only events not yet converted to charters

**Fix needed:** Driver Calendar needs data loading logic (currently skeleton code)

---

### SOLUTION - What Needs to Be Fixed

I'll create a patch that:

1. **Calculate Event Heights**
   - Use charter duration (pickup to dropoff time)
   - If duration unknown, estimate based on booking type:
     * Hourly → show hours * hour_height
     * Airport runs → 2 hours
     * Weddings → 4 hours
     * Default → 1.5 hours

2. **Add Filter Toolbar**
   ```
   Show: ☑ Bookings  ☑ Quotes  ☐ Cancelled  ☑ Assigned Only  
   ```
   Filters update calendar in real-time

3. **Fix Driver Calendar**
   - Load charters filtered by employee_id
   - Show "Your Schedule" view for logged-in driver

4. **Fix Event Overlap**
   - When multiple events start at same time, offset them horizontally
   - Show partial width side-by-side instead of overlapping

---

## Question 2: Do I Need to Create L:\limo Drive for Exe Installation?

### Answer: **NO! ❌**

The `L:\limo` path is **ONLY your development workspace**. The exe is **completely portable**.

### How the Exe Actually Works

**Dispatcher can install anywhere:**
```
✅ C:\ArrowLimo\
✅ C:\Users\Dispatcher\Desktop\ArrowApp\
✅ D:\Programs\Limousine\
✅ USB drive (E:\Portable\ArrowLimo\)
✅ Network drive (\\Server\Apps\ArrowLimo\)
✅ ANY folder on ANY drive
```

**Only requirement:** `.env` file must be in **same folder** as the exe

### Why L:\limo Doesn't Matter

The exe uses **relative paths**, not absolute:

```python
# NOT this (hardcoded):
config_path = "L:\\limo\\config\\settings.json"  # ❌ Would fail

# But this (relative to exe location):
config_path = os.path.join(os.path.dirname(__file__), "config", "settings.json")  # ✅
```

PyInstaller bundles everything the exe needs, so it doesn't reference L:\limo at all.

### Dispatcher Installation Example

**Dispatcher receives:** `ArrowLimousine_Installer.zip` (150-200 MB)

**Dispatcher extracts to:** `C:\MyApps\ArrowLimo\`

**Folder contents:**
```
C:\MyApps\ArrowLimo\
├── ArrowLimousineApp.exe    ← The app
├── .env.example              ← Template
└── DISPATCHER_SETUP.md       ← Instructions
```

**Dispatcher setup:**
1. Copy `.env.example` → `.env`
2. Edit `.env`:
   ```ini
   DB_HOST=your-neon-host.us-west-2.aws.neon.tech
   DB_NAME=almsdata
   DB_USER=dispatcher_user
   DB_PASSWORD=secure_password_123
   ```
3. Double-click `ArrowLimousineApp.exe`
4. Login and use!

**No L: drive needed!** The exe works from wherever it's extracted.

---

## Summary

| Question | Answer |
|----------|--------|
| **Why are events squishy?** | Hardcoded 1.5-hour height. Need duration calculation. |
| **Why no filter options?** | Not implemented yet. Will add checkbox filters. |
| **Why other calendars empty?** | Driver Calendar needs data loading code. |
| **Need L:\limo drive for exe?** | **NO!** Exe works from any folder anywhere. |

---

## Next Steps

### For Calendar Fixes (I can do this now):
Would you like me to:
1. ✅ Fix event height calculation (use actual charter duration)
2. ✅ Add filter checkboxes (Bookings/Quotes/Cancelled/Assigned)
3. ✅ Fix Driver Calendar to load driver's assignments
4. ✅ Improve event overlap handling

### For Exe Distribution:
The deployment system is **ready to use**:
1. Run `build_exe.bat` (takes 3-5 min)
2. Wait for `dist\ArrowLimousineApp.exe` to be created
3. Create ZIP: `Compress-Archive -Path "dist\ArrowLimousine_Deployment" -DestinationPath "ArrowLimo_Installer.zip"`
4. Send ZIP to dispatcher (works on any Windows PC, any folder)

---

**Want me to implement the calendar fixes now?** I can:
- Patch the height calculation
- Add filter toolbar
- Fix driver calendar data loading
- Test and verify

Let me know!
