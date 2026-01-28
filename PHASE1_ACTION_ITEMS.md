# IMMEDIATE ACTION ITEMS - Phase 1 Handoff

**Date:** January 24, 2026 10:30 PM  
**Status:** Ready for Admin Execution

---

## 🔴 BLOCKING TASK - Requires Admin (5-10 minutes)

### Network Share Setup on DISPATCHMAIN

**Choose ONE of these 3 methods:**

#### Method A: PowerShell Script (RECOMMENDED)
```powershell
# 1. Right-click PowerShell → "Run as Administrator"
# 2. Copy & paste this:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
& 'l:\limo\scripts\setup_network_share.ps1'

# 3. When prompted, select "y" to create share
# 4. Share is created at \\DISPATCHMAIN\limo
```

#### Method B: Windows Settings GUI
```
1. Settings → System → Sharing → Advanced sharing options
2. Turn ON "Network discovery"
3. Turn ON "File and printer sharing"
4. Right-click L:\limo folder
5. Properties → Sharing → Advanced Sharing
6. Check "Share this folder"
7. Share name: limo
8. Click "Permissions" → Everyone → Full Control
9. Click Apply
```

#### Method C: Command Line (Admin CMD)
```batch
# 1. Right-click Command Prompt → "Run as Administrator"
# 2. Paste this:
net share limo=L:\limo /GRANT:Everyone,FULL

# 3. Should show: "limo was shared successfully"
```

**Verify it worked:**
```powershell
# In PowerShell, run:
Test-Path \\DISPATCHMAIN\limo

# Should return: True
```

---

## 🟢 READY NOW - No Admin Needed

### 1. Test Desktop App Connection to Neon

```powershell
cd l:\limo
python -X utf8 scripts\test_app_neon_connection.py
```

**Expected Output:**
```
✅ Charters: 18,722
✅ Vehicles: 26
✅ Payments: 83,142
✅ Neon connection ready for desktop app!
```

### 2. Launch Desktop App

```powershell
cd l:\limo
python -X utf8 desktop_app/main.py
```

**Expected Behavior:**
1. Dialog appears: "Select Database"
2. Choose "Neon (master - online)"
3. Login screen appears
4. App loads with live data

### 3. Create Similar Network Share on Client Computers

On **CLIENT1** and **CLIENT2**, run (NO admin needed):

```batch
net use L: \\DISPATCHMAIN\limo /persistent:yes
```

If asked for credentials:
- Username: `DISPATCHMAIN\<username>`
- Password: (your DISPATCHMAIN login password)

---

## 📊 What Gets Tested in Phase 2

### App Functionality
- [ ] Select "Neon (master)" in DB dialog
- [ ] Login works
- [ ] Dashboards load
- [ ] Data matches expected values
- [ ] Sorting/filtering works

### Network Share
- [ ] L: drive maps on Client1
- [ ] L: drive maps on Client2
- [ ] Can read files from L:\limo\documents
- [ ] App runs on Client1 with Neon

### Data Quality
- [ ] 18,722 charters visible
- [ ] 26 vehicles all accessible
- [ ] FK constraints intact
- [ ] No orphaned records

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `desktop_app/main.py` | App with Neon selector |
| `scripts/setup_network_share.ps1` | Network share setup (admin) |
| `scripts/restore_vehicles_final.py` | Vehicle restore (already done) |
| `PHASE1_COMPLETION_REPORT.md` | Full completion details |
| `NETWORK_SHARE_SETUP_GUIDE.md` | Network share manual instructions |

---

## 🚨 If Something Goes Wrong

### Issue: "Can't connect to Neon"
**Solution:**
```powershell
python -X utf8 scripts\test_app_neon_connection.py
```
Shows detailed error. If network issue, check firewall rules.

### Issue: "Share not found"
**Solution:**
Verify on DISPATCHMAIN:
```powershell
Get-SmbShare -Name "limo"
```
If not found, re-run Method A/B/C above.

### Issue: "Can't authenticate on client"
**Solution:**
Disconnect and reconnect with explicit credentials:
```batch
net use L: /delete
net use L: \\DISPATCHMAIN\limo /user:DISPATCHMAIN\username password /persistent:yes
```

### Issue: "App shows blank data"
**Solution:**
Check DB target selected:
1. App startup dialog
2. Ensure "Neon" selected
3. Check if charters load
4. If still blank, check `desktop_app/main.py` login code

---

## ✅ Success Criteria

**Phase 1 Complete When:**
- ✅ Network share created on DISPATCHMAIN
- ✅ Desktop app connects to Neon (not local)
- ✅ 18,722 charters visible in app
- ✅ 26 vehicles accessible
- ✅ L: drive maps on at least 1 other computer

**Estimated Time:** 30 minutes total

---

## 📞 Questions?

1. **Database:** Check the restore scripts in `scripts/`
2. **Network:** See `NETWORK_SHARE_SETUP_GUIDE.md`
3. **Code:** Check git history or `desktop_app/main.py` comments

---

**Next Session:** Start Phase 2 QA Testing once network share is live.

