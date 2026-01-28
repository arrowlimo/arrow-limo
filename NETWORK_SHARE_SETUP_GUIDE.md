# Network Share Setup Instructions for DISPATCHMAIN

**Note:** This setup requires Administrator privileges on DISPATCHMAIN.

## Method 1: Manual PowerShell Setup (Recommended)

1. **Open PowerShell as Administrator:**
   - Right-click on PowerShell → "Run as Administrator"
   - Type: `powershell`

2. **Run the setup script:**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   & 'l:\limo\scripts\setup_network_share.ps1'
   ```

3. **When prompted:** Select "y" to create the share if needed

## Method 2: Manual SMB Share Creation

If admin PowerShell is unavailable, create the share manually:

1. **Open Settings:**
   - Settings → System → Sharing → Advanced sharing options

2. **Enable sharing:**
   - Turn ON "Network discovery"
   - Turn ON "File and printer sharing"

3. **Create the share:**
   - Right-click on `L:\limo` folder
   - Select "Share with" → "Specific people"
   - Add "Everyone"
   - Grant "Read/Write" permissions
   - Share name: `limo`
   - Network path becomes: `\\DISPATCHMAIN\limo`

## Method 3: Command Line (Requires Admin Command Prompt)

Open Command Prompt as Administrator and run:

```batch
net share limo=L:\limo /GRANT:Everyone,FULL
```

## After Share Is Created

On the OTHER 2 computers, map the network drive:

```batch
net use L: \\DISPATCHMAIN\limo /persistent:yes
```

If credentials are needed:
- Username: `DISPATCHMAIN\<username>`
- Password: (your DISPATCHMAIN login password)

## Verification

Check that the share works:
```powershell
Test-Path \\DISPATCHMAIN\limo
```

Should return `True` if accessible.

## Firewall Settings Needed

- **File and Printer Sharing** must be enabled for private networks
- **Network Discovery** must be ON
- Set network profile to "Private" (not "Public")

---

**Current Status:** Setup scripts created, awaiting admin execution on DISPATCHMAIN.
